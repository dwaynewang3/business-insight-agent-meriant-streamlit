"""The agent's tools, loaded from MCP servers.

Each session starts the warehouse MCP server for the user's role (so the model can't change
the role) and the policies MCP server, lists their tools in one fixed, sorted order (so the
prompt cache keeps working), and turns them into Claude tool definitions. Tool calls go
through the MCP client of the server that owns the tool.

The MCP client is async and the agent is not, so the client runs on its own event loop in a
background thread, inside a single task that owns the connection for its whole life.
"""

import asyncio
import concurrent.futures
import functools
import json
import os
import re
import sys
import threading
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from mcp_servers.actions.github import ENV_VARS as GITHUB_ENV_VARS

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Which tool a number came from, for the "Agreed metric" and "Custom query" labels.
SOURCES = {"query_metric": "agreed_metric", "run_sql": "custom_query"}

# Named tool sets. Experiment 1's "semantic layer off" arm drops the metric tools and the
# catalog search (which also returns metric definitions).
POLICY_TOOLS = ("get_policy_clause", "search_policies")

TOOLSETS: dict[str, tuple[str, ...] | None] = {
    "full": None,
    "semantic_off": ("check_data_quality", "describe_table", "run_sql"),
    "sql_only": ("run_sql",),
}


@dataclass(frozen=True)
class ToolOutcome:
    content: str  # what the model sees
    is_error: bool
    record: dict  # what the trace and the eval runner keep


def warehouse_server(role: str, warehouse: str | Path, transport: str = "stdio"):
    """How to reach the warehouse server: a subprocess over stdio, or the server object
    itself (in-process, used by the tests)."""
    if transport == "stdio":
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_servers.warehouse", "--role", role, "--warehouse", str(warehouse)],
            cwd=str(PROJECT_ROOT),
        )
    if transport == "inprocess":
        from mcp_servers.warehouse.server import build_server

        return build_server(role, warehouse)
    raise ValueError(f"transport must be stdio or inprocess, not {transport!r}.")


def policies_server(kb: str | Path, today: str, transport: str = "stdio"):
    """How to reach the policies server, with "today" set to the warehouse's extract date."""
    if transport == "stdio":
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_servers.policies", "--kb", str(kb), "--as-of", today],
            cwd=str(PROJECT_ROOT),
        )
    if transport == "inprocess":
        from mcp_servers.policies.server import build_server

        return build_server(_policy_library(str(kb)), date.fromisoformat(today))
    raise ValueError(f"transport must be stdio or inprocess, not {transport!r}.")


@functools.lru_cache(maxsize=4)
def _policy_library(kb: str):
    """Loaded once per process (in-process transport), with the embedder the knowledge base
    was built with, so tests built with the hash embedder never download a model."""
    import duckdb

    from mcp_servers.policies.embed import FastEmbedder, HashEmbedder
    from mcp_servers.policies.search import PolicyLibrary

    with duckdb.connect(kb, read_only=True) as con:
        model = con.execute("SELECT embedding_model FROM kb_info").fetchone()[0]
    return PolicyLibrary(kb, HashEmbedder() if model == HashEmbedder.name else FastEmbedder())


def actions_server(store: str | Path | None, transport: str = "stdio"):
    """How to reach the actions server, which only the graph's own code calls."""
    if transport == "stdio":
        args = ["-m", "mcp_servers.actions"] + (["--store", str(store)] if store else [])
        # A server process inherits only a few safe variables, so the GitHub settings are
        # passed on by name. Only this server gets them: the model can't call it.
        env = {name: os.environ[name] for name in GITHUB_ENV_VARS if os.environ.get(name)}
        return StdioServerParameters(command=sys.executable, args=args, cwd=str(PROJECT_ROOT),
                                     env=env or None)
    if transport == "inprocess":
        from mcp_servers.actions.server import build_server

        return build_server(Path(store) if store else None)
    raise ValueError(f"transport must be stdio or inprocess, not {transport!r}.")


# Tools sent without `strict`. Every strict schema in a request, the report's included, is
# compiled into one grammar, and the API rejects a grammar that grows too large ("Simplify
# your tool schemas or reduce the number of strict tools"). Its documented fix is to keep
# strict for the tools where a malformed call does real harm. The policy tools take simple
# arguments, and their server checks each one and returns errors to the model.
NON_STRICT_TOOLS = frozenset(POLICY_TOOLS)


def claude_tool(tool) -> dict:
    """A Claude tool definition from an MCP tool, with a closed schema, strict unless it's in
    NON_STRICT_TOOLS."""
    schema = _without_titles(tool.input_schema)
    schema["additionalProperties"] = False
    return {
        "name": tool.name,
        "description": " ".join((tool.description or "").split()),
        "input_schema": schema,
        "strict": tool.name not in NON_STRICT_TOOLS,
    }


def _without_titles(node):
    """Drop the schema titles pydantic adds (they only cost tokens). A property that happens to
    be called "title" is a dict, so it stays."""
    if isinstance(node, dict):
        return {k: _without_titles(v) for k, v in node.items()
                if not (k == "title" and isinstance(v, str))}
    if isinstance(node, list):
        return [_without_titles(v) for v in node]
    return node


