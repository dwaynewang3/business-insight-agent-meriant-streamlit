"""Approved tickets and alerts as GitHub issues, when a repository is configured.

Off by default: actions are only stored locally. With ACTIONS_GITHUB_REPO (owner/name) and
ACTIONS_GITHUB_TOKEN set, each approved action is first opened as an issue in that repository,
and the local record keeps the issue's number and URL. GitHub Issues stands in for the
customer's tracker (Jira, ServiceNow): the same place in the flow, behind the same approval
step, so the model still has no tool that writes.

An issue carries the action's title, reason and evidence SQL, which the model wrote from what
it queried, so point this at a private repository. The token needs only "Issues: read and
write" on that one repository (a fine-grained personal access token).
"""

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable

API = "https://api.github.com"
REPO_VAR, TOKEN_VAR = "ACTIONS_GITHUB_REPO", "ACTIONS_GITHUB_TOKEN"
ENV_VARS = (REPO_VAR, TOKEN_VAR)  # passed on to the actions server's process
_REPO = re.compile(r"[\w.-]+/[\w.-]+")


def _send(request: urllib.request.Request, timeout: float) -> bytes:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


class GitHubIssues:
    def __init__(self, repo: str, token: str,
                 send: Callable[[urllib.request.Request, float], bytes] = _send,
                 timeout: float = 20.0):
        if not _REPO.fullmatch(repo):
            raise ValueError(f"{REPO_VAR} must look like owner/name, not {repo!r}.")
        if not token:
            raise ValueError(f"{TOKEN_VAR} is needed to open issues in {repo}.")
        self.repo, self._token, self._send, self.timeout = repo, token, send, timeout

    @classmethod
    def from_env(cls) -> "GitHubIssues | None":
        """The repository named in the environment, or None when it isn't set."""
        repo = os.environ.get(REPO_VAR, "").strip()
        return cls(repo, os.environ.get(TOKEN_VAR, "").strip()) if repo else None

    def open(self, action: dict) -> dict:
        """Open one approved action as an issue. Returns its number and URL; raises ValueError
        if GitHub doesn't create it, so the action is reported as failed, not created."""
        request = urllib.request.Request(
            f"{API}/repos/{self.repo}/issues",
            data=json.dumps({"title": action["title"], "body": issue_body(action),
                             "labels": [action["kind"]]}).encode(),
            headers={"Authorization": f"Bearer {self._token}",
                     "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28",
                     "Content-Type": "application/json",
                     "User-Agent": "business-insights-agent"},
            method="POST")
        try:
            created = json.loads(self._send(request, self.timeout))
        except urllib.error.HTTPError as error:
            raise ValueError(f"GitHub didn't create the issue in {self.repo}: "
                             f"{error.code} {error.reason}.") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise ValueError(f"GitHub couldn't be reached: {error}.") from error
        return {"number": created["number"], "url": created["html_url"]}


def issue_body(action: dict) -> str:
    """What a person opening the issue needs: why, who approved it, and the SQL to check."""
    lines = [action["reason"] or "No reason given.", "",
             f"- Approved by: `{action['approved_by']}`",
             f"- Proposed by the Business Insights Agent in run `{action['run_id']}` "
             f"(local record {action['id']})"]
    for number, sql in enumerate(action["evidence_sql"], start=1):
        lines += ["", f"**Evidence query {number}**", "", "```sql", sql.strip(), "```"]
    return "\n".join(lines)
