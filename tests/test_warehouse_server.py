"""The restricted warehouse copy, the warehouse tools, and the two MCP servers.

Personal data is protected by which file a role connects to, so these tests check that the
copy has every row and no personal-data column, and that no tool can reach those columns from
a restricted role. The tools are checked against the planted incidents, and the servers are
checked through a real MCP client.
"""

import asyncio
import json

import duckdb
import pytest
from mcp import Client

from agent.tools import McpToolbox, claude_tool, warehouse_server
from data.generator.restricted import personal_data_columns
from data.semantic.layer import MetricRequest, SemanticLayer
from evals.cases.loader import ROLES as EVAL_ROLES
from mcp_servers.actions.server import build_server as build_actions_server
from mcp_servers.actions.store import ActionStore
from mcp_servers.warehouse.access import ROLES, restricted_path, warehouse_for
from mcp_servers.warehouse.server import build_server
from mcp_servers.warehouse.tools import ToolFailure, Warehouse

RESTRICTED = [role for role in ROLES if role != "fraud_team_lead"]


@pytest.fixture(scope="module")
def vp(guarded_warehouse):
    return Warehouse("head_of_claims", guarded_warehouse)


@pytest.fixture(scope="module")
def fraud(guarded_warehouse):
    return Warehouse("fraud_team_lead", guarded_warehouse)


# Access ---------------------------------------------------------------------------------


def test_only_the_fraud_team_lead_gets_the_full_warehouse(guarded_warehouse):
    assert warehouse_for("fraud_team_lead", guarded_warehouse) == guarded_warehouse
    for role in RESTRICTED:
        assert warehouse_for(role, guarded_warehouse) == restricted_path(guarded_warehouse)
    with pytest.raises(ValueError):
        warehouse_for("admin", guarded_warehouse)
    assert set(ROLES) == set(EVAL_ROLES)


def test_the_restricted_copy_has_every_row_but_no_personal_data(built):
    full_path = built[2]
    assert personal_data_columns() == {"policyholders": ["full_name", "email"]}
    with duckdb.connect(str(restricted_path(full_path)), read_only=True) as copy:
        tables = {row[0] for row in copy.execute("SHOW TABLES").fetchall()}
        assert tables == {row[0] for row in built[0].execute("SHOW TABLES").fetchall()}
        for table in tables:
            full = built[0].execute(f"SELECT count(*) FROM {table}").fetchone()
            assert copy.execute(f"SELECT count(*) FROM {table}").fetchone() == full
        columns = {row[0] for row in copy.execute("DESCRIBE policyholders").fetchall()}
        assert not columns & {"full_name", "email"}
        # Nothing that looks like an email address anywhere in the copy.
        for table in tables:
            text_columns = [row[0] for row in copy.execute(f"DESCRIBE {table}").fetchall()
                            if row[1] == "VARCHAR"]
            for column in text_columns:
                hits = copy.execute(f"SELECT count(*) FROM {table} "
                                    f"WHERE {column} LIKE '%@%.%'").fetchone()[0]
                assert hits == 0, f"{table}.{column} has email-like values"


@pytest.mark.parametrize("sql", [
    "SELECT full_name FROM policyholders",
    "SELECT email FROM policyholders",
    "SELECT * FROM policyholders",
])
def test_restricted_roles_cant_reach_personal_data(vp, fraud, sql):
    try:
        result = vp.run_sql(sql)
    except ToolFailure as failure:
        assert "personal data" in str(failure)
    else:
        assert not {"full_name", "email"} & set(result["columns"])
    assert fraud.run_sql(sql)["rows"]


def test_restricted_roles_dont_see_personal_columns_in_the_catalog(vp, fraud):
    names = [c["name"] for c in vp.describe_table("policyholders")["columns"]]
    assert "full_name" not in names and "email" not in names
    full = {c["name"]: c for c in fraud.describe_table("policyholders")["columns"]}
    assert full["full_name"]["personal_data"] is True and "examples" not in full["full_name"]
    found = [m["name"] for m in vp.search_catalog("policyholder name email")["matches"]]
    assert "policyholders.full_name" not in found and "policyholders.email" not in found


