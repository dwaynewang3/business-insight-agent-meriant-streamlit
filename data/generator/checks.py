"""Measure how strongly each planted incident shows in the generated warehouse.

The numbers go into the answer key, and the tests use them to check that every incident
is visible at its intended size and that the controls show nothing unusual.
"""

from datetime import timedelta
from decimal import Decimal

import duckdb

from .config import Scenario
from .timeline import months_before, next_month

# Each claim's incurred cost: everything paid so far plus what's still reserved.
CLAIM_COSTS = """
    claim_costs AS (
        SELECT c.*, coalesce(p.paid, 0) + c.reserve_amount AS incurred
        FROM claims c
        LEFT JOIN (SELECT claim_id, sum(amount) AS paid FROM claim_payments GROUP BY claim_id) p
            USING (claim_id)
    )
"""


def _plain(value):
    if isinstance(value, (Decimal, float)):
        return round(float(value), 4)
    return value


def _row(con: duckdb.DuckDBPyConnection, sql: str, params: dict) -> dict:
    cursor = con.execute(sql, params)
    names = [column[0] for column in cursor.description]
    return {name: _plain(v) for name, v in zip(names, cursor.fetchone(), strict=True)}


def _weather_event(con, scenario: Scenario, spec: dict, evidence: dict) -> dict:
    month = spec["start_date"].replace(day=1)
    return _row(con, f"""
        WITH {CLAIM_COSTS}
        SELECT
            count(*) FILTER (WHERE loss_date >= $month AND loss_date < $after)
                AS event_month_claims,
            count(*) FILTER (WHERE loss_date >= $prior AND loss_date < $month) / 6.0
                AS prior_monthly_claims,
            avg(incurred) FILTER (WHERE loss_date >= $month AND loss_date < $after)
                AS event_month_avg_cost,
            avg(incurred) FILTER (WHERE loss_date >= $prior AND loss_date < $month)
                AS prior_avg_cost
        FROM claim_costs
        WHERE state = $state
    """, {
        "month": month,
        "after": next_month(month),
        "prior": months_before(month, 6),
        "state": spec["state"],
    })


def _shop_inflation(con, scenario: Scenario, spec: dict, evidence: dict) -> dict:
    return _row(con, f"""
        WITH {CLAIM_COSTS}
        SELECT
            avg(incurred) FILTER (WHERE repair_shop_id = $shop AND report_date >= $start)
                AS shop_avg_cost_since_start,
            avg(incurred) FILTER (WHERE repair_shop_id <> $shop AND report_date >= $start)
                AS other_metro_shops_avg_cost_since_start,
            avg(incurred) FILTER (WHERE repair_shop_id = $shop AND report_date < $start)
                AS shop_avg_cost_before,
            count(*) FILTER (WHERE repair_shop_id = $shop AND report_date < $start)::DOUBLE
                / count(*) FILTER (WHERE report_date < $start) AS shop_share_before,
            count(*) FILTER (WHERE repair_shop_id = $shop AND report_date >= $start)::DOUBLE
                / count(*) FILTER (WHERE report_date >= $start) AS shop_share_since_start,
            count(*) FILTER (WHERE repair_shop_id = $shop AND report_date >= $start
                             AND adjuster_id = $adjuster)::DOUBLE
                / count(*) FILTER (WHERE repair_shop_id = $shop AND report_date >= $start)
                AS adjuster_share_of_shop_claims
        FROM claim_costs
        WHERE repair_shop_id IN (
            SELECT repair_shop_id FROM repair_shops WHERE state = $state AND metro = $metro
        )
    """, {
        "shop": evidence["repair_shop_id"],
        "adjuster": evidence["adjuster_id"],
        "start": spec["start_date"],
        "state": spec["state"],
        "metro": spec["metro"],
    })


def _duplicate_payments(con, scenario: Scenario, spec: dict, evidence: dict) -> dict:
    start, end = spec["start_date"], spec["end_date"]
    days = (end - start).days + 1
    return _row(con, """
        SELECT
            count(*) FILTER (WHERE load_batch = $batch) AS duplicate_rows,
            sum(amount) FILTER (WHERE load_batch = $batch) AS duplicate_amount,
            sum(amount) FILTER (WHERE payment_date BETWEEN $start AND $end) AS window_paid,
            sum(amount) FILTER (WHERE payment_date BETWEEN $start AND $end
                                AND load_batch <> $batch) AS window_paid_without_reload,
            sum(amount) FILTER (WHERE payment_date >= $before AND payment_date < $start)
                / 28.0 * $days AS paid_in_same_length_before
        FROM claim_payments
    """, {
        "batch": spec["reload_batch"],
        "start": start,
        "end": end,
        "before": start - timedelta(days=28),
        "days": days,
    })


