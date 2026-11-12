"""Approved actions as GitHub issues: off unless a repository is set, the issue is opened
before anything is recorded, and only the actions server's process gets the token.

A stand-in for GitHub's API receives the requests, so nothing leaves the machine.
"""

import json
import urllib.error

import pytest

from agent import costs
from agent.graph import AgentConfig, Session
from agent.tools import McpToolbox, actions_server
from mcp_servers.actions.github import REPO_VAR, TOKEN_VAR, GitHubIssues
from mcp_servers.actions.server import build_server
from mcp_servers.actions.store import ActionStore
from tests.fakes import FakeClaude, reply, report

ALERT = {"title": "Shop RS-010 cost outlier", "reason": "Costs 60% above peers",
         "evidence_sql": ["SELECT 1", "SELECT 2"], "approved_by": "fraud_team_lead",
         "run_id": "r-abc"}


class FakeGitHub:
    """Records each request and answers like GitHub's "create an issue"."""

    def __init__(self, fail: Exception | None = None):
        self.requests, self.fail = [], fail

    def __call__(self, request, timeout):
        self.requests.append(request)
        if self.fail:
            raise self.fail
        number = len(self.requests)
        return json.dumps({"number": number,
                           "html_url": f"https://github.com/acme/tickets/issues/{number}"}).encode()


def test_an_action_becomes_an_issue_with_its_reason_approver_and_evidence(tmp_path):
    github = FakeGitHub()
    store = ActionStore(tmp_path / "actions.jsonl",
                        GitHubIssues("acme/tickets", "secret-token", send=github))
    created = store.create("alert", **ALERT)

    assert created["issue"] == 1 and created["url"].endswith("/acme/tickets/issues/1")
    assert store.list() == [created]  # the local record keeps the link
    [request] = github.requests
    assert request.full_url == "https://api.github.com/repos/acme/tickets/issues"
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == "Bearer secret-token"
    sent = json.loads(request.data)
    assert sent["title"] == ALERT["title"] and sent["labels"] == ["alert"]
    for part in ("Costs 60% above peers", "`fraud_team_lead`", "`r-abc`", "ALR-0001",
                 "```sql\nSELECT 2\n```"):
        assert part in sent["body"]
    assert "secret-token" not in sent["body"]


def test_nothing_is_recorded_when_github_refuses_the_issue(tmp_path):
    refused = urllib.error.HTTPError("https://api.github.com", 403, "Forbidden", None, None)
    store = ActionStore(tmp_path / "actions.jsonl",
                        GitHubIssues("acme/tickets", "secret-token", send=FakeGitHub(refused)))
    with pytest.raises(ValueError, match="403 Forbidden") as failure:
        store.create("ticket", **ALERT)
    assert "secret-token" not in str(failure.value)
    assert store.list() == []


def test_the_server_reports_the_issue_or_the_failure(tmp_path):
    issues = GitHubIssues("acme/tickets", "secret-token", send=FakeGitHub())
    toolbox = McpToolbox(build_server(tmp_path / "actions.jsonl", issues))
    try:
        created = toolbox.call("create_ticket", ALERT)
        assert not created.is_error and json.loads(created.content)["issue"] == 1
        issues._send = FakeGitHub(urllib.error.URLError("no route"))
        failed = toolbox.call("create_ticket", ALERT)
        assert failed.is_error and "couldn't be reached" in failed.content
    finally:
        toolbox.close()
    assert len(ActionStore(tmp_path / "actions.jsonl").list()) == 1


def test_github_is_off_unless_a_repository_is_set(monkeypatch):
    monkeypatch.delenv(REPO_VAR, raising=False)
    assert GitHubIssues.from_env() is None
    monkeypatch.setenv(REPO_VAR, "acme/tickets")
    monkeypatch.setenv(TOKEN_VAR, "")
    with pytest.raises(ValueError, match=TOKEN_VAR):  # a repository without a token is a mistake
        GitHubIssues.from_env()
    monkeypatch.setenv(TOKEN_VAR, "secret-token")
    assert GitHubIssues.from_env().repo == "acme/tickets"
    with pytest.raises(ValueError, match="owner/name"):
        GitHubIssues("https://github.com/acme/tickets", "secret-token")


def test_only_the_actions_server_process_gets_the_github_settings(monkeypatch):
    monkeypatch.delenv(REPO_VAR, raising=False)
    monkeypatch.delenv(TOKEN_VAR, raising=False)
    assert actions_server(None).env is None
    monkeypatch.setenv(REPO_VAR, "acme/tickets")
    monkeypatch.setenv(TOKEN_VAR, "secret-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-for-the-server")
    assert actions_server(None).env == {REPO_VAR: "acme/tickets", TOKEN_VAR: "secret-token"}


def test_an_approved_action_comes_back_with_its_issue_link(guarded_warehouse, tmp_path,
                                                           monkeypatch):
    monkeypatch.setattr(costs, "LEDGER", tmp_path / "spend.jsonl")
    issues = GitHubIssues("acme/tickets", "secret-token", send=FakeGitHub())
    monkeypatch.setattr("agent.graph.actions_server",
                        lambda store, transport: build_server(store, issues))
    proposed = [{"type": "alert", "title": ALERT["title"], "reason": ALERT["reason"]}]
    config = AgentConfig(warehouse=guarded_warehouse, transport="inprocess",
                         actions_store=tmp_path / "actions.jsonl")
    with Session("fraud_team_lead", config, client=FakeClaude(reply(report(actions=proposed))),
                 trace_dir=tmp_path / "traces") as chat:
        answer = chat.ask("Is any repair shop an outlier on cost?")
        [decision] = chat.decide(answer.run_id, [0])
    assert decision["status"] == "created" and decision["id"] == "ALR-0001"
    assert decision["url"] == "https://github.com/acme/tickets/issues/1"
