"""The LLM grader, run against a stand-in for the Batch API, so no API calls are made."""

import json
from types import SimpleNamespace

import pytest
from anthropic.types import Message

from agent import costs
from evals.cases import load_why_cases
from evals.graders.llm import GRADER_MODEL, Item, grade_folders, request_params

WHY = {case.id: case for case in load_why_cases()}
USAGE = {"input_tokens": 1_000_000, "output_tokens": 0}  # $4.00 at full price


def verdict(passed: bool, reason: str = "ok") -> Message:
    body = {"explains_correctly": passed, "unsupported_causes": [] if passed else ["noise"],
            "verdict": "pass" if passed else "fail", "reason": reason}
    return Message.model_validate({
        "id": "msg", "type": "message", "role": "assistant", "model": GRADER_MODEL,
        "content": [{"type": "text", "text": json.dumps(body)}], "stop_reason": "end_turn",
        "stop_sequence": None, "usage": USAGE})


class FakeBatches:
    """Decides each verdict with `judge(custom_id, params)`."""

    def __init__(self, judge):
        self.judge, self.requests, self.polls = judge, [], 0
        self.messages = SimpleNamespace(batches=self)

    def create(self, requests):
        self.requests = requests
        return SimpleNamespace(id="batch-1")

    def retrieve(self, batch_id):
        self.polls += 1
        return SimpleNamespace(processing_status="ended" if self.polls > 1 else "in_progress")

    def results(self, batch_id):
        for request in self.requests:
            message = verdict(self.judge(request["custom_id"], request["params"]))
            yield SimpleNamespace(custom_id=request["custom_id"],
                                  result=SimpleNamespace(type="succeeded", message=message))


@pytest.fixture(autouse=True)
def ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(costs, "LEDGER", tmp_path / "spend.jsonl")
    monkeypatch.delenv("SPEND_LIMIT_USD", raising=False)


@pytest.fixture
def run_folder(tmp_path):
    folder = tmp_path / "run"
    (folder / "cases").mkdir(parents=True)
    for case_id in ("why-nsw-cost-july-2026", "why-motor-book-shrinking"):
        report = {"answer": f"Answer to {case_id}", "findings": [
            {"claim": "c", "evidence_sql": "SELECT secret_sql", "key_numbers": []}],
            "hypotheses": [], "data_quality_issues": []}
        (folder / "cases" / f"{case_id}.json").write_text(
            json.dumps({"case_id": case_id, "report": report}))
    return folder


def test_grades_are_written_and_checked(run_folder, built):
    manifest = built[2].with_name("dev_manifest.json")
    fake = FakeBatches(lambda custom_id, params: custom_id != "check-empty")
    outcome = grade_folders(fake, [run_folder], manifest, poll_seconds=0)

    assert outcome["trusted"] is True
    saved = json.loads((run_folder / "llm_grades.json").read_text())
    assert saved["trusted"] and set(saved["grades"]) == {"why-nsw-cost-july-2026",
                                                         "why-motor-book-shrinking"}
    # Batch prices are half the normal price, and every grade is in the spend ledger.
    assert costs.spent() == pytest.approx(4 * 2.0)


def test_grades_are_untrusted_when_the_checks_fail(run_folder, built):
    manifest = built[2].with_name("dev_manifest.json")
    outcome = grade_folders(FakeBatches(lambda *_: True), [run_folder], manifest, poll_seconds=0)
    assert outcome["trusted"] is False  # it passed an empty answer


def test_the_request_uses_another_model_and_leaves_out_the_sql():
    case = WHY["why-nsw-cost-july-2026"]
    report = {"answer": "An East Coast Low", "findings": [{"claim": "c", "evidence_sql": "SELECT 1",
                                                     "key_numbers": []}]}
    params = request_params(Item("x", case, "The storm WX-003", report))
    assert params["model"] == GRADER_MODEL != "claude-sonnet-5-5"
    assert params["output_config"]["effort"] == "medium" and "tool_choice" not in params
    text = params["messages"][0]["content"]
    assert "The storm WX-003" in text and "An East Coast Low" in text and "SELECT 1" not in text


def test_the_label_sheet_keeps_your_labels_and_measures_agreement(run_folder, built, tmp_path):
    from evals.graders.labels import agreement, read_sheet, write_sheet

    manifest = built[2].with_name("dev_manifest.json")
    (run_folder / "llm_grades.json").write_text(json.dumps({"grades": {
        "why-nsw-cost-july-2026": {"passed": True, "reason": "names the storm"},
        "why-motor-book-shrinking": {"passed": False, "reason": "invents a cause"}}}))
    sheet = tmp_path / "labels.csv"
    assert write_sheet([run_folder], sheet, manifest) == 2

    rows = read_sheet(sheet)
    rows[0]["your_verdict"] = "fail"  # why-motor-book-shrinking: agrees with the grader
    rows[1]["your_verdict"] = "fail"  # why-nsw-cost-july-2026: disagrees
    import csv
    with sheet.open("w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    result = agreement(read_sheet(sheet))
    assert result["labeled"] == 2 and result["agree"] == 1
    assert result["disagreements"] == [("why-nsw-cost-july-2026", "fail", "pass")]
    # Rewriting the sheet keeps the labels already filled in.
    write_sheet([run_folder], sheet, manifest)
    assert [r["your_verdict"] for r in read_sheet(sheet)] == ["fail", "fail"]