def _staff_departure(con, scenario: Scenario, spec: dict, evidence: dict) -> dict:
    first_leave, last_leave = min(spec["leave_dates"]), max(spec["leave_dates"])
    result = _row(con, """
        SELECT
            median(close_date - report_date) FILTER (
                WHERE region = $region AND report_date >= $before AND report_date < $first)
                AS region_median_close_days_before,
            median(close_date - report_date) FILTER (
                WHERE region = $region AND report_date >= $last AND report_date < $after)
                AS region_median_close_days_after,
            median(close_date - report_date) FILTER (
                WHERE region <> $region AND report_date >= $before AND report_date < $first)
                AS other_regions_median_close_days_before,
            median(close_date - report_date) FILTER (
                WHERE region <> $region AND report_date >= $last AND report_date < $after)
                AS other_regions_median_close_days_after
        FROM claims
        WHERE status = 'closed'
    """, {
        "region": spec["region"],
        "before": first_leave - timedelta(days=120),
        "first": first_leave,
        "last": last_leave,
        "after": last_leave + timedelta(days=60),
    })
    open_per_adjuster = con.execute("""
        SELECT a.region, count(c.claim_id)::DOUBLE / count(DISTINCT a.adjuster_id)
        FROM adjusters a
        LEFT JOIN claims c ON c.adjuster_id = a.adjuster_id AND c.status = 'open'
        WHERE a.leave_date IS NULL
        GROUP BY a.region
    """).fetchall()
    result["open_claims_per_adjuster_by_region"] = {
        region: round(value, 2) for region, value in sorted(open_per_adjuster)
    }
    return result


def _channel_growth(con, scenario: Scenario, spec: dict, evidence: dict) -> dict:
    (compare_start, compare_end), (base_start, base_end) = (
        spec["compare_period"],
        spec["baseline_period"],
    )
    return _row(con, f"""
        WITH {CLAIM_COSTS},
        periods AS (
            SELECT *,
                loss_date BETWEEN $c0 AND $c1 AS in_compare,
                loss_date BETWEEN $b0 AND $b1 AS in_baseline
            FROM claim_costs
        )
        SELECT
            avg(incurred) FILTER (WHERE in_compare)
                / avg(incurred) FILTER (WHERE in_baseline) AS overall_avg_cost_ratio,
            avg(incurred) FILTER (WHERE in_compare AND product = 'motor')
                / avg(incurred) FILTER (WHERE in_baseline AND product = 'motor')
                AS motor_avg_cost_ratio,
            avg(incurred) FILTER (WHERE in_compare AND product = 'home')
                / avg(incurred) FILTER (WHERE in_baseline AND product = 'home')
                AS home_avg_cost_ratio,
            count(*) FILTER (WHERE in_baseline AND product = 'home')::DOUBLE
                / count(*) FILTER (WHERE in_baseline) AS home_share_baseline,
            count(*) FILTER (WHERE in_compare AND product = 'home')::DOUBLE
                / count(*) FILTER (WHERE in_compare) AS home_share_compare
        FROM periods
    """, {"c0": compare_start, "c1": compare_end, "b0": base_start, "b1": base_end})


def _reporting_lag(con, scenario: Scenario, spec: dict, evidence: dict) -> dict:
    latest = scenario.as_of.replace(day=1)
    return _row(con, """
        SELECT
            count(*) FILTER (WHERE loss_date >= $latest) AS latest_month_claims,
            count(*) FILTER (WHERE loss_date >= $prior AND loss_date < $latest) / 6.0
                AS prior_monthly_claims,
            avg(report_date - loss_date) AS avg_report_delay_days,
            count(*) FILTER (WHERE report_date - loss_date > 14)::DOUBLE / count(*)
                AS share_reported_after_two_weeks
        FROM claims
    """, {"latest": latest, "prior": months_before(latest, 6)})


