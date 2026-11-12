"""The compliance review (agent/compliance.py), its grader and the held-out split. No API calls:
the judge is a scripted fake, and the knowledge base uses the hash test embedder."""

import json
from datetime import date

import pytest

from agent import costs
from agent.compliance import (
    CHECKS,
    VERDICT_FORMAT,
    ComplianceError,
    ReviewConfig,
    aggregate,
    as_of_dates,
    load_facts,
    retrieve_for_check,
    review_claim,
    review_claims_batch,
    sub_queries,
    validate,
)
from agent.tools import _policy_library
from evals.graders.compliance import grade, load_compliance_cases, reference_review, summarise
from tests.fakes import FakeClaude, reply


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(costs, "LEDGER", tmp_path / "spend.jsonl")


@pytest.fixture
def warehouse(guarded_warehouse):
    """Facts are read over the SQL guard's connection, so through the guarded copy."""
    return guarded_warehouse


def finding(check="exclusions", status="BREACH", severity="HIGH", clause_ids=("POL-MTR-002:3.4",),
            evidence=(("licence_status", "EXPIRED"),)) -> dict:
    return {"check": check, "status": status, "severity": severity, "rule": "r",
            "clause_ids": list(clause_ids), "calculation": "", "explanation": "e",
            "evidence": [{"field": f, "value": v} for f, v in evidence]}


def test_the_split_holds_out_9_claims_including_one_trap_and_one_control():
    dev, held_out = load_compliance_cases("dev"), load_compliance_cases("held_out")
    assert (len(dev), len(held_out), len(load_compliance_cases("all"))) == (18, 9, 27)
    assert sum(c.expected["expected_overall"] == "COMPLIANT" for c in held_out) == 2
    # Every kind of breach is still seen in development.
    kinds = {f["check"] for c in dev for f in c.expected["required_findings"]}
    assert kinds == {f["check"] for c in load_compliance_cases("all")
                     for f in c.expected["required_findings"]}


def test_facts_come_from_the_derived_view_with_blanks_as_none(warehouse):
    facts = load_facts(warehouse, "gc-010")
    assert facts["claim_id"] == "GC-010" and facts["incident_date"] == "2026-02-10"
    assert facts["licence_status"] == "EXPIRED" and facts["licence_expired_days"] == 18
    assert facts["bac_reading"] is None and facts["catastrophe_event_id"] is None
    assert as_of_dates(facts) == (date(2026, 2, 10), date(2026, 2, 20))
    json.dumps(facts)  # plain values only
    with pytest.raises(ComplianceError, match="GC-001 to GC-027"):
        load_facts(warehouse, "GC-999")


def test_findings_are_checked_against_the_facts_and_the_supplied_clauses(warehouse):
    facts = load_facts(warehouse, "GC-010")
    supplied = {"POL-MTR-002:3.4": "5.3"}
    assert validate(finding(), facts, supplied) == []
    assert validate(finding(evidence=[("licence_expired_days", "18"), ("bac_reading", "null"),
                                      ("total_loss", "false")]), facts, supplied) == []
    problems = validate(finding(clause_ids=["POL-AUT-003:4.3"],
                                evidence=[("licence_status", "VALID"), ("made_up", "1")]),
                        facts, supplied)
    assert len(problems) == 3 and "wasn't given" in problems[0]
    assert validate(finding(severity="NONE", clause_ids=[]), facts, supplied) == [
        "a BREACH finding must cite a clause", "a BREACH finding must have a severity"]
    # NOT_ASSESSED must point at a field that really is blank.
    assert validate(finding(status="NOT_ASSESSED", severity="NONE",
                            evidence=[("bac_reading", "null")]), facts, supplied) == []
    assert validate(finding(status="NOT_ASSESSED", severity="NONE"), facts, supplied)
    # A fact the claim file doesn't hold at all: no evidence, named in the rule.
    assert validate(finding(status="NOT_ASSESSED", severity="NONE", evidence=[]), facts,
                    supplied) == []


