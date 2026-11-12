"""The Claude Code setup in claude_code/: its MCP config starts the warehouse server, and the
skill names only tools that server has."""

import json
import re
from pathlib import Path

import pytest
from mcp.client.stdio import StdioServerParameters

from agent.tools import PROJECT_ROOT, McpToolbox

FOLDER = PROJECT_ROOT / "claude_code"
SKILL = FOLDER / "skills" / "investigate-claims" / "SKILL.md"
TOOLS = ["check_data_quality", "describe_table", "get_metric", "query_metric", "run_sql",
         "search_catalog"]


@pytest.mark.skipif(not Path("data/dev_restricted.duckdb").exists(), reason="needs `make data`")
def test_the_mcp_config_starts_the_warehouse_server_as_written():
    [(name, server)] = json.loads((FOLDER / "mcp.json").read_text())["mcpServers"].items()
    toolbox = McpToolbox(StdioServerParameters(command=server["command"], args=server["args"],
                                               cwd=str(PROJECT_ROOT)), timeout=120)
    try:
        assert name == "claims-warehouse" and toolbox.names == TOOLS
        # head_of_claims, as the config sets it: the copy without personal data.
        refused = toolbox.call("run_sql", {"sql": "SELECT full_name FROM policyholders",
                                           "purpose": "check the role"})
        assert refused.is_error and "personal data" in refused.content
    finally:
        toolbox.close()


def test_the_skill_names_the_server_and_only_tools_it_has():
    front, body = SKILL.read_text().split("---\n", 2)[1:]
    fields = dict(line.split(": ", 1) for line in front.strip().splitlines())
    assert fields["name"] == SKILL.parent.name and len(fields["description"]) > 50
    assert "`claims-warehouse`" in body
    named = set(re.findall(r"`([a-z]+(?:_[a-z]+)+)`", body))
    assert named - {"weather_events"} <= set(TOOLS) and len(named & set(TOOLS)) >= 5
