"""The eval runner, run against the scripted stand-in for Claude, so no API calls are made."""

import json

import pytest

from agent import __version__, costs
from agent.graph import AgentConfig
from evals.cases import load_what_cases
from evals.graders import WhatGrader
from evals.run_evals import (
    check_grader,
    resummarize,
    run_cases,
    saved_records,
    select_cases,
    summarize,
    wilson_range,
    write_markdown,
)
from tests.fakes import FakeClaude, reply, report, sql_call

CASES = {case.id: case for case in load_what_cases()}


@pytest.fixture(autouse=True)
def ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(costs, "LEDGER", tmp_path / "spend.jsonl")
    monkeypatch.delenv("SPEND_LIMIT_USD", raising=False)


@pytest.fixture(scope="module")
def grader(guarded_warehouse):
    return WhatGrader(guarded_warehouse)


@pytest.fixture
def config(guarded_warehouse):
    return AgentConfig(warehouse=guarded_warehouse, transport="inprocess")


def test_wilson_range_matches_the_plans_example():
    low, high = wilson_range(27, 30)
    assert low == pytest.approx(0.74, abs=0.01) and high == pytest.approx(0.97, abs=0.01)
    assert wilson_range(0, 0) == (0.0, 0.0)


def test_the_smoke_subset_names_real_cases_and_passes_the_grader_check(grader):
    cases = select_cases("smoke", None)
    assert 5 <= len(cases) <= 10
    check_grader(grader, cases)  # raises SystemExit on a problem


def test_a_run_grades_each_case_and_saves_its_transcript(config, grader, tmp_path):
    right = CASES["what-loss-ratio-by-product-2025"]
    wrong = CASES["what-claim-count-total-2025-q4"]
    fake = FakeClaude(
        reply(sql_call("SELECT 1 AS x"), stop_reason="tool_use"),
        reply(report(right.reference_sql[0])),
        reply(report("SELECT 12345 AS claims")),
    )
    records, skipped, version = run_cases([right, wrong], config, grader, tmp_path, 1.0, fake)

    assert [r["grade"]["category"] for r in records] == ["pass", "wrong_result"]
    assert skipped == [] and version.startswith(f"{__version__}+")
    saved = json.loads((tmp_path / "cases" / f"{right.id}.json").read_text())
    assert saved["transcript"][0]["role"] == "user" and len(saved["transcript"]) == 4
    assert saved["tool_calls"][0]["sql"] == "SELECT 1 AS x"

    summary = summarize("test", records, skipped, config.settings, version)
    assert summary["passed"] == 1 and summary["categories"] == {"pass": 1, "wrong_result": 1}
    assert summary["cost_usd"] == pytest.approx(sum(r["cost_usd"] for r in records), abs=1e-4)


def test_a_run_stops_at_its_cost_cap(config, grader, tmp_path):
    expensive = {"input_tokens": 200_000, "output_tokens": 0}  # $0.40 a call
    cases = [CASES["what-claim-count-total-2025-q4"], CASES["what-paid-amount-total-2025"]]
    fake = FakeClaude(reply(report("SELECT 1 AS x"), usage=expensive))
    records, skipped, _ = run_cases(cases, config, grader, tmp_path, 0.30, fake)
    assert len(records) == 1 and skipped == [cases[1].id]


def test_an_api_error_counts_as_an_error_not_a_wrong_answer(config, grader, tmp_path):
    fake = FakeClaude(reply(stop_reason="refusal"))
    records, _, _ = run_cases([CASES["what-claim-count-total-2025-q4"]], config, grader,
                              tmp_path, 1.0, fake)
    assert records[0]["grade"]["category"] == "error"


def test_a_stopped_run_can_be_resumed_without_rerunning_saved_cases(config, grader, tmp_path):
    first, second = CASES["what-claim-count-total-2025-q4"], CASES["what-paid-amount-total-2025"]
    run_cases([first], config, grader, tmp_path, 1.0, FakeClaude(reply(report())))
    saved = saved_records(tmp_path)
    assert list(saved) == [first.id]

    fake = FakeClaude(reply(report()))
    to_run = [case for case in (first, second) if case.id not in saved]
    records, _, _ = run_cases(to_run, config, grader, tmp_path, 1.0, fake)
    assert [r["case_id"] for r in records] == [second.id] and len(fake.requests) == 1
    assert set(saved_records(tmp_path)) == {first.id, second.id}


