"""Checks that the generated warehouse is internally consistent and behaves like a real book."""

from dataclasses import replace

import duckdb

from data.generator import generate


def value(con, sql: str):
    return con.execute(sql).fetchone()[0]


def test_all_tables_have_rows(dev):
    tables = [
        "warehouse_info", "policyholders", "policies", "exposure_monthly", "claims",
        "claim_payments", "adjusters", "repair_shops", "weather_events",
    ]
    for table in tables:
        assert value(dev, f"SELECT count(*) FROM {table}") > 0, table


def test_references_point_to_existing_rows(dev):
    orphans = {
        "policy without holder":
            "SELECT count(*) FROM policies WHERE policyholder_id NOT IN "
            "(SELECT policyholder_id FROM policyholders)",
        "claim without policy":
            "SELECT count(*) FROM claims WHERE policy_id NOT IN (SELECT policy_id FROM policies)",
        "claim without adjuster":
            "SELECT count(*) FROM claims WHERE adjuster_id NOT IN "
            "(SELECT adjuster_id FROM adjusters)",
        "claim with unknown shop":
            "SELECT count(*) FROM claims WHERE repair_shop_id IS NOT NULL AND repair_shop_id "
            "NOT IN (SELECT repair_shop_id FROM repair_shops)",
        "payment without claim":
            "SELECT count(*) FROM claim_payments WHERE claim_id NOT IN "
            "(SELECT claim_id FROM claims)",
    }
    for problem, sql in orphans.items():
        assert value(dev, sql) == 0, problem


def test_claim_dates_follow_the_claim_lifecycle(dev, scenario):
    as_of = scenario.as_of.isoformat()
    assert value(dev, f"""
        SELECT count(*) FROM claims
        WHERE report_date < loss_date OR report_date > DATE '{as_of}' OR close_date < report_date
    """) == 0
    assert value(dev, f"""
        SELECT count(*) FROM claim_payments p JOIN claims c USING (claim_id)
        WHERE p.payment_date < c.report_date OR p.payment_date > DATE '{as_of}'
    """) == 0


def test_claims_happen_while_the_policy_is_in_force(dev):
    assert value(dev, """
        SELECT count(*) FROM claims c JOIN policies p USING (policy_id)
        WHERE c.loss_date < p.start_date
           OR (p.end_date IS NOT NULL AND c.loss_date >= p.end_date)
           OR c.state <> p.state OR c.product <> p.product
    """) == 0


def test_status_matches_close_date_and_reserve(dev):
    assert value(dev, """
        SELECT count(*) FROM claims
        WHERE status NOT IN ('open', 'closed')
           OR (status = 'closed' AND (close_date IS NULL OR reserve_amount <> 0))
           OR (status = 'open' AND close_date IS NOT NULL)
           OR reserve_amount < 0
    """) == 0


def test_adjusters_work_their_region_while_employed(dev):
    assert value(dev, """
        SELECT count(*) FROM claims c JOIN adjusters a USING (adjuster_id)
        WHERE a.region <> c.region OR a.hire_date > c.report_date
           OR (a.leave_date IS NOT NULL AND a.leave_date <= c.report_date)
    """) == 0


def test_departed_adjusters_hold_no_open_claims(dev):
    assert value(dev, """
        SELECT count(*) FROM claims c JOIN adjusters a USING (adjuster_id)
        WHERE a.leave_date IS NOT NULL AND c.status = 'open'
    """) == 0


def test_repair_shops_only_on_motor_damage_in_the_same_state(dev):
    assert value(dev, """
        SELECT count(*) FROM claims c LEFT JOIN repair_shops s USING (repair_shop_id)
        WHERE (c.product = 'motor' AND c.cause IN ('collision', 'glass', 'storm'))
                <> (c.repair_shop_id IS NOT NULL)
           OR s.state <> c.state
    """) == 0


def test_loss_ratio_is_in_a_realistic_range(dev):
    loss_ratio = value(dev, """
        SELECT ((SELECT sum(amount) FROM claim_payments) + (SELECT sum(reserve_amount) FROM claims))
               / (SELECT sum(earned_premium) FROM exposure_monthly)
    """)
    assert 0.4 < loss_ratio < 0.8


def test_same_seed_gives_the_same_data(scenario, tmp_path):
    small = replace(scenario, policies=replace(scenario.policies, initial_count=1500))
    small = replace(small, incidents=[i for i in small.incidents if i["type"] != "weather_event"])
    fingerprints = []
    for name in ("first", "second"):
        path = tmp_path / f"{name}.duckdb"
        generate(small, path)
        with duckdb.connect(str(path), read_only=True) as con:
            fingerprints.append(con.execute("""
                SELECT (SELECT md5(string_agg(claim_id || cause || loss_date || coalesce(notes, ''),
                                               ',' ORDER BY claim_id)) FROM claims),
                       (SELECT sum(amount) FROM claim_payments),
                       (SELECT md5(string_agg(email, ',' ORDER BY policyholder_id))
                        FROM policyholders)
            """).fetchone())
    assert fingerprints[0] == fingerprints[1]