def test_the_verdict_is_aggregated_in_code():
    assert aggregate([finding(status="PASS"), finding()]) == "NON_COMPLIANT"
    assert aggregate([finding(status="PASS"), finding(status="NEEDS_REVIEW")]) == "NEEDS_REVIEW"
    assert aggregate([finding(status="PASS"), finding(status="NOT_ASSESSED")]) == "COMPLIANT"


def test_the_grader_scores_the_expected_verdicts_fully_and_an_empty_review_not_at_all():
    cases = load_compliance_cases("all")
    right = [grade(c, reference_review(c)) for c in cases]
    totals = summarise(right)
    assert (totals["overall_correct"], totals["required_detected"]) == (27, 22)
    assert (totals["false_breaches"], totals["traps_and_controls_right"]) == (0, 7)
    empty = summarise([grade(c, {"overall": None, "findings": []}) for c in cases])
    assert (empty["overall_correct"], empty["required_detected"]) == (0, 0)
    errored = grade(cases[1], {"overall": None, "findings": [], "error": "APIError: down"})
    assert errored["misses"] == [] and not errored["overall_correct"]


def test_matching_is_by_clause_and_version_with_a_diagnosis_for_each_miss():
    case = next(c for c in load_compliance_cases("all") if c.claim_id == "GC-010")
    cited = finding(check="cover")  # the check name doesn't matter, the clause does
    v53 = {**cited, "clauses": [{"clause_id": "POL-MTR-002:3.4", "version": "5.3"}]}
    v60 = {**cited, "clauses": [{"clause_id": "POL-MTR-002:3.4", "version": "6.0"}]}
    got = grade(case, {"overall": "NON_COMPLIANT", "findings": [v53]})
    assert (got["detected"], got["strict_citations"], got["check_name_agrees"]) == (1, 1, 0)
    # The superseded version governs this incident, so v6.0 doesn't count.
    got = grade(case, {"overall": "NON_COMPLIANT", "findings": [v60],
                       "retrieved": {"all": ["POL-MTR-002@6.0:3.4"]}})
    assert got["detected"] == 0 and got["false_breaches"] == 1
    assert got["misses"][0]["diagnosis"] == "wrong_version"
    got = grade(case, {"overall": "COMPLIANT", "findings": [],
                       "retrieved": {"all": ["POL-CLM-001@4.2:2.2"]}})
    assert got["misses"][0]["diagnosis"] == "retrieval_miss"
    got = grade(case, {"overall": "COMPLIANT", "findings": [],
                       "retrieved": {"all": ["POL-MTR-002@5.3:3.4"]}})
    assert got["misses"][0]["diagnosis"] == "judge_error"
    invented = {**cited, "clauses": [{"clause_id": "POL-XYZ-999:1.1", "version": None}]}
    got = grade(case, {"overall": "NON_COMPLIANT", "findings": [invented]}, {"POL-MTR-002:3.4"})
    assert (got["invented_citations"], got["unsupplied_citations"]) == (1, 1)


def test_a_v0_review_makes_one_judge_call_and_records_versions_and_problems(
        warehouse, policy_kb, ledger):
    library = _policy_library(str(policy_kb))
    facts = load_facts(warehouse, "GC-010")
    coverage, procedure = as_of_dates(facts)
    retrieved = library.search("expired licence exclusion", coverage, procedure, k=8)
    clause = retrieved[0].clause
    verdict = {"findings": [finding(clause_ids=[clause.clause_id]),
                            finding(check="cover", status="PASS", severity="NONE",
                                    clause_ids=["POL-NOT-000:1.1"], evidence=[])]}
    fake = FakeClaude(reply({"type": "text", "text": json.dumps(verdict)}))
    # The naive query is the whole fact list, so patch search to return known clauses.
    library_search = library.search
    library.search = lambda *a, **k: retrieved
    try:
        result = review_claim("GC-010", library, fake, ReviewConfig(warehouse), "v0", "run-1")
    finally:
        library.search = library_search
    assert result["error"] is None and result["overall"] == "NON_COMPLIANT"
    assert result["findings"][0]["clauses"] == [{"clause_id": clause.clause_id,
                                                 "version": clause.version}]
    assert result["validation"] == [{"finding": 1, "problems": [
        "cites clauses it wasn't given: POL-NOT-000:1.1"]}]
    assert len(result["retrieved"]["all"]) == len(retrieved) and result["cost_usd"] > 0
    request = fake.requests[0]
    assert request["output_config"]["format"] == VERDICT_FORMAT and "tools" not in request
    blocks = request["messages"][0]["content"]
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}  # facts, shared by a claim's calls
    message = "".join(b["text"] for b in blocks)
    assert "<claim_facts>" in message and all(f"- {name}:" in message for name in CHECKS)
    assert f'id="{clause.clause_id}" version="{clause.version}"' in message
    assert json.loads((costs.LEDGER).read_text().splitlines()[0])["run_id"] == "run-1"