def test_a_follow_up_is_asked_in_the_same_session_and_graded(config, grader, tmp_path):
    from evals.cases import load_followup_cases
    from evals.graders import FollowUpGrader

    case = next(c for c in load_followup_cases() if c.id == "followup-loss-ratio-next-period")
    fake = FakeClaude(reply(report("SELECT 1 AS x")), reply(report(case.grade_as.reference_sql[0])))
    records, _, _ = run_cases([case], config, FollowUpGrader(grader), tmp_path, 1.0, fake)

    record = records[0]
    assert record["grade"]["category"] == "pass"
    assert record["first"]["question"] == case.first
    assert record["cost_usd"] == pytest.approx(record["first"]["cost_usd"] * 2, abs=1e-6)
    second = fake.requests[1]["messages"]
    assert [m["role"] for m in second] == ["user", "assistant", "user"]
    assert second[-1]["content"][-1]["text"] == case.question


def test_each_case_records_how_many_key_numbers_its_sql_confirms(config, grader, tmp_path):
    body = json.loads(report()["text"])
    body["findings"] = [{"claim": "c", "evidence_sql": "SELECT 7 AS n", "confidence": "high",
                         "key_numbers": [{"label": "n", "value": 7, "unit": "claims"},
                                         {"label": "m", "value": 9, "unit": "claims"}]}]
    # The agent asks once for the unconfirmed number to be fixed; here the model doesn't.
    fake = FakeClaude(reply({"type": "text", "text": json.dumps(body)}),
                      reply({"type": "text", "text": json.dumps(body)}))
    records, _, _ = run_cases([CASES["what-claim-count-total-2025-q4"]], config, grader,
                              tmp_path, 1.0, fake)
    assert (records[0]["numbers"]["confirmed"], records[0]["numbers"]["checked"]) == (1, 2)
    summary = summarize("test", records, [], config.settings, None)
    assert (summary["key_numbers_confirmed"], summary["key_numbers_checked"]) == (1, 2)


def why_record(case_id: str, category: str, report: dict | None = None) -> dict:
    return {"case_id": case_id, "grade": {"passed": category == "pass", "category": category,
                                          "reason": "code checks"},
            "report": report, "cost_usd": 0.01, "seconds": 1.0, "tool_calls": [],
            "model_calls": [], "fell_back": False, "models_served": [], "agent_version": "v"}


def test_llm_verdicts_score_why_answers_but_never_overrule_a_code_failure(config):
    records = [why_record("a", "pass"), why_record("b", "unscored"),
               why_record("c", "missing_evidence"), why_record("d", "unscored")]
    llm = {"grader": "claude-opus-5-5", "trusted": True, "grades": {
        "a": {"passed": False, "reason": "Invents a cause.", "cost_usd": 0.01},
        "b": {"passed": True, "reason": "No cause invented.", "cost_usd": 0.01},
        "c": {"passed": True, "reason": "Fine.", "cost_usd": 0.01}}}
    summary = summarize("test", records, [], config.settings, None, llm=llm)
    assert {case: g["category"] for case, g in summary["grades"].items()} == {
        "a": "wrong_explanation", "b": "pass", "c": "missing_evidence", "d": "unscored"}
    assert (summary["passed"], summary["scored"], summary["unscored"]) == (1, 3, 1)
    assert summary["llm_grader"]["cost_usd"] == pytest.approx(0.03)


def test_llm_verdicts_are_left_out_when_the_graders_own_checks_failed(config):
    llm = {"grader": "claude-opus-5-5", "trusted": False,
           "grades": {"b": {"passed": True, "reason": "", "cost_usd": 0.0}}}
    summary = summarize("test", [why_record("b", "unscored")], [], config.settings, None, llm=llm)
    assert summary["unscored"] == 1 and summary["llm_grader"]["trusted"] is False


