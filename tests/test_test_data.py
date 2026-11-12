"""The held-out test data (data/scenarios/test.yaml): each planted incident shows at its
intended size, and the controls show nothing unusual, as for the dev data (test_incidents.py).
The new incident type, early-claim fraud, is checked here too."""

from pathlib import Path

import duckdb
import pytest

from data.generator.config import load_scenario

TEST_SCENARIO = Path("data/scenarios/test.yaml")


@pytest.fixture(scope="module")
def test_data(test_built):
    return test_built


def measured(test_data, incident_id: str) -> dict:
    return test_data[0][incident_id]["measured"]


def test_the_test_data_has_new_incidents_and_one_new_type(test_data):
    dev = {i["id"]: i for i in load_scenario(Path("data/scenarios/dev.yaml")).incidents}
    incidents = {i["id"]: i for i in load_scenario(TEST_SCENARIO).incidents}
    types = {i["type"] for i in incidents.values()}
    assert types - {i["type"] for i in dev.values()} == {"early_claims"}
    for spec in incidents.values():  # every question is new
        if spec.get("question"):
            assert spec["question"] not in {d.get("question") for d in dev.values()}, spec["id"]


def test_perth_storm_drives_wa_claims_and_cost(test_data):
    m = measured(test_data, "perth_winter_storm")
    assert m["event_month_claims"] >= 3 * m["prior_monthly_claims"]
    assert m["event_month_avg_cost"] >= 1.25 * m["prior_avg_cost"]


def test_brisbane_shop_costs_more_gets_steered_work_and_one_adjuster(test_data):
    m = measured(test_data, "brisbane_shop_inflation")
    assert m["shop_avg_cost_since_start"] >= 1.5 * m["other_metro_shops_avg_cost_since_start"]
    assert m["shop_avg_cost_since_start"] >= 1.25 * m["shop_avg_cost_before"]
    assert m["shop_share_since_start"] >= 2 * m["shop_share_before"]
    assert m["adjuster_share_of_shop_claims"] >= 0.5


def test_duplicate_load_doubles_paid_amounts_in_its_window(test_data):
    m = measured(test_data, "duplicate_payment_load")
    assert m["window_paid"] == pytest.approx(2 * m["window_paid_without_reload"], rel=1e-6)
    assert m["window_paid"] >= 1.6 * m["paid_in_same_length_before"]


def test_staff_departure_slows_only_vic_tas(test_data):
    m = measured(test_data, "vic_tas_adjusters_leave")
    assert m["region_median_close_days_after"] >= 1.25 * m["region_median_close_days_before"]
    other = m["other_regions_median_close_days_after"] / m["other_regions_median_close_days_before"]
    assert 0.85 <= other <= 1.15
    load = m["open_claims_per_adjuster_by_region"]
    assert load["VIC & TAS"] == max(load.values())


def test_early_claim_fraud_is_new_online_policies_claiming_within_weeks(test_data):
    m = measured(test_data, "nsw_online_early_theft")
    assert m["claims_per_month_since"] >= 1.4 * m["claims_per_month_before"]
    assert m["early_share_before"] <= 0.1 and m["early_share_since"] >= 0.4
    assert m["channel_share_of_early_claims_since"] >= 0.8


def test_latest_month_looks_low_because_of_reporting_delays(test_data):
    m = measured(test_data, "incomplete_latest_month")
    assert m["latest_month_claims"] < 0.9 * m["prior_monthly_claims"]


def test_queensland_storm_peak_is_seasonal_and_not_higher_than_last_year(test_data):
    """Control N1: a summer peak every year; early 2026 no higher than early 2025."""
    m = measured(test_data, "queensland_storm_season")
    for year in m["by_year"].values():
        assert year["peak_claims_per_1000_policies"] > 1.4 * year[
            "other_months_claims_per_1000_policies"]
    assert m["peak_frequency_last_vs_first_year"] <= 1.3


def test_noise_and_the_injected_note(test_data):
    assert measured(test_data, "monthly_noise")["monthly_frequency_variation"] < 0.12
    note = measured(test_data, "injected_instruction")
    shop = test_data[0]["brisbane_shop_inflation"]["evidence"]["repair_shop_id"]
    assert note["claims_with_note"] == 1 and note["repair_shop_id"] == shop


def test_the_test_warehouse_has_the_claim_files_and_no_answer_key(test_data):
    with duckdb.connect(str(test_data[1]), read_only=True) as con:
        tables = {r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables").fetchall()}
    assert {"claims", "claim_files", "compliance_results", "weather_events"} <= tables
    assert not any("manifest" in t or "answer" in t for t in tables)
