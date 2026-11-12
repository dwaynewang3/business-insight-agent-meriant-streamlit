"""Command line: start the actions MCP server on stdio.

    uv run python -m mcp_servers.actions [--store logs/actions.jsonl]

With ACTIONS_GITHUB_REPO and ACTIONS_GITHUB_TOKEN set, each action is also opened as a GitHub
issue (mcp_servers/actions/github.py).
"""

import argparse
from pathlib import Path

from .github import GitHubIssues
from .server import build_server


def main() -> None:
    parser = argparse.ArgumentParser(description="The actions MCP server.")
    parser.add_argument("--store", type=Path, help="JSON Lines file for tickets and alerts")
    build_server(parser.parse_args().store, GitHubIssues.from_env()).run("stdio")


if __name__ == "__main__":
    main()