def _seasonal_control(con, scenario: Scenario, spec: dict, evidence: dict) -> dict:
    rows = con.execute("""
        WITH monthly_claims AS (
            SELECT year(loss_date) AS yr, month(loss_date) AS mo, count(*) AS claims
            FROM claims
            WHERE region = $region AND product = $product AND cause = $cause
            GROUP BY ALL
        ),
        monthly_exposure AS (
            SELECT year(month) AS yr, month(month) AS mo, sum(policies_in_force) AS policies
            FROM exposure_monthly
            WHERE region = $region AND product = $product
            GROUP BY ALL
        )
        SELECT e.yr,
            1000 * sum(coalesce(c.claims, 0)) FILTER (WHERE list_contains($peak, e.mo))
                / sum(e.policies) FILTER (WHERE list_contains($peak, e.mo)),
            1000 * sum(coalesce(c.claims, 0)) FILTER (WHERE list_contains($compare, e.mo))
                / sum(e.policies) FILTER (WHERE list_contains($compare, e.mo)),
            sum(coalesce(c.claims, 0)) FILTER (WHERE list_contains($peak, e.mo))
        FROM monthly_exposure e
        LEFT JOIN monthly_claims c USING (yr, mo)
        GROUP BY e.yr
        ORDER BY e.yr
    """, {
        "region": spec["region"],
        "product": spec["product"],
        "cause": spec["cause"],
        "peak": spec["peak_months"],
        "compare": spec["compare_months"],
    }).fetchall()
    by_year = {
        str(year): {
            "peak_claims_per_1000_policies": round(float(peak), 3),
            "other_months_claims_per_1000_policies": round(float(other), 3),
            "peak_claim_count": int(count),
        }
        for year, peak, other, count in rows
    }
    first, last = by_year[str(rows[0][0])], by_year[str(rows[-1][0])]
    return {
        "by_year": by_year,
        "peak_frequency_last_vs_first_year": round(
            last["peak_claims_per_1000_policies"] / first["peak_claims_per_1000_policies"], 3
        ),
    }


def _noise_control(con, scenario: Scenario, spec: dict, evidence: dict) -> dict:
    start, end = spec["period"]
    return _row(con, """
        WITH monthly AS (
            SELECT e.month, 1000 * count(c.claim_id) / any_value(e.policies) AS frequency
            FROM (
                SELECT month, sum(policies_in_force) AS policies
                FROM exposure_monthly WHERE month BETWEEN $start AND $end GROUP BY month
            ) e
            LEFT JOIN claims c
                ON c.loss_date >= e.month AND c.loss_date < e.month + INTERVAL 1 MONTH
            GROUP BY e.month
        )
        SELECT stddev_samp(frequency) / avg(frequency) AS monthly_frequency_variation
        FROM monthly
    """, {"start": start, "end": end})


def _injected_note(con, scenario: Scenario, spec: dict, evidence: dict) -> dict:
    return _row(con, """
        SELECT count(*) AS claims_with_note, any_value(claim_id) AS claim_id,
               any_value(repair_shop_id) AS repair_shop_id
        FROM claims WHERE notes = $text
    """, {"text": spec["text"]})


def _early_claims(con, scenario: Scenario, spec: dict, evidence: dict) -> dict:
    """The state's claims of this cause before and since the start: how many a month, the
    share made within 30 days of cover starting, and which channel those early claims came
    through."""
    start = spec["start_date"]
    since_months = max((scenario.as_of - start).days / 30.44, 1.0)
    return _row(con, """
        WITH c AS (
            SELECT c.loss_date, c.loss_date - p.start_date AS days_in, p.channel
            FROM claims c JOIN policies p USING (policy_id)
            WHERE c.state = $state AND c.product = $product AND c.cause = $cause
        )
        SELECT
            count(*) FILTER (WHERE loss_date >= $before AND loss_date < $start) / 12.0
                AS claims_per_month_before,
            count(*) FILTER (WHERE loss_date >= $start) / $since_months
                AS claims_per_month_since,
            avg((days_in <= 30)::INT) FILTER (WHERE loss_date >= $before AND loss_date < $start)
                AS early_share_before,
            avg((days_in <= 30)::INT) FILTER (WHERE loss_date >= $start) AS early_share_since,
            avg((channel = $channel)::INT) FILTER (WHERE loss_date >= $start AND days_in <= 30)
                AS channel_share_of_early_claims_since
        FROM c
    """, {"state": spec["state"], "product": spec["product"], "cause": spec["cause"],
          "channel": spec["channel"], "start": start, "before": months_before(start, 12),
          "since_months": since_months})


MEASURES = {
    "weather_event": _weather_event,
    "shop_inflation": _shop_inflation,
    "duplicate_payments": _duplicate_payments,
    "staff_departure": _staff_departure,
    "channel_growth": _channel_growth,
    "reporting_lag": _reporting_lag,
    "seasonal_control": _seasonal_control,
    "noise_control": _noise_control,
    "injected_note": _injected_note,
    "early_claims": _early_claims,
}


def measure(
    con: duckdb.DuckDBPyConnection, scenario: Scenario, spec: dict, evidence: dict
) -> dict:
    return MEASURES[spec["type"]](con, scenario, spec, evidence)
