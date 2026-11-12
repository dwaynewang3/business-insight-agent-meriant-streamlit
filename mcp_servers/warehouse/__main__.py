"""Command line: start the warehouse MCP server on stdio for one role.

    uv run python -m mcp_servers.warehouse --role head_of_claims --warehouse data/dev.duckdb
"""

import argparse

from .access import ROLES
from .server import build_server


def main() -> None:
    parser = argparse.ArgumentParser(description="The warehouse MCP server, for one role.")
    parser.add_argument("--role", choices=sorted(ROLES), required=True)
    parser.add_argument("--warehouse", default="data/dev.duckdb",
                        help="the full warehouse; other roles get its copy without personal data")
    args = parser.parse_args()
    build_server(args.role, args.warehouse).run("stdio")


if __name__ == "__main__":
    main()
