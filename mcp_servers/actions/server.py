"""The actions MCP server: creates tickets and alerts.

    uv run python -m mcp_servers.actions

The model never gets these tools. The agent's report lists proposed actions, the graph
pauses, and only the actions a person approves are sent here by the graph's own code.
"""

import json
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

from .store import ActionStore

WRITES = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False,
                         open_world_hint=False)


def build_server(path: Path | None = None, issues=None) -> MCPServer:
    """issues: a GitHubIssues to open each action as an issue too, or None (local only)."""
    store = ActionStore(path, issues)
    server = MCPServer("actions", version="0.1.0", log_level="WARNING", instructions=(
        "Creates tickets and alerts. Call it only for actions a person has approved."))

    def create(kind: str, title: str, reason: str, evidence_sql: list[str], approved_by: str,
               run_id: str) -> str:
        try:
            return json.dumps(store.create(kind, title, reason, evidence_sql, approved_by,
                                           run_id))
        except ValueError as error:
            raise ToolError(str(error)) from error

    @server.tool(annotations=WRITES)
    def create_ticket(title: str, reason: str, evidence_sql: list[str], approved_by: str,
                      run_id: str) -> str:
        """Open a ticket, such as a data-quality fix for the data team, with the evidence."""
        return create("ticket", title, reason, evidence_sql, approved_by, run_id)

    @server.tool(annotations=WRITES)
    def create_alert(title: str, reason: str, evidence_sql: list[str], approved_by: str,
                     run_id: str) -> str:
        """Raise an alert, such as a possible fraud pattern for the fraud team, with the
        evidence."""
        return create("alert", title, reason, evidence_sql, approved_by, run_id)

    @server.tool(annotations=ToolAnnotations(read_only_hint=True))
    def list_actions(kind: str | None) -> str:
        """List tickets and alerts created so far. kind: "ticket", "alert", or null for both."""
        return json.dumps(store.list(kind))

    return server
