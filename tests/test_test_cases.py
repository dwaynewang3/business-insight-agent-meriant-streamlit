"""The test data's question set (evals/cases/test/): the grader accepts every reference answer on
the test warehouse and rejects a slightly wrong one, and every "why" case points at the test
data's answer key. No API calls."""

from pathlib import Path

import pytest

from evals.cases import load_what_cases, load_why_cases
from evals.graders import WhatGrader
from evals.run_evals import SUITES, select_cases

TEST_CASES = Path("evals/cases/test")
WHAT = {case.id: case for case in load_what_cases(TEST_CASES / "what.yaml")}
WHY = load_why_cases(TEST_CASES / "why.yaml")


@pytest.fixture(scope="module")
def grader(test_built):
    return WhatGrader(test_built[1])


def test_the_question_set_reuses_every_dev_template_once():
    dev_templates = {case.template for case in load_what_cases()}
    assert sorted(case.template for case in WHAT.values()) == sorted(dev_templates)
    assert len(WHY) == 7 and [c.kind for c in WHY].count("control") == 1


@pytest.mark.parametrize("case", WHAT.values(), ids=list(WHAT))
def test_every_reference_answer_passes_and_a_wrong_one_fails(grader, case):
    for sql in case.reference_sql:
        grade = grader.grade(case, {"status": "answered", "answer_sql": sql})
        assert grade.passed, grade.reason
    value = next(iter(case.values))
    wrong = (f"WITH ref AS ({case.reference_sql[0]}) "
             f"SELECT * REPLACE ({value} + abs({value}) * 0.1 + 0.01 AS {value}) FROM ref")
    assert not grader.grade(case, {"status": "answered", "answer_sql": wrong}).passed


def test_paid_amounts_in_may_accept_answers_with_or_without_the_duplicate_load():
    case = WHAT["what-paid-amount-total-2026-05"]
    assert len(case.reference_sql) == 2 and "reload-2026-05-16" in case.reference_sql[1]


def test_every_why_case_points_at_the_test_answer_key(test_built):
    incidents = test_built[0]
    for case in WHY:
        assert case.answer_key in incidents, case.id
        assert incidents[case.answer_key]["question"] == case.question, case.id


def test_the_runner_picks_the_test_suites_cases_and_warehouse():
    assert SUITES["test"] == (Path(__file__).parent.parent / "evals" / "cases" / "test",
                              Path("data/test.duckdb"))
    assert [c.id for c in select_cases(None, None, "why", "test")] == [c.id for c in WHY]
    with pytest.raises(SystemExit, match="no safety cases"):
        select_cases(None, None, "safety", "test")