def test_a_review_that_cant_run_says_why(warehouse, policy_kb, ledger):
    library = _policy_library(str(policy_kb))
    result = review_claim("GC-999", library, FakeClaude(), ReviewConfig(warehouse))
    assert result["overall"] is None and "GC-999" in result["error"]
    cut_off = FakeClaude(reply({"type": "text", "text": "{"}, stop_reason="max_tokens"))
    result = review_claim("GC-001", library, cut_off, ReviewConfig(warehouse))
    assert "stopped early" in result["error"] and result["cost_usd"] > 0


def test_the_agent_can_review_a_claim_and_the_judge_cost_counts_toward_the_question(
        warehouse, tmp_path, ledger):
    from agent.graph import AgentConfig, Session
    from tests.fakes import report

    verdict = {"findings": [finding(check=name, status="PASS", severity="NONE", clause_ids=[],
                                    evidence=[]) for name in CHECKS]}
    fake = FakeClaude(
        reply({"type": "tool_use", "id": "tu_1", "name": "check_claim_compliance",
               "input": {"claim_id": "GC-001"}}, stop_reason="tool_use"),
        reply({"type": "text", "text": json.dumps(verdict)}),  # the judge
        reply(report(answer_sql=None)),
    )
    assert AgentConfig().compliance_variant == "full"  # the agent's default since B7
    # v0 here, so one scripted judge call stands in for the review.
    config = AgentConfig(warehouse=warehouse, transport="inprocess", compliance_variant="v0")
    with Session("claims_ops_manager", config=config, client=fake, trace_dir=tmp_path) as chat:
        answer = chat.ask("Was GC-001 handled correctly?")
    assert answer.error is None and len(answer.model_calls) == 3
    assert answer.cost_usd == pytest.approx(sum(c["cost_usd"] for c in answer.model_calls))
    call = answer.tool_calls[0]
    assert call["tool"] == "check_claim_compliance" and "model_calls" not in call
    assert call["compliance"]["overall"] == "COMPLIANT"
    result = json.loads(fake.requests[2]["messages"][-1]["content"][0]["content"])
    assert result["overall"] == "COMPLIANT" and len(result["findings"]) == 10
    # The judge's call is labelled with the question's run, like the agent's own.
    runs = {json.loads(line)["run_id"] for line in costs.LEDGER.read_text().splitlines()}
    assert runs == {answer.run_id}


def test_v1_queries_are_triggered_by_the_facts_and_kept_to_each_checks_documents(
        warehouse, policy_kb):
    facts = load_facts(warehouse, "GC-010")
    exclusions = sub_queries("exclusions", facts)
    assert any("EXPIRED licence 18 days" in q for q in exclusions)
    assert any("setting aside exclusion POL-MTR-002:3.4" in q for q in exclusions)
    assert sub_queries("notification", facts) == []  # notified the next day
    library = _policy_library(str(policy_kb))
    coverage, procedure = as_of_dates(facts)
    clauses, queries = retrieve_for_check(library, "documentation", facts, coverage, procedure)
    assert queries[0] == "documents required before a accept decision on a collision claim"
    assert "POL-DOC-005:A" in {c.clause_id for c in clauses}
    clauses, _ = retrieve_for_check(library, "fraud", facts, coverage, procedure)
    # Top 6 within the check's documents, plus cross-references (which may be elsewhere).
    assert all(c.doc_id == "POL-FRD-004" for c in clauses[:6]) and len(clauses) <= 10
    clauses, _ = retrieve_for_check(library, "exclusions", facts, coverage, procedure)
    assert {c.version for c in clauses if c.doc_id == "POL-MTR-002"} == {"5.3"}  # in force


