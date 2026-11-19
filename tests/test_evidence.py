"""Key numbers: matching a written number to its query result, and the eval runner's check
that each finding's numbers come from its own SQL."""

import pytest

from agent.key_numbers import is_rounded, matches, source_value, step
from evals.graders.evidence import NumberChecker


@pytest.fixture(scope="module")
def checker(guarded_warehouse):
    return NumberChecker(guarded_warehouse)


def finding(sql: str, *numbers: tuple[float, str]) -> dict:
    return {"claim": "c", "evidence_sql": sql, "confidence": "high",
            "key_numbers": [{"label": f"number {i}", "value": value, "unit": unit}
                            for i, (value, unit) in enumerate(numbers)]}


@pytest.mark.parametrize("value, expected", [
    (53.6, 0.1), (159, 1), (0.5551, 0.0001), (1_200_000, 100_000), (1000, 100), (50, 1), (-4, 1),
])
def test_the_rounding_step_follows_how_the_number_is_written(value, expected):
    assert step(value) == pytest.approx(expected)


@pytest.mark.parametrize("value, cell, unit", [
    (53.6, 53.62, "%"),  # rounded
    (53.6, 0.5362, "%"),  # a fraction written as a percentage
    (0.536, 53.6, "ratio"),  # a percentage written as a fraction
    (1_200_000, 1_234_567, "AUD"),
    (12.3, 0.0123, "claims per 1,000 policies"),
    (12, -12.0, "%"),  # a fall written without its sign
    (4812, 4812.37, "AUD"),
])
def test_fair_ways_of_writing_a_number_match(value, cell, unit):
    assert matches(value, cell, unit)


@pytest.mark.parametrize("value, cell, unit", [
    (53.6, 54.2, "%"),
    (1000, 1400, "claims"),  # trailing zeros don't stretch to one significant figure
    (12.3, 0.0123, "claims"),  # a rate per 1,000 only when the unit says so
    (231, 311, "claims"),
])
def test_different_numbers_dont_match(value, cell, unit):
    assert not matches(value, cell, unit)


def test_numbers_from_the_findings_own_sql_are_confirmed(checker, dev):
    claims = dev.execute("SELECT count(*) FROM claims").fetchone()[0]
    result = checker.check({"findings": [
        finding("SELECT count(*) AS claims FROM claims", (claims, "claims"))]})
    assert result == {"checked": 1, "confirmed": 1, "unconfirmed": []}


def test_a_column_total_counts_but_a_number_from_elsewhere_doesnt(checker, dev):
    by_product = dict(dev.execute("SELECT product, count(*) FROM claims GROUP BY 1").fetchall())
    total = sum(by_product.values())
    sql = "SELECT product, count(*) AS claims FROM claims GROUP BY 1"
    result = checker.check({"findings": [finding(
        sql, (by_product["motor"], "claims"), (total, "claims"), (total + 500, "claims"))]})
    assert (result["checked"], result["confirmed"]) == (3, 2)
    assert result["unconfirmed"] == [{"finding": 0, "label": "number 2", "value": total + 500,
                                      "unit": "claims",
                                      "reason": "Not in the result of its finding's SQL."}]


def test_a_finding_whose_sql_fails_or_is_missing_confirms_nothing(checker):
    result = checker.check({"findings": [
        finding("DELETE FROM claims", (1, "claims")),
        finding("", (2, "claims")),
        finding("SELECT 1 AS x"),  # no key numbers, nothing to check
    ]})
    assert (result["checked"], result["confirmed"]) == (2, 0)
    assert result["unconfirmed"][0]["reason"].startswith("Its SQL failed")
    assert result["unconfirmed"][1]["reason"] == "The finding has no SQL."


def test_a_missing_report_has_nothing_to_check(checker):
    assert checker.check(None) == {"checked": 0, "confirmed": 0, "unconfirmed": []}


def test_the_exact_value_behind_a_rounded_number_is_found_in_its_scale():
    result = (["product", "loss_ratio", "claims"],
              [("motor", 0.536245, 1287), ("home", 0.597917, 783)])

    def exact(value, unit, column=None, row=()):
        number = {"value": value, "unit": unit}
        if column:
            number |= {"column": column, "row": "; ".join(f"{c} = {v}" for c, v in row)}
        return source_value(number, result)

    assert exact(53.6, "%", "loss_ratio", [("product", "motor")]) == pytest.approx(53.6245)
    assert exact(2070, "claims", "claims") == 2070  # a column total
    assert exact(1287, "claims", "claims", [("product", "motor")]) == 1287
    assert exact(783, "claims", "claims", [("product", "motor")]) is None  # home's count
    assert exact(77.7, "%", "loss_ratio") is None
    assert exact("n/a", "%") is None
    # Reports from before numbers named their cell: anywhere in the result.
    assert exact(53.6, "%") == pytest.approx(53.6245) and exact(783, "claims") == 783
    assert is_rounded(53.6, 53.6245) and not is_rounded(1287, 1287.0)


def bound(value: float, unit: str, column: str, **row: str) -> dict:
    return {"label": "n", "value": value, "unit": unit, "column": column,
            "row": "; ".join(f"{c} = {v}" for c, v in row.items())}


BY_CHANNEL = (["channel", "month", "claims"],
              [("broker", "2026-01-01", 300), ("broker", "2026-02-01", 338),
               ("direct", "2026-01-01", 230), ("direct", "2026-02-01", 250)])


