"""Recorded compliance verdicts (data/compliance/results.py): from an eval run's reviews to
the warehouse's compliance_results and compliance_findings. No API calls."""

import json

import duckdb

from data.compliance.build import load_review_results
from data.compliance.results import rows_from_run


def write_review(folder, claim_id, overall, findings, error=None, repeat=1):
    review = {"claim_id": claim_id, "overall": overall, "error": error, "variant": "v1",
              "run_id": f"c-{claim_id.lower()}", "policy_versions": ["POL-AUT-003@3.1"],
              "model_calls": [{"model_served": "claude-sonnet-5-5"}], "findings": findings}
    (folder / f"{claim_id}-r{repeat}.json").write_text(json.dumps({"review": review}))


def finding(check, status, severity="NONE", clauses=()):
    return {"check": check, "status": status, "severity": severity, "rule": "r",
            "clauses": [{"clause_id": c, "version": "3.1"} for c in clauses]}


def test_verdicts_go_from_a_run_into_queryable_tables(tmp_path):
    reviews = tmp_path / "run" / "reviews"
    reviews.mkdir(parents=True)
    write_review(reviews, "GC-004", "NON_COMPLIANT",
                 [finding("authority", "BREACH", "HIGH", ["POL-AUT-003:2.1"]),
                  finding("cover", "PASS")])
    write_review(reviews, "GC-005", "NON_COMPLIANT",
                 [finding("authority", "BREACH", "HIGH", ["POL-AUT-003:2.2"])])
    write_review(reviews, "GC-019", "COMPLIANT", [finding("authority", "PASS")])
    write_review(reviews, "GC-020", None, [], error="APIError: down")  # left out
    write_review(reviews, "GC-021", "COMPLIANT", [], repeat=2)  # only repeat 1 counts
    rows = rows_from_run(tmp_path / "run")
    assert [r["claim_id"] for r in rows] == ["GC-004", "GC-005", "GC-019"]
    path = tmp_path / "review_results.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    con = duckdb.connect()
    con.execute("CREATE TABLE compliance_results (x INT)")  # replaced, so it can be rerun
    assert load_review_results(con, path) == 3
    breach_types = con.execute("""
        SELECT check_area, count(*) FROM compliance_findings WHERE status = 'BREACH'
        GROUP BY ALL""").fetchall()
    assert breach_types == [("authority", 2)]
    assert con.execute("SELECT clauses FROM compliance_findings WHERE claim_id = 'GC-004' "
                       "AND status = 'BREACH'").fetchone() == ("POL-AUT-003:2.1 v3.1",)
    assert con.execute("SELECT overall, breaches, policy_versions FROM compliance_results "
                       "WHERE claim_id = 'GC-019'").fetchone() == ("COMPLIANT", 0,
                                                                  "POL-AUT-003 v3.1")
    assert load_review_results(con, tmp_path / "none.jsonl") == 0  # no file: empty tables
    assert con.execute("SELECT count(*) FROM compliance_results").fetchone() == (0,)