class AreaJudge:
    """A fake judge that answers by the area it's asked about, since v1's calls run in
    parallel and arrive in any order. `bad` areas cite a clause they weren't given."""

    def __init__(self, breach: str | None = None, bad: tuple = (), bad_twice: tuple = ()):
        self.breach, self.bad, self.bad_twice = breach, set(bad), set(bad_twice)
        self.requests: list[dict] = []
        self.beta = self.messages = self

    def create(self, **params):
        self.requests.append(params)  # list.append is thread-safe
        text = params["messages"][0]["content"][1]["text"]
        area = text.split("\n- ")[1].split(":")[0]
        given = text.split('<clause id="')[1].split('"')[0]
        retry = len(params["messages"]) > 1
        cited = given
        if area in self.bad_twice or (area in self.bad and not retry):
            cited = "POL-XYZ-999:1.1"
        status = "BREACH" if area == self.breach else "PASS"
        verdict = {"findings": [finding(check=area, status=status,
                                        severity="HIGH" if status == "BREACH" else "NONE",
                                        clause_ids=[cited], evidence=[])]}
        return reply({"type": "text", "text": json.dumps(verdict)})


def test_a_v1_review_judges_each_check_separately_and_retries_invalid_findings(
        warehouse, policy_kb, ledger):
    library = _policy_library(str(policy_kb))
    fake = AreaJudge(breach="exclusions", bad=("fraud",), bad_twice=("settlement",))
    result = review_claim("GC-010", library, fake, ReviewConfig(warehouse), "v1", "run-v1")
    assert result["error"] is None and result["overall"] == "NON_COMPLIANT"
    # Ten checks, one retry each for fraud and settlement.
    assert len(fake.requests) == len(result["model_calls"]) == 12
    first = fake.requests[0]["messages"][0]["content"][1]["text"]
    assert "- cover:" in first  # the first check runs alone, to write the cache
    assert set(result["retrieved"]) == set(CHECKS) and all(result["queries"].values())
    by_check = {f["check"]: f for f in result["findings"]}
    assert by_check["fraud"]["status"] == "PASS" and "validation_failed" not in by_check["fraud"]
    assert by_check["settlement"]["status"] == "NEEDS_REVIEW"
    assert by_check["settlement"]["validation_failed"] is True
    assert [v["check"] for v in result["validation"]] == ["settlement"]
    assert by_check["exclusions"]["clauses"][0]["version"]  # versions attached
    assert {json.loads(line)["check"] for line in costs.LEDGER.read_text().splitlines()} == \
        set(CHECKS)


def batch_sender(judge, fail: tuple = ()):
    """A stand-in for the Batch API: answers each request with the fake judge, except the
    custom IDs in fail, and records the batches it was sent."""
    sent: list[list[dict]] = []

    def send(client, requests):
        sent.append(requests)
        replies = {r["custom_id"]: ("batch request errored" if r["custom_id"] in fail
                                    else judge.create(**r["params"])) for r in requests}
        return f"batch-{len(sent)}", replies

    send.sent = sent
    return send


