"""The stress data (data/scenarios/stress.yaml): every planted incident shows at its intended
size, the cost rise has no cause in the data, and every "why" case's premise holds."""

from pathlib import Path

import duckdb
import pytest

from data.generator import generate
from data.generator.config import load_scenario
from evals.cases import load_why_cases
from evals.run_evals import SUITES, select_cases

STRESS_CASES = Path("evals/cases/stress")
WHY = load_why_cases(STRESS_CASES / "why.yaml")


@pytest.fixture(scope="module")
def stress(tmp_path_factory):
    """The stress warehouse, open read-only, and its incidents by id."""
    path = tmp_path_factory.mktemp("stress_warehouse") / "stress.duckdb"
    manifest = generate(load_scenario(Path("data/scenarios/stress.yaml")), path)
    con = duckdb.connect(str(path), read_only=True)
    yield con, {i["id"]: i for i in manifest["incidents"]}
    con.close()


def test_the_hailstorm_and_the_duplicate_load_both_land_in_victorias_may_payments(stress):
    con, incidents = stress
    storm, duplicates = con.execute("""
        SELECT sum(amount) FILTER (WHERE c.loss_date BETWEEN DATE '2026-04-27'
                                   AND DATE '2026-04-28' AND c.cause = 'storm'
                                   AND p.load_batch <> 'reload-2026-05-23'),
               sum(amount) FILTER (WHERE p.load_batch = 'reload-2026-05-23')
        FROM claim_payments p JOIN claims c USING (claim_id)
        WHERE c.state = 'VIC' AND p.payment_date BETWEEN DATE '2026-05-01' AND DATE '2026-05-31'
    """).fetchone()
    # Each is a material part of the jump, so naming one isn't enough.
    assert storm > 1_000_000 and 500_000 < duplicates < storm
    assert incidents["melbourne_hailstorm"]["evidence"]["event_id"] == "WX-001"


def test_the_cost_rise_is_real_and_shows_evenly_with_nothing_else_changing(stress):
    con, incidents = stress
    measured = incidents["nsw_motor_cost_rise"]["measured"]
    assert measured["avg_cost"] > 1.3 * measured["avg_cost_year_before"]
    assert 0.9 < measured["other_states_avg_cost"] / measured[
        "other_states_avg_cost_year_before"] < 1.1
    assert 0.8 < measured["claims"] / measured["claims_year_before"] < 1.25
    # Every sales channel, and the main causes, rose: no one part of the book explains it.
    for dimension in ("p.channel", "c.cause"):
        ratios = con.execute(f"""
            WITH costs AS (
                SELECT {dimension} AS part, c.loss_date,
                       coalesce(sum(pay.amount), 0) + any_value(c.reserve_amount) AS incurred
                FROM claims c JOIN policies p USING (policy_id)
                LEFT JOIN claim_payments pay USING (claim_id)
                WHERE c.state = 'NSW' AND c.product = 'motor'
                GROUP BY c.claim_id, part, c.loss_date)
            SELECT part, avg(incurred) FILTER (WHERE loss_date BETWEEN DATE '2026-06-01'
                                                                   AND DATE '2026-08-31')
                         / avg(incurred) FILTER (WHERE loss_date BETWEEN DATE '2025-06-01'
                                                                     AND DATE '2025-08-31')
            FROM costs GROUP BY part
            HAVING count(*) FILTER (WHERE loss_date BETWEEN DATE '2026-06-01'
                                                        AND DATE '2026-08-31') >= 30
        """).fetchall()
        assert ratios and all(ratio > 1.15 for _, ratio in ratios), (dimension, ratios)
    # And nothing in the warehouse points at it: no weather event in New South Wales then.
    assert con.execute("""
        SELECT count(*) FROM weather_events
        WHERE state = 'NSW' AND start_date BETWEEN DATE '2026-05-01' AND DATE '2026-08-31'
    """).fetchone()[0] == 0


def test_the_new_hail_code_takes_half_of_storm_claims_and_the_total_holds(stress):
    _, incidents = stress
    measured = incidents["storm_hail_recode"]["measured"]
    assert measured["new_code_before"] == 0
    assert measured["old_code_claims"] < 0.6 * measured["old_code_claims_year_before"]
    assert 0.8 < measured["both_codes_claims"] / measured["old_code_claims_year_before"] < 1.25


@pytest.mark.parametrize("case", WHY, ids=[c.id for c in WHY])
def test_every_why_cases_premise_holds_in_the_stress_data(stress, case):
    con, incidents = stress
    assert case.answer_key in incidents
    assert con.execute(case.verify_sql).fetchone()[0] is True


def test_the_runner_picks_the_stress_suites_cases_and_warehouse():
    assert SUITES["stress"][1] == Path("data/stress.duckdb")
    assert [c.id for c in select_cases(None, None, "why", "stress")] == [c.id for c in WHY]
    assert {c.kind for c in WHY} == {"incident", "unexplained"}
    with pytest.raises(SystemExit, match="no what cases"):
        select_cases(None, None, "what", "stress")
