"""The "what" grader passes every right answer and fails wrong or missing ones.

Before any paid eval run, the grader has to accept each case's own reference answers and
reject an empty answer and a slightly wrong one. These tests check that for every case, and
check the comparison rules from evals/cases/what.yaml one by one.
"""

import pytest

from evals.cases import load_what_cases, load_why_cases
from evals.graders import WhatGrader, WhyCodeGrader

CASES = {case.id: case for case in load_what_cases()}


@pytest.fixture(scope="module")
def grader(guarded_warehouse):
    return WhatGrader(guarded_warehouse)


def answered(sql: str | None) -> dict:
    return {"status": "answered", "answer_sql": sql}


def wrap(case_id: str, select: str, reference: int = 0) -> tuple:
    """A query over the case's reference result, as `ref`."""
    case = CASES[case_id]
    return case, answered(f"WITH ref AS ({case.reference_sql[reference]}) {select}")


@pytest.mark.parametrize("case", CASES.values(), ids=list(CASES))
def test_every_reference_answer_passes(grader, case):
    for sql in case.reference_sql:
        grade = grader.grade(case, answered(sql))
        assert grade.passed, grade.reason


@pytest.mark.parametrize("case", CASES.values(), ids=list(CASES))
def test_a_slightly_wrong_answer_fails(grader, case):
    value = next(iter(case.values))
    sql = (f"WITH ref AS ({case.reference_sql[0]}) "
           f"SELECT * REPLACE ({value} + abs({value}) * 0.1 + 0.01 AS {value}) FROM ref")
    grade = grader.grade(case, answered(sql))
    assert not grade.passed and grade.category == "wrong_result"


@pytest.mark.parametrize("report, error, category", [
    (None, "API error: overloaded", "error"),
    ({"status": "needs_clarification", "answer_sql": None}, None, "no_answer"),
    ({"status": "declined", "answer_sql": None}, None, "no_answer"),
    (answered(None), None, "no_answer"),
    (answered("  "), None, "no_answer"),
    (answered("SELECT no_such_column FROM claims"), None, "sql_error"),
    (answered("DELETE FROM claims"), None, "sql_error"),
    (answered("SELECT * FROM read_text('.env')"), None, "sql_error"),
])
def test_a_missing_answer_fails_with_its_own_category(grader, report, error, category):
    grade = grader.grade(CASES["what-claim-count-total-2025-q4"], report, error)
    assert not grade.passed and grade.category == category


PASSING = {
    "renamed and reordered columns": (
        "what-claim-frequency-by-state-motor-2026-q2",
        "SELECT claim_frequency AS freq, 'x' AS note, state AS st FROM ref"),
    "state names instead of codes": (
        "what-claim-frequency-by-state-motor-2026-q2",
        "SELECT n.name, ref.claim_frequency FROM ref JOIN (VALUES ('NSW', 'New South Wales'), "
        "('VIC', 'Victoria'), ('QLD', 'Queensland'), ('WA', 'Western Australia'), "
        "('SA', 'South Australia'), ('TAS', 'Tasmania'), ('ACT', 'Australian Capital Territory'), "
        "('NT', 'Northern Territory')) n(code, name) ON state = code"),
    "a ratio as a rounded percentage": (
        "what-loss-ratio-by-product-2025",
        "SELECT upper(product), round(100 * loss_ratio, 1) AS pct FROM ref"),
    "a single value with extra columns": (
        "what-average-claim-cost-motor-nsw-2026-q2",
        "SELECT 'motor' AS product, 42 AS claims, round(average_claim_cost, 2) FROM ref"),
    "months as year-month text": (
        "what-claim-count-by-month-nsw-2025",
        "SELECT strftime(month, '%Y-%m') AS m, claim_count FROM ref"),
    "months by name": (
        "what-claim-count-by-month-nsw-2025",
        "SELECT strftime(month, '%B %Y') AS m, claim_count FROM ref"),
    "adjuster names instead of IDs": (
        "what-open-claims-by-adjuster-west-south",
        "SELECT a.full_name, open_claims FROM ref JOIN adjusters a USING (adjuster_id)"),
    "rows with zero left out": (
        "what-open-claims-by-adjuster-west-south",
        "SELECT * FROM ref WHERE open_claims > 0"),
    "repair shop names instead of IDs": (
        "what-shop-average-claim-cost-melbourne-2025",
        "SELECT s.name, average_claim_cost FROM ref JOIN repair_shops s USING (repair_shop_id)"),
}

