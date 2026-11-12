"""The semantic layer documents the real warehouse, and its metrics give the right numbers."""

from datetime import date

import pytest

from data.semantic import MetricError, MetricRequest, SemanticLayer


@pytest.fixture(scope="session")
def layer():
    return SemanticLayer()


def run(con, layer, **request):
    return con.execute(layer.compile(MetricRequest(**request))).fetchall()


def test_catalog_documents_every_table_and_column(dev, layer):
    actual = set(dev.execute("""
        SELECT table_name, column_name FROM information_schema.columns
        WHERE table_schema = 'main'
    """).fetchall())
    documented = {
        (table, column) for table, spec in layer.tables.items() for column in spec["columns"]
    }
    assert documented - actual == set(), "documented but not in the warehouse"
    assert actual - documented == set(), "in the warehouse but not documented"


def test_categorical_values_are_all_documented(dev, layer):
    for table, spec in layer.tables.items():
        for column, column_spec in spec["columns"].items():
            if "values" not in column_spec:
                continue
            actual = {
                v for (v,) in dev.execute(
                    f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL"
                ).fetchall()
            }
            assert actual <= set(column_spec["values"]), (table, column)


def test_scoping_doc_metrics_are_all_defined(layer):
    agreed = ["claim_count", "claim_frequency", "average_claim_cost", "loss_ratio",
              "cycle_time_days", "paid_amount"]
    assert set(agreed) <= set(layer.metrics)


def test_every_metric_runs_as_a_total_by_month_and_by_dimension(dev, layer):
    for name in layer.metrics:
        (total,) = run(dev, layer, metric=name, grain=None)
        assert total[-1] is not None, name
        assert len(run(dev, layer, metric=name, grain="month")) >= 20, name
        dimension = layer.dimensions(name)[0]
        by_dimension = run(dev, layer, metric=name, grain=None, dimensions=(dimension,))
        assert len(by_dimension) >= 2, (name, dimension)


def test_loss_ratio_matches_hand_written_sql(dev, layer):
    expected = dict(dev.execute("""
        WITH incurred AS (
            SELECT c.product, sum(c.reserve_amount) + coalesce(sum(p.paid), 0) AS losses
            FROM claims c
            LEFT JOIN (SELECT claim_id, sum(amount) AS paid FROM claim_payments GROUP BY 1) p
                USING (claim_id)
            GROUP BY 1
        )
        SELECT product, losses / (SELECT sum(earned_premium) FROM exposure_monthly e
                                  WHERE e.product = incurred.product)
        FROM incurred
    """).fetchall())
    got = dict(run(dev, layer, metric="loss_ratio", grain=None, dimensions=("product",)))
    for product, ratio in expected.items():
        assert float(got[product]) == pytest.approx(float(ratio))


def test_claim_frequency_is_claims_per_thousand_policies(dev, layer):
    request = dict(metric="claim_frequency", grain="month", filters={"region": "VIC & TAS"},
                   start=date(2025, 1, 1), end=date(2025, 1, 31))
    ((_, frequency),) = run(dev, layer, **request)
    claims, policies = dev.execute("""
        SELECT (SELECT count(*) FROM claims WHERE region = 'VIC & TAS'
                AND loss_date BETWEEN DATE '2025-01-01' AND DATE '2025-01-31'),
               (SELECT sum(policies_in_force) FROM exposure_monthly
                WHERE region = 'VIC & TAS' AND month = DATE '2025-01-01')
    """).fetchone()
    assert float(frequency) == pytest.approx(1000 * claims / float(policies))


def test_semantic_layer_agrees_with_the_answer_key(dev, layer, answer_key):
    def average_cost_by_product(start, end):
        rows = run(dev, layer, metric="average_claim_cost", grain=None,
                   dimensions=("product",), start=start, end=end)
        return {product: float(value) for product, value in rows}

    q2_2026 = average_cost_by_product("2026-04-01", "2026-06-30")
    year_2025 = average_cost_by_product("2025-01-01", "2025-12-31")
    expected = answer_key["home_partner_growth"]["measured"]
    for product in ("motor", "home"):
        ratio = q2_2026[product] / year_2025[product]
        assert ratio == pytest.approx(expected[f"{product}_avg_cost_ratio"], rel=1e-3)


def test_unknown_metric_or_dimension_explains_the_options(layer):
    with pytest.raises(MetricError, match="Available metrics"):
        layer.compile(MetricRequest(metric="severity_index"))
    with pytest.raises(MetricError, match="Available: state, region, product"):
        layer.compile(MetricRequest(metric="claim_frequency", dimensions=("cause",)))
    with pytest.raises(MetricError, match="must be a date"):
        layer.compile(MetricRequest(metric="claim_count", start="last spring"))


def test_filter_values_cannot_change_the_query(dev, layer):
    rows = run(dev, layer, metric="claim_count", grain=None,
               filters={"state": "NSW' OR '1'='1"})
    assert rows == [(0,)]