def test_a_saved_run_can_be_resummarized_with_its_llm_grades_and_no_api_calls(guarded_warehouse,
                                                                              tmp_path):
    folder = tmp_path / "run"
    (folder / "cases").mkdir(parents=True)
    answer = {"findings": [{"claim": "c", "evidence_sql": "SELECT 3 AS n",
                            "key_numbers": [{"label": "n", "value": 3, "unit": "claims"}]}]}
    case_id = "why-motor-book-shrinking"
    (folder / "cases" / f"{case_id}.json").write_text(
        json.dumps(why_record(case_id, "unscored", answer)))
    (folder / "summary.json").write_text(json.dumps({"model": "claude-sonnet-5-5",
                                                     "effort": "high", "toolset": "full"}))
    (folder / "llm_grades.json").write_text(json.dumps({
        "grader": "claude-opus-5-5", "trusted": True,
        "grades": {case_id: {"passed": True, "reason": "No cause invented.", "cost_usd": 0.005}}}))

    summary = resummarize(folder, guarded_warehouse)
    assert (summary["passed"], summary["unscored"], summary["effort"]) == (1, 0, "high")
    assert summary["key_numbers_confirmed"] == 1
    markdown = (folder / "summary.md").read_text()
    assert "LLM grader: claude-opus-5-5" in markdown and "confirmed by their finding's SQL: 1/1" \
        in markdown


def test_repeat_runs_cover_every_case_before_repeating_and_resume_where_they_stopped(
        config, grader, tmp_path):
    first, second = CASES["what-claim-count-total-2025-q4"], CASES["what-paid-amount-total-2025"]
    expensive = {"input_tokens": 200_000, "output_tokens": 0}  # $0.40 a call
    fake = FakeClaude(*[reply(report(), usage=expensive) for _ in range(3)])
    records, skipped, _ = run_cases([first, second], config, grader, tmp_path, 1.0, fake,
                                    repeats=2)
    assert [(r["case_id"], r["repeat"]) for r in records] == [
        (first.id, 1), (second.id, 1), (first.id, 2)]
    assert skipped == [f"{second.id}.r2"]
    assert sorted(saved_records(tmp_path)) == sorted([first.id, second.id, f"{first.id}.r2"])

    fake = FakeClaude(reply(report()))
    records, _, _ = run_cases([first, second], config, grader, tmp_path, 1.0, fake, repeats=2,
                              done=set(saved_records(tmp_path)))
    assert [(r["case_id"], r["repeat"]) for r in records] == [(second.id, 2)]
    assert (tmp_path / "cases" / f"{second.id}.r2.json").exists()


def repeat_record(case_id: str, repeat: int, passed: bool) -> dict:
    return why_record(case_id, "pass" if passed else "wrong_result") | {"repeat": repeat}


def test_with_repeats_the_headline_counts_cases_that_passed_every_run(config, tmp_path):
    records = [repeat_record("a", 1, True), repeat_record("b", 1, True),
               repeat_record("a", 2, True), repeat_record("b", 2, False),
               repeat_record("a", 3, True), repeat_record("b", 3, True)]
    summary = summarize("test", records, [], config.settings, None)
    assert (summary["passed"], summary["scored"], summary["repeats"]) == (1, 2, 3)
    assert (summary["cases"], summary["runs"]) == (2, 6)
    assert summary["consistency"] == {"runs_passed": 5, "runs_scored": 6,
                                      "per_repeat": [[2, 2], [1, 2], [2, 2]],
                                      "mixed_cases": ["b"]}
    write_markdown(tmp_path / "summary.md", summary, records)
    markdown = (tmp_path / "summary.md").read_text()
    assert "Passed in every run: **1/2 cases**" in markdown and "per run: 2/2, 1/2, 2/2" in markdown
    assert "| b.r2 | wrong_result |" in markdown


def test_an_llm_verdict_applies_to_its_own_repeat_run(config):
    records = [repeat_record("a", 1, True), repeat_record("a", 2, True)]
    llm = {"grader": "claude-opus-5-5", "trusted": True, "grades": {
        "a": {"passed": True, "reason": "Right.", "cost_usd": 0.0},
        "a.r2": {"passed": False, "reason": "Invents a cause.", "cost_usd": 0.0}}}
    summary = summarize("test", records, [], config.settings, None, llm=llm)
    assert summary["grades"]["a"]["category"] == "pass"
    assert summary["grades"]["a.r2"]["category"] == "wrong_explanation"
    assert summary["consistency"]["mixed_cases"] == ["a"] and summary["passed"] == 0