FAILING = {
    "a missing row": (
        "what-claim-frequency-by-state-motor-2026-q2",
        "SELECT * FROM ref WHERE state <> 'NSW'"),
    "an extra row": (
        "what-top-states-by-loss-ratio-3-home-2025",
        "SELECT * FROM ref UNION ALL SELECT 'ZZ', 0.5"),
    "duplicate rows": (
        "what-loss-ratio-by-product-2025",
        "SELECT * FROM ref UNION ALL SELECT * FROM ref"),
    "a breakdown instead of a single value": (
        "what-average-claim-cost-motor-nsw-2026-q2",
        "SELECT * FROM ref UNION ALL SELECT * FROM ref"),
    "the wrong unit": (
        "what-claim-frequency-by-state-motor-2026-q2",
        "SELECT state, claim_frequency / 3 FROM ref"),
}


@pytest.mark.parametrize("case_id, select", PASSING.values(), ids=list(PASSING))
def test_fair_variations_of_a_right_answer_pass(grader, case_id, select):
    grade = grader.grade(*wrap(case_id, select))
    assert grade.passed, grade.reason


@pytest.mark.parametrize("case_id, select", FAILING.values(), ids=list(FAILING))
def test_wrong_shapes_fail(grader, case_id, select):
    grade = grader.grade(*wrap(case_id, select))
    assert not grade.passed and grade.category == "wrong_result"


def test_either_reading_of_a_payment_question_passes(grader):
    case = CASES["what-paid-amount-total-2025"]
    assert len(case.reference_sql) == 2  # with and without the duplicate load
    for reference in range(2):
        grade = grader.grade(*wrap(case.id, "SELECT * FROM ref", reference))
        assert grade.passed, grade.reason


# "Why" code checks ------------------------------------------------------------------------

WHY = {case.id: case for case in load_why_cases()}


def why_report(text: str, issues: list | None = None) -> dict:
    return {"status": "answered", "answer": text, "findings": [], "hypotheses": [],
            "data_quality_issues": issues or []}


def test_a_why_answer_passes_when_it_names_the_key_evidence():
    case = WHY["why-nsw-cost-july-2026"]
    grade = WhyCodeGrader().grade(case, why_report("A severe East Coast Low (WX-003) hit Sydney."))
    assert grade.passed


def test_a_why_answer_fails_without_the_key_evidence():
    case = WHY["why-nsw-cost-july-2026"]
    grade = WhyCodeGrader().grade(case, why_report("Costs rose because of inflation in Sydney."))
    assert not grade.passed and grade.category == "missing_evidence"
    assert "WX-003" in grade.reason


def test_a_data_problem_must_be_flagged_where_the_case_needs_it():
    case = next(c for c in WHY.values() if c.flags_data_quality)
    terms = " ".join(group[0] for group in case.must_mention)
    assert WhyCodeGrader().grade(case, why_report(terms)).category == "missing_data_quality"
    issue = [{"issue": "Rows loaded twice", "impact": "Paid is overstated"}]
    assert WhyCodeGrader().grade(case, why_report(terms, issue)).passed


def test_cases_with_nothing_to_find_wait_for_the_llm_grader():
    case = next(c for c in WHY.values() if c.nothing_to_find)
    grade = WhyCodeGrader().grade(case, why_report("Nothing unusual."))
    assert grade.category == "unscored" and not grade.passed
    assert WhyCodeGrader().grade(case, None, "API error").category == "error"
