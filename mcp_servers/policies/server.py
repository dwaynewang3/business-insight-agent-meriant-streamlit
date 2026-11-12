"""The policies MCP server: read-only search of Meridian's policy library.

    uv run python -m mcp_servers.policies --as-of 2026-09-30

A thin wrapper around PolicyLibrary (search.py), where the logic and the tests live. Results
are clauses in force on a date, each with its clause ID and version, so every policy
statement can be cited. "Today" is the warehouse's extract date, passed in by the app. It
works from any MCP client, including Claude Code.
"""

import json
from datetime import date
from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

from .search import PolicyLibrary

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True,
                            open_world_hint=False)

INSTRUCTIONS = (
    "Read-only search of Meridian General Insurance's internal policy library: claims "
    "handling, motor coverage and exclusions, delegated authority, fraud, documentation, "
    "service levels, and settlement and excess. Every result is a clause with its ID and "
    "version. Cite the clause IDs you rely on."
)

SEARCH = (
    "Search Meridian's internal policy library: claims handling, motor coverage and "
    "exclusions, delegated authority, fraud, documentation, service levels, settlement and "
    "excess. Returns the most relevant clauses with clause_id, version, effective dates, the "
    "document's review date, and text.\n"
    "Use when: the user asks what a policy says or what a rule, limit or threshold is; or "
    "BEFORE writing SQL that applies a policy rule across many claims (fetch the rule, then "
    "cite it).\n"
    "Do not use for: counts, sums or trends in claims data (use run_sql); checking one "
    "specific claim (use check_claim_compliance).\n"
    "Policies change over time. Pass as_of_date (YYYY-MM-DD) when the question concerns a past "
    "date or a specific incident, or null for today, the warehouse's extract date ({today}). "
    "claim_type is motor for motor claims. top_k: how many clauses, 1 to 10 (8 is usual).\n"
    "Always cite clause_ids from the results. If no result answers the question, say the "
    "policy library does not cover it."
)

GET_CLAUSE = (
    "Fetch the exact text of one clause by ID, e.g. 'POL-AUT-003:4.7' or 'POL-MTR-002:3.4'. "
    "Pass as_of_date for the version in force on that date (null for today, {today}), or "
    "all_versions=true to see how the clause changed over time. Use when a clause ID is "
    "already known (from the user, an earlier result or a cross-reference)."
)


def _day(text: str | None, default: date) -> date:
    if not text:
        return default
    try:
        return date.fromisoformat(text)
    except ValueError as error:
        raise ToolError(f"as_of_date must be a date like 2026-06-16, not {text!r}.") from error


def build_server(library: PolicyLibrary, today: date) -> MCPServer:
    server = MCPServer("policies", instructions=INSTRUCTIONS, version="0.1.0",
                       log_level="WARNING")

    @server.tool(annotations=READ_ONLY, description=SEARCH.format(today=today))
    def search_policies(
        query: str,
        as_of_date: str | None,
        claim_type: Literal["motor", "home", "liability", "travel"],
        top_k: int,
    ) -> str:
        if not query.strip():
            raise ToolError("query is empty. Ask in words or keywords; codes like D-04 work.")
        day = _day(as_of_date, today)
        hits = library.search(query, day, day, claim_type=claim_type, k=max(1, min(top_k, 10)))
        return json.dumps({
            "as_of_date": day.isoformat(),
            "clauses": [h.clause.as_dict() for h in hits],
            "note": "Cite the clause_ids you rely on. If none of these answers the question, "
                    "say the policy library doesn't cover it.",
        })

    @server.tool(annotations=READ_ONLY, description=GET_CLAUSE.format(today=today))
    def get_policy_clause(clause_id: str, as_of_date: str | None, all_versions: bool) -> str:
        try:
            versions = library.get_clause(clause_id, _day(as_of_date, today), all_versions)
        except ValueError as error:
            raise ToolError(str(error)) from error
        if not versions:
            raise ToolError(f"No clause {clause_id!r} is in force on "
                            f"{_day(as_of_date, today)}. Try all_versions=true, or "
                            "search_policies.")
        return json.dumps({"clauses": [c.as_dict() for c in versions]})

    return server