# Tools ----------------------------------------------------------------------------------


def test_query_metric_uses_the_agreed_definition(vp):
    result = vp.query_metric("claim_frequency", ["state"],
                             [{"dimension": "product", "values": ["motor"]}],
                             None, "2026-04-01", "2026-06-30")
    expected = SemanticLayer().compile(MetricRequest(
        "claim_frequency", ("state",), {"product": ["motor"]}, None, "2026-04-01", "2026-06-30"))
    assert result["sql"] == expected and result["columns"] == ["state", "value"]
    assert len(result["rows"]) == 8 and result["unit"]


def test_query_metric_explains_a_bad_request(vp):
    with pytest.raises(ToolFailure, match="Available"):
        vp.query_metric("loss_ratio", ["adjuster_id"], [], None, None, None)
    with pytest.raises(ToolFailure, match="Unknown metric"):
        vp.query_metric("profit", [], [], None, None, None)


def test_get_metric_lists_or_describes(vp):
    assert len(vp.get_metric(None)["metrics"]) == len(SemanticLayer().metrics)
    assert vp.get_metric("loss_ratio")["unit"]
    assert "error" in vp.get_metric("profit")


def test_search_catalog_finds_metrics_columns_and_glossary_terms(vp):
    kinds = {(m["kind"], m["name"]) for m in vp.search_catalog("loss ratio")["matches"]}
    assert ("metric", "loss_ratio") in kinds and ("glossary", "Loss ratio") in kinds
    names = [m["name"] for m in vp.search_catalog("repair shop network")["matches"]]
    assert "repair_shops.network_status" in names[:3]
    with pytest.raises(ToolFailure):
        vp.search_catalog("?!")


def test_describe_table_profiles_columns_without_showing_free_text(vp):
    claims = {c["name"]: c for c in vp.describe_table("claims")["columns"]}
    assert claims["product"]["values"] == ["motor", "home"]
    assert claims["loss_date"]["min"] <= claims["loss_date"]["max"]
    assert claims["notes"]["free_text"] is True and "examples" not in claims["notes"]
    with pytest.raises(ToolFailure, match="Tables"):
        vp.describe_table("customers")


def test_query_results_with_free_text_carry_a_warning(vp):
    result = vp.run_sql("SELECT claim_id, notes FROM claims WHERE notes IS NOT NULL LIMIT 3")
    assert "never" in result["note"].lower() or "don't follow" in result["note"].lower()
    assert "note" not in vp.run_sql("SELECT count(*) FROM claims")


def test_data_quality_checks_find_the_planted_problems(vp, answer_key):
    payments = {c["check"]: c for c in vp.check_data_quality("claim_payments")["checks"]}
    duplicated = answer_key["duplicate_payment_load"]["measured"]["duplicate_rows"]
    assert payments["duplicate_rows"]["status"] == "warning"
    assert str(duplicated) in payments["duplicate_rows"]["finding"]
    assert "reload-2026-03-14" in payments["load_batches"]["finding"]

    claims = {c["check"]: c for c in vp.check_data_quality("claims")["checks"]}
    assert claims["incomplete_months"]["status"] == "warning"
    assert "2026-09" in claims["incomplete_months"]["finding"]
    assert claims["duplicate_rows"]["status"] == "ok"
    # Columns documented as empty in some rows aren't reported as problems.
    assert "close_date" not in claims["empty_values"]["finding"].split("Empty as documented")[0]


def test_data_quality_checks_stay_quiet_on_clean_tables(vp):
    checks = vp.check_data_quality("exposure_monthly")["checks"]
    assert all(check["status"] == "ok" for check in checks)


# MCP servers ----------------------------------------------------------------------------