def test_a_v1_batch_review_matches_the_live_rules_at_half_price(warehouse, policy_kb, ledger):
    library = _policy_library(str(policy_kb))
    fake = AreaJudge(breach="exclusions", bad=("fraud",), bad_twice=("settlement",))
    send = batch_sender(fake)
    results = review_claims_batch(["GC-010", "gc-001"], library, None, ReviewConfig(warehouse),
                                  "v1", {"GC-010": "run-a"}, send=send)
    assert [r["claim_id"] for r in results] == ["GC-010", "GC-001"]
    # Round 1: 10 checks x 2 claims; round 2: the retries (fraud and settlement, each claim).
    assert [len(b) for b in send.sent] == [20, 4]
    assert send.sent[1][0]["custom_id"] == "GC-010-fraud-2"
    params = send.sent[0][0]["params"]
    assert not {"betas", "fallbacks", "cache_control"} & set(params)  # batch-safe, prefix cache
    assert params["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    first = results[0]
    assert first["error"] is None and first["overall"] == "NON_COMPLIANT"
    assert first["seconds"] is None and first["batch_ids"] == ["batch-1", "batch-2"]
    by_check = {f["check"]: f for f in first["findings"]}
    assert by_check["fraud"]["status"] == "PASS"
    assert by_check["settlement"]["status"] == "NEEDS_REVIEW"
    assert [v["check"] for v in first["validation"]] == ["settlement"]
    assert [f["check"] for f in first["findings"]] == list(CHECKS)  # checklist order
    # The fake reports the same for every claim: GC-001 too has the breach and the failed check.
    assert results[1]["overall"] == "NON_COMPLIANT"
    assert {f["check"]: f["status"] for f in results[1]["findings"]}["settlement"] == "NEEDS_REVIEW"
    assert results[1]["run_id"] == "c-gc-001"
    live_cost = 0.0013  # 100 input + 50 output + 3000 cache-read tokens at Sonnet 5.5 prices
    assert first["model_calls"][0]["cost_usd"] == pytest.approx(live_cost / 2)
    assert first["cost_usd"] == pytest.approx(12 * live_cost / 2)


def test_a_batch_review_with_a_failed_request_or_unknown_claim_says_why(
        warehouse, policy_kb, ledger):
    library = _policy_library(str(policy_kb))
    send = batch_sender(AreaJudge(), fail=("GC-002-triage-1",))
    results = review_claims_batch(["GC-001", "GC-002", "GC-999"], library, None,
                                  ReviewConfig(warehouse), "v1", send=send)
    assert results[0]["error"] is None and results[0]["overall"] == "COMPLIANT"
    assert results[1]["overall"] is None and "triage: batch request errored" in results[1]["error"]
    assert results[1]["cost_usd"] > 0  # the other nine replies were still paid for
    assert results[2]["error"].startswith("ComplianceError: No claim file 'GC-999'")
    v0 = review_claims_batch(["GC-001"], library, None, ReviewConfig(warehouse), "v0",
                             send=batch_sender(AreaJudge()))
    assert v0[0]["error"] is None and list(v0[0]["retrieved"]) == ["all"]


def test_full_context_gives_the_judge_the_whole_library_and_checks_versions_by_date(
        warehouse, policy_kb, ledger):
    library = _policy_library(str(policy_kb))
    verdict = {"findings": [finding(clause_ids=["POL-MTR-002:3.4"]),
                            finding(check="cover", status="PASS", severity="NONE",
                                    clause_ids=["POL-NOT-000:1.1"], evidence=[])]}
    fake = FakeClaude(reply({"type": "text", "text": json.dumps(verdict)}))
    result = review_claim("GC-010", library, fake, ReviewConfig(warehouse), "full", "run-f")
    assert result["error"] is None and result["overall"] == "NON_COMPLIANT"
    library_block, rest = fake.requests[0]["messages"][0]["content"]
    assert library_block["cache_control"] == {"type": "ephemeral"}  # shared by every claim
    assert 'id="POL-MTR-002:3.4" version="5.3"' in library_block["text"]
    assert 'id="POL-MTR-002:3.4" version="6.0"' in library_block["text"]  # both versions
    assert "<claim_facts>" in rest["text"] and "superseded versions" in rest["text"]
    # The incident was in February 2026, so the citation is to the version then in force.
    assert result["findings"][0]["clauses"] == [{"clause_id": "POL-MTR-002:3.4",
                                                 "version": "5.3"}]
    assert result["validation"] == [{"finding": 1, "problems": [
        "cites clauses it wasn't given: POL-NOT-000:1.1"]}]