@pytest.mark.parametrize("number, confirmed", [
    (bound(300, "claims", "claims", channel="broker", month="2026-01"), True),  # month given
    (bound(338, "claims", "CLAIMS", channel="Broker", month="2026-02-01"), True),  # any case
    (bound(230, "claims", "claims", channel="broker", month="2026-01"), False),  # direct's
    (bound(638, "claims", "claims", channel="broker"), True),  # the rows it picks: total
    (bound(319, "claims", "claims", channel="broker"), True),  # ... or average
    (bound(1118, "claims", "claims"), True),  # no row: the column's total
    (bound(480, "claims", "claims", channel="direct"), True),
    (bound(480, "claims", "claims", channel="broker"), False),  # direct's total on broker
])
def test_a_number_is_checked_against_the_cell_it_names(number, confirmed):
    from agent.key_numbers import cell_values

    cells, problem = cell_values(number, BY_CHANNEL)
    assert problem is None
    assert any(matches(number["value"], cell, number["unit"]) for cell in cells) == confirmed


@pytest.mark.parametrize("number, reason", [
    (bound(300, "claims", "count"), "Its column, 'count', isn't in the result"),
    (bound(300, "claims", "claims", region="NSW"), "Its row names a column, 'region'"),
    (bound(300, "claims", "claims", channel="online"), "No row in the result has channel = online"),
    (bound(300, "claims", "channel", channel="broker", month="2026-01"), "Its cell in 'channel'"),
    ({"value": 300, "unit": "claims", "column": "claims", "row": "broker, January"},
     "Its row, 'broker, January', isn't written as column = value pairs"),
])
def test_a_cell_that_cant_be_found_says_why(number, reason):
    from agent.key_numbers import cell_values

    cells, problem = cell_values(number, BY_CHANNEL)
    assert cells == [] and problem.startswith(reason)


def test_numbers_that_name_their_cell_are_checked_there(checker, dev):
    by_product = dict(dev.execute("SELECT product, count(*) FROM claims GROUP BY 1").fetchall())
    sql = "SELECT product, count(*) AS claims FROM claims GROUP BY 1"
    report = {"findings": [{"claim": "c", "evidence_sql": sql, "confidence": "high",
                            "key_numbers": [
                                bound(by_product["motor"], "claims", "claims", product="motor"),
                                bound(by_product["motor"], "claims", "claims", product="home")]}]}
    result = checker.check(report)
    assert (result["checked"], result["confirmed"]) == (2, 1)
    assert result["unconfirmed"][0]["reason"] == (
        "Not the value in its cell of its finding's SQL result.")


def test_citations_are_read_from_the_text_and_checked_against_tool_results():
    from agent.citations import check_citations, extract_citations

    calls = [{"tool": "search_policies", "clauses": [["POL-MTR-002:3.4", "6.0"],
                                                     ["POL-AUT-003:4.3", "3.1"]]},
             {"tool": "run_sql", "sql": "SELECT 1"}]
    report = {"answer": "Excluded (POL-MTR-002 §3.4, v6.0), and no override is allowed "
                        "(POL-AUT-003 §4.3). The old rule (POL-MTR-002 §3.4, v5.3) differed.",
              "findings": [{"claim": "Excess per POL-STL-007:3.4, v3.0."}], "hypotheses": []}
    cited = extract_citations(report)
    assert {(c["clause_id"], c["version"]) for c in cited} == {
        ("POL-MTR-002:3.4", "6.0"), ("POL-AUT-003:4.3", None), ("POL-MTR-002:3.4", "5.3"),
        ("POL-STL-007:3.4", "3.0")}
    result = check_citations(report, calls)
    # 6.0 and the unversioned 4.3 were returned; v5.3 and STL-007 never were.
    assert (result["cited"], result["confirmed"], result["without_version"]) == (4, 2, 1)
    assert check_citations({"answer": "No policy here."}, calls)["cited"] == 0


def test_citation_lists_are_read_with_the_versions_that_follow_them():
    from agent.citations import citations_in

    text = ("Authority breaches cite POL-AUT-003 §2.1, §2.2 and §4.3 (v3.1). Exclusions "
            "breaches cite POL-MTR-002 §3.1 and §3.2 (v6.0) and §3.4 (v5.3), with "
            "POL-CLM-001 §7.2 (v4.2). See (POL-STL-007 §3.4(a), v3.0), POL-DOC-005:A and "
            "POL-DOC-005 Appendix A. POL-MTR-002 v5.3 governs; POL-AUT-003 sets AUD 50,000. "
            "Authority cites POL-AUT-003 v3.1 (§1.2, §2.3).")
    assert citations_in(text) == [
        ("POL-AUT-003:2.1", "3.1"), ("POL-AUT-003:2.2", "3.1"), ("POL-AUT-003:4.3", "3.1"),
        ("POL-MTR-002:3.1", "6.0"), ("POL-MTR-002:3.2", "6.0"), ("POL-MTR-002:3.4", "5.3"),
        ("POL-CLM-001:7.2", "4.2"), ("POL-STL-007:3.4", "3.0"), ("POL-DOC-005:A", None),
        ("POL-DOC-005:A", None), ("POL-AUT-003:1.2", "3.1"), ("POL-AUT-003:2.3", "3.1")]


def test_clauses_named_in_recorded_findings_count_as_returned():
    import json

    from agent.citations import check_citations
    from agent.tools import _summary

    rows = {"rows": [{"check_area": "authority", "clauses": "POL-AUT-003:2.1 v3.1; "
                      "POL-AUT-003:2.2 v3.1"}], "truncated": False}
    call = {"tool": "run_sql", **_summary("run_sql", {"sql": "SELECT ..."}, json.dumps(rows))}
    assert call["clauses"] == [["POL-AUT-003:2.1", "3.1"], ["POL-AUT-003:2.2", "3.1"]]
    report = {"answer": "Most breaches are authority (POL-AUT-003 §2.1 and §2.2, v3.1)."}
    assert check_citations(report, [call])["confirmed"] == 2
