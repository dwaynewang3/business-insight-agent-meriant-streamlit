"""Command line: start the policies MCP server on stdio.

    uv run python -m mcp_servers.policies --as-of 2026-09-30
"""

import argparse
from datetime import date
from pathlib import Path

from agent.context import warehouse_dates

from .build import DEFAULT_PATH
from .search import PolicyLibrary
from .server import build_server


def main() -> None:
    parser = argparse.ArgumentParser(description="The policies MCP server.")
    parser.add_argument("--kb", type=Path, default=DEFAULT_PATH, help="the policy knowledge base")
    parser.add_argument("--as-of", type=date.fromisoformat,
                        help="today's date for the library; default: the warehouse's extract date")
    parser.add_argument("--warehouse", type=Path, default=Path("data/dev.duckdb"))
    args = parser.parse_args()
    today = args.as_of or date.fromisoformat(str(warehouse_dates(args.warehouse)["extract_date"]))
    build_server(PolicyLibrary(args.kb), today).run("stdio")


if __name__ == "__main__":
    main()
