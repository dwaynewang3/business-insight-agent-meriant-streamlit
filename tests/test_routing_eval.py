"""The routing eval's grader (evals/routing_eval.py). No API calls."""

from evals.routing_eval import grade, load_questions


def test_every_question_passes_its_own_tools_and_fails_with_none():
    questions = load_questions()
    assert len(questions) == 16
    for q in questions:
        assert grade(q, q["required_tools"] + q["any_of_tools"][:1])["passed"], q["qid"]
        assert q["qid"] == "T-15" or not grade(q, [])["passed"], q["qid"]


def test_an_agreed_metric_counts_as_the_data_route_both_ways():
    by_id = {q["qid"]: q for q in load_questions()}
    assert grade(by_id["T-01"], ["query_metric"])["passed"]
    assert not grade(by_id["T-02"], ["search_policies", "query_metric"])["passed"]
    result = grade(by_id["T-04"], ["run_sql", "check_claim_compliance"])
    assert result["reason"] == ("didn't call search_policies; "
                                "called forbidden check_claim_compliance")
