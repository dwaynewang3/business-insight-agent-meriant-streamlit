"""Tickets and alerts, stored locally in a JSON Lines file.

The file is the record of what was created: every action keeps who approved it and which
answer proposed it, so it can be traced back. With a GitHub repository configured
(mcp_servers/actions/github.py), each action is also opened there as an issue, standing in
for a real ticketing or alerting system (Jira, ServiceNow, PagerDuty).
"""

import json
import time
from pathlib import Path

ACTIONS_FILE = Path("logs/actions.jsonl")
KINDS = {"ticket": "TCK", "alert": "ALR"}


class ActionStore:
    def __init__(self, path: Path | None = None, issues=None):
        self.path = path or ACTIONS_FILE
        self.issues = issues  # a GitHubIssues, or None to store locally only

    def create(self, kind: str, title: str, reason: str, evidence_sql: list[str],
               approved_by: str, run_id: str) -> dict:
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {', '.join(KINDS)}, not {kind!r}.")
        if not title.strip() or not approved_by.strip():
            raise ValueError("An action needs a title and the role that approved it.")
        existing = self.list(kind)
        action = {
            "id": f"{KINDS[kind]}-{len(existing) + 1:04d}",
            "kind": kind,
            "title": title.strip(),
            "reason": reason.strip(),
            "evidence_sql": evidence_sql,
            "approved_by": approved_by,
            "run_id": run_id,
            "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "status": "open",
        }
        if self.issues is not None:
            # The issue first: if it can't be opened, nothing is recorded as created.
            issue = self.issues.open(action)
            action |= {"issue": issue["number"], "url": issue["url"]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as out:
            out.write(json.dumps(action) + "\n")
        return action

    def list(self, kind: str | None = None) -> list[dict]:
        if not self.path.exists():
            return []
        actions = [json.loads(line) for line in self.path.read_text().splitlines() if line]
        return [a for a in actions if kind is None or a["kind"] == kind]