class McpToolbox:
    def __init__(self, server, allowed: Collection[str] | None = None, timeout: float = 60.0):
        self.timeout = timeout
        self._server = server
        self._loop = asyncio.new_event_loop()
        self._jobs: asyncio.Queue | None = None
        ready: concurrent.futures.Future = concurrent.futures.Future()
        self._thread = threading.Thread(target=self._run, args=(ready,), daemon=True)
        self._thread.start()
        tools = ready.result(timeout)
        chosen = sorted((t for t in tools if allowed is None or t.name in allowed),
                        key=lambda t: t.name)
        if allowed is not None and (missing := set(allowed) - {t.name for t in chosen}):
            self.close()
            raise ValueError(f"The server has no tools called {', '.join(sorted(missing))}.")
        self.definitions = [claude_tool(t) for t in chosen]
        self.names = [t.name for t in chosen]

    def _run(self, ready: concurrent.futures.Future) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve(ready))
        finally:
            self._loop.close()

    async def _serve(self, ready: concurrent.futures.Future) -> None:
        try:
            async with Client(self._server) as client:
                listing = await client.list_tools()
                self._jobs = asyncio.Queue()
                ready.set_result(listing.tools)
                while (job := await self._jobs.get()) is not None:
                    work, result = job
                    try:
                        result.set_result(await work(client))
                    except Exception as error:  # handed to the caller's thread
                        result.set_exception(error)
        except Exception as error:
            if not ready.done():
                ready.set_exception(error)

    def call(self, name: str, arguments: dict, run_id: str | None = None) -> ToolOutcome:
        """Call one tool. run_id is for tools that label their own model calls; MCP tools
        don't use it."""
        record = {"tool": name, "input": arguments, "source": SOURCES.get(name)}
        if name not in self.names:
            message = f"There's no tool called {name!r}. The tools are: {', '.join(self.names)}."
            return ToolOutcome(message, True, {**record, "error": message})
        result: concurrent.futures.Future = concurrent.futures.Future()
        self._loop.call_soon_threadsafe(
            self._jobs.put_nowait, (lambda client: client.call_tool(name, arguments), result))
        try:
            reply = result.result(self.timeout)
        except Exception as error:  # transport failures and timeouts go back to the model
            message = f"The tool call failed: {type(error).__name__}: {error}"
            return ToolOutcome(message, True, {**record, "error": message})
        text = "\n".join(c.text for c in reply.content if getattr(c, "type", "") == "text")
        if reply.is_error:
            return ToolOutcome(text, True, {**record, "error": text})
        return ToolOutcome(text, False, {**record, **_summary(name, arguments, text)})

    def close(self) -> None:
        if self._jobs is not None and self._thread.is_alive():
            self._loop.call_soon_threadsafe(self._jobs.put_nowait, None)
        self._thread.join(self.timeout)


class ToolBelt:
    """Several toolboxes as one: a single sorted tool list, and each call routed to the box
    that owns the tool. It has the same interface as McpToolbox. The boxes are MCP servers,
    plus the agent-side compliance tool (agent/compliance.py)."""

    def __init__(self, boxes: list):
        self.boxes = boxes
        self.owner = {name: box for box in boxes for name in box.names}
        if len(self.owner) != sum(len(box.names) for box in boxes):
            raise ValueError("Two servers offer a tool with the same name.")
        self.definitions = sorted((d for box in boxes for d in box.definitions),
                                  key=lambda d: d["name"])
        self.names = [d["name"] for d in self.definitions]

    def call(self, name: str, arguments: dict, run_id: str | None = None) -> ToolOutcome:
        box = self.owner.get(name)
        if box is None:
            message = f"There's no tool called {name!r}. The tools are: {', '.join(self.names)}."
            return ToolOutcome(message, True, {"tool": name, "input": arguments,
                                               "source": None, "error": message})
        return box.call(name, arguments, run_id)

    def close(self) -> None:
        for box in self.boxes:
            box.close()


def _summary(name: str, arguments: dict, text: str) -> dict:
    """The parts of a tool result worth keeping in the trace: the SQL, the size, and the
    policy clauses returned (which the citation check reads)."""
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        return {}
    summary = {}
    if name == "run_sql":
        summary["sql"] = arguments.get("sql", "")
    elif isinstance(result, dict) and "sql" in result:
        summary["sql"] = result["sql"]
    if isinstance(result, dict) and "rows" in result and isinstance(result["rows"], list):
        summary["rows"] = len(result["rows"])
        summary["truncated"] = result.get("truncated", False)
    if isinstance(result, dict) and isinstance(result.get("clauses"), list):
        summary["clauses"] = [[c["clause_id"], c["version"]] for c in result["clauses"]]
    elif name in SOURCES and (named := sorted(set(_STORED_CLAUSE.findall(text)))):
        # Clauses named in query results, from the recorded compliance findings.
        summary["clauses"] = [list(pair) for pair in named]
    return summary


# How compliance_findings stores a cited clause: POL-AUT-003:2.1 v3.1.
_STORED_CLAUSE = re.compile(r"(POL-[A-Z]{3}-\d{3}:(?:\d+\.\d+|[A-Z])) v(\d+\.\d+)")