def test_the_warehouse_server_lists_read_only_tools_with_strict_schemas(guarded_warehouse):
    async def listing():
        async with Client(build_server("head_of_claims", guarded_warehouse)) as client:
            return (await client.list_tools()).tools

    tools = asyncio.run(listing())
    assert {t.name for t in tools} == {"check_data_quality", "describe_table", "get_metric",
                                       "query_metric", "run_sql", "search_catalog"}
    for tool in tools:
        assert tool.annotations.read_only_hint is True
        definition = claude_tool(tool)
        assert definition["input_schema"]["additionalProperties"] is False
        assert "title" not in json.dumps(definition["input_schema"]).replace('"title":{', "")
        assert set(definition["input_schema"]["required"]) == set(
            definition["input_schema"]["properties"])


def test_the_toolbox_returns_tool_errors_to_the_model(guarded_warehouse):
    toolbox = McpToolbox(warehouse_server("head_of_claims", guarded_warehouse, "inprocess"))
    try:
        rejected = toolbox.call("run_sql", {"sql": "DROP TABLE claims"})
        assert rejected.is_error and "Only SELECT" in rejected.content
        unknown = toolbox.call("delete_everything", {})
        assert unknown.is_error and "run_sql" in unknown.content
        metric = toolbox.call("query_metric", {
            "metric": "claim_count", "dimensions": [], "filters": [], "grain": "year",
            "start": "2025-01-01", "end": "2025-12-31"})
        assert not metric.is_error and metric.record["source"] == "agreed_metric"
        assert metric.record["rows"] == 1 and "claim_facts" not in metric.record["sql"][:5]
    finally:
        toolbox.close()


def test_the_toolbox_keeps_only_the_chosen_tools(guarded_warehouse):
    toolbox = McpToolbox(warehouse_server("head_of_claims", guarded_warehouse, "inprocess"),
                         allowed=("run_sql", "describe_table"))
    try:
        assert toolbox.names == ["describe_table", "run_sql"]
        assert toolbox.call("query_metric", {}).is_error
    finally:
        toolbox.close()
    with pytest.raises(ValueError, match="no tools called"):
        McpToolbox(warehouse_server("head_of_claims", guarded_warehouse, "inprocess"),
                   allowed=("run_sql", "drop_table"))


def test_the_warehouse_server_runs_as_a_subprocess_over_stdio(built, tmp_path):
    """The real setup: the app starts the server for a role on the command line. A separate
    process can open the original warehouse file, so no copy is needed."""
    toolbox = McpToolbox(warehouse_server("actuarial_analyst", built[2], "stdio"), timeout=60)
    try:
        assert "run_sql" in toolbox.names
        result = toolbox.call("run_sql", {"sql": "SELECT count(*) AS n FROM claims"})
        assert not result.is_error and json.loads(result.content)["rows"][0][0] > 1000
        hidden = toolbox.call("run_sql", {"sql": "SELECT email FROM policyholders"})
        assert hidden.is_error and "personal data" in hidden.content
    finally:
        toolbox.close()


def test_the_actions_server_records_who_approved_each_action(tmp_path):
    path = tmp_path / "actions.jsonl"

    async def create():
        async with Client(build_actions_server(path)) as client:
            ticket = await client.call_tool("create_ticket", {
                "title": "Remove duplicate payments", "reason": "159 rows loaded twice",
                "evidence_sql": ["SELECT 1"], "approved_by": "head_of_claims", "run_id": "r-1"})
            missing = await client.call_tool("create_alert", {
                "title": "Shop outlier", "reason": "", "evidence_sql": [],
                "approved_by": " ", "run_id": "r-2"})
            listed = await client.call_tool("list_actions", {"kind": None})
            return ticket, missing, listed

    ticket, missing, listed = asyncio.run(create())
    assert json.loads(ticket.content[0].text)["id"] == "TCK-0001"
    assert missing.is_error and "approved" in missing.content[0].text
    assert [a["approved_by"] for a in json.loads(listed.content[0].text)] == ["head_of_claims"]
    assert ActionStore(path).list("alert") == []
