"""Proposed actions wait for a person, and only approved ones reach the actions server.

The model never has a tool that writes. These tests check the pause after a report, that a
decision sends exactly the approved actions with who approved them, that actions keep waiting
while more questions are asked, that ending the session sends only what's approved then and
drops the rest, and that a pause saved to SQLite survives reopening the session.
"""

import pytest

from agent import costs
from agent.graph import AgentConfig, Session
from mcp_servers.actions.store import ActionStore
from tests.fakes import FakeClaude, reply, report

ACTIONS = [
    {"type": "ticket", "title": "Remove duplicate payments", "reason": "159 rows loaded twice"},
    {"type": "alert", "title": "Shop RS-010 cost outlier", "reason": "Costs 60% above peers"},
]


@pytest.fixture(autouse=True)
def ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(costs, "LEDGER", tmp_path / "spend.jsonl")
    monkeypatch.delenv("SPEND_LIMIT_USD", raising=False)


@pytest.fixture
def config(guarded_warehouse, tmp_path):
    return AgentConfig(warehouse=guarded_warehouse, transport="inprocess",
                       actions_store=tmp_path / "actions.jsonl",
                       checkpoints=tmp_path / "checkpoints.sqlite")


def open_session(config, tmp_path, fake, session_id=None, role="head_of_claims") -> Session:
    return Session(role, config=config, client=fake, trace_dir=tmp_path / "traces",
                   session_id=session_id)


def test_only_approved_actions_are_created(config, tmp_path):
    with open_session(config, tmp_path, FakeClaude(reply(report(actions=ACTIONS)))) as chat:
        answer = chat.ask("Why did paid amounts jump in early March?")
        assert answer.pending_actions == ACTIONS
        assert ActionStore(config.actions_store).list() == []  # nothing before a decision

        decisions = chat.decide(answer.run_id, [1])

    assert [d["status"] for d in decisions] == ["rejected", "created"]
    created = ActionStore(config.actions_store).list()
    assert len(created) == 1 and created[0]["id"] == decisions[1]["id"]
    assert created[0]["title"] == "Shop RS-010 cost outlier"
    assert created[0]["approved_by"] == "head_of_claims" and created[0]["run_id"] == answer.run_id


def test_actions_keep_waiting_while_more_questions_are_asked(config, tmp_path):
    fake = FakeClaude(reply(report(actions=ACTIONS)), reply(report(actions=ACTIONS[:1])),
                      reply(report()))
    with open_session(config, tmp_path, fake) as chat:
        first = chat.ask("Why did paid amounts jump in early March?")
        second = chat.ask("Which batch was it?")
        third = chat.ask("Thanks. How many claims in Q4 2025?")
        assert third.error is None and third.pending_actions == []
        assert chat.pending == [
            {"run_id": first.run_id, "question": "Why did paid amounts jump in early March?",
             "proposed_actions": ACTIONS},
            {"run_id": second.run_id, "question": "Which batch was it?",
             "proposed_actions": ACTIONS[:1]},
        ]
        assert ActionStore(config.actions_store).list() == []  # nothing sent while waiting

        assert [d["status"] for d in chat.decide(second.run_id, [])] == ["rejected"]
        assert [group["run_id"] for group in chat.pending] == [first.run_id]
        with pytest.raises(ValueError):
            chat.decide(second.run_id, [0])  # already decided
    # The follow-ups still went to the model in the same conversation.
    assert [m["role"] for m in fake.requests[1]["messages"]] == ["user", "assistant", "user"]


def test_ending_the_session_sends_only_what_is_approved_then_and_drops_the_rest(config,
                                                                               tmp_path):
    fake = FakeClaude(reply(report(actions=ACTIONS)), reply(report(actions=ACTIONS)))
    with open_session(config, tmp_path, fake) as chat:
        first = chat.ask("Why did paid amounts jump in early March?")
        second = chat.ask("And in April?")
        decisions = chat.end({first.run_id: [0]})
        assert chat.pending == [] and chat.end() == {}

    assert [d["status"] for d in decisions[first.run_id]] == ["created", "dropped"]
    assert [d["status"] for d in decisions[second.run_id]] == ["dropped", "dropped"]
    created = ActionStore(config.actions_store).list()
    assert [c["title"] for c in created] == ["Remove duplicate payments"]


def test_a_paused_session_can_be_reopened_and_decided(config, tmp_path):
    with open_session(config, tmp_path, FakeClaude(reply(report(actions=ACTIONS)))) as first:
        first.ask("Why did paid amounts jump in early March?")
        session_id = first.session_id

    fake = FakeClaude(reply(report()))
    with open_session(config, tmp_path, fake, session_id=session_id) as reopened:
        [waiting] = reopened.pending
        assert waiting["proposed_actions"] == ACTIONS
        assert [d["status"] for d in reopened.decide(waiting["run_id"], [0, 1])] == \
            ["created", "created"]
        reopened.ask("Thanks. Anything else to check?")
    # The reopened session carried on the same conversation, without a second context block.
    sent = fake.requests[0]["messages"]
    assert len(sent) == 3 and len(sent[-1]["content"]) == 1
    assert len(ActionStore(config.actions_store).list()) == 2


def test_reports_without_actions_dont_pause(config, tmp_path):
    with open_session(config, tmp_path, FakeClaude(reply(report()))) as chat:
        assert chat.ask("How many claims in Q4 2025?").pending_actions == []
        assert chat.pending == []
