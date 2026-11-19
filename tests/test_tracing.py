"""What goes to Langfuse: one trace per question with its session, a generation per Claude
call with tokens and cost, and a span per tool call without any result rows.

A real Langfuse client writes to an in-memory exporter, so nothing leaves the machine.
"""

import json
import uuid

import pytest
from langfuse import Langfuse
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from agent import costs
from agent.graph import AgentConfig, Session
from tests.fakes import FakeClaude, reply, report, sql_call


@pytest.fixture(autouse=True)
def ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(costs, "LEDGER", tmp_path / "spend.jsonl")


@pytest.fixture
def exported():
    exporter = InMemorySpanExporter()  # Langfuse's own span processor writes to it
    provider = TracerProvider()
    # Langfuse keeps one client per public key, so each test gets its own key and exporter.
    client = Langfuse(public_key=f"pk-test-{uuid.uuid4().hex}", secret_key="sk-test",
                      base_url="http://localhost:9",
                      tracer_provider=provider, span_exporter=exporter, flush_at=1)
    yield client, exporter
    provider.shutdown()


def test_a_question_becomes_one_trace_with_its_calls(guarded_warehouse, tmp_path, exported):
    client, exporter = exported
    fake = FakeClaude(
        reply(sql_call("SELECT full_name, state FROM policyholders LIMIT 2"),
              stop_reason="tool_use"),
        reply(report()),
    )
    config = AgentConfig(warehouse=guarded_warehouse, transport="inprocess")
    with Session("fraud_team_lead", config, client=fake, trace_dir=tmp_path,
                 langfuse=client) as chat:
        answer = chat.ask("Who are two policyholders?")

    spans = {span.name: span for span in exporter.get_finished_spans()}
    assert {"question", "claude", "run_sql"} <= set(spans)
    question = dict(spans["question"].attributes)
    assert chat.session_id in json.dumps(question)
    generation = dict(spans["claude"].attributes)
    assert str(answer.model_calls[0]["cost_usd"]) in json.dumps(generation)
    # The query went out, but none of its result rows did.
    sent = json.dumps({name: dict(span.attributes) for name, span in spans.items()})
    assert "SELECT full_name" in sent
    tool_result = chat.messages[2]["content"][0]["content"]
    rows = json.loads(tool_result)["rows"]
    assert rows and all(name not in sent for name, _ in rows)


def test_names_and_contact_details_are_masked_in_langfuse_but_kept_locally(
        guarded_warehouse, dev, tmp_path, exported):
    client, exporter = exported
    name, email = dev.execute("SELECT full_name, email FROM policyholders LIMIT 1").fetchone()
    question = f"What do we know about {name}? Their email is {email}, phone 0412 345 678."
    body = json.loads(report()["text"]) | {"answer": f"{name} has one open claim."}
    fake = FakeClaude(reply({"type": "text", "text": json.dumps(body)}))
    config = AgentConfig(warehouse=guarded_warehouse, transport="inprocess")
    with Session("fraud_team_lead", config, client=fake, trace_dir=tmp_path,
                 langfuse=client) as chat:
        answer = chat.ask(question)
        chat.feedback(answer, helpful=False, comment=f"{name} has two claims, not one.")

    sent = json.dumps([dict(span.attributes) for span in exporter.get_finished_spans()])
    assert name not in sent and email not in sent and "0412 345 678" not in sent
    assert "[name] has one open claim" in sent and "[email]" in sent and "[phone]" in sent
    local = (tmp_path / f"{chat.session_id}.jsonl").read_text()
    assert name in local and email in local  # the local trace keeps the full text


ACTIONS = [
    {"type": "ticket", "title": "Remove duplicate payments", "reason": "159 rows loaded twice"},
    {"type": "alert", "title": "Shop RS-010 cost outlier", "reason": "Costs 60% above peers"},
]


def test_approval_decisions_are_traced_in_the_same_session(guarded_warehouse, tmp_path,
                                                           exported):
    client, exporter = exported
    fake = FakeClaude(reply(report(actions=ACTIONS)), reply(report(actions=ACTIONS)),
                      reply(report()))
    config = AgentConfig(warehouse=guarded_warehouse, transport="inprocess",
                         actions_store=tmp_path / "actions.jsonl")
    with Session("head_of_claims", config, client=fake, trace_dir=tmp_path,
                 langfuse=client) as chat:
        first = chat.ask("Why did paid amounts jump in early March?")
        chat.decide(first.run_id, [1])
        chat.ask("And in April?")  # its actions are left pending...
        chat.ask("Thanks.")  # ...through the next question...
        chat.end()  # ...until the session ends, which drops them and is traced too

    spans = exporter.get_finished_spans()
    approvals = [s for s in spans if s.name == "approval"]
    assert len(approvals) == 2
    sent = [json.dumps(dict(s.attributes)) for s in approvals]
    assert all(chat.session_id in text for text in sent)
    assert first.run_id in sent[0]  # linked to the question it decides on
    assert '\\"status\\": \\"created\\"' in sent[0] and "rejected" in sent[0]
    assert "The session ended" in sent[1] and "dropped" in sent[1]
    # The created alert is a child of the first approval; nothing was created in the second.
    created = [s for s in spans if s.name.startswith("create_")]
    assert [s.name for s in created] == ["create_alert"]
    assert created[0].parent.span_id == approvals[0].context.span_id


def test_feedback_is_kept_locally_and_scored_on_the_questions_trace(guarded_warehouse, tmp_path,
                                                                    exported, monkeypatch):
    client, _ = exported
    scores = []
    monkeypatch.setattr(client, "create_score", lambda **score: scores.append(score))
    config = AgentConfig(warehouse=guarded_warehouse, transport="inprocess")
    with Session("head_of_claims", config, client=FakeClaude(reply(report())),
                 trace_dir=tmp_path / "traces", langfuse=client) as chat:
        answer = chat.ask("How many claims in Q4 2025?")
        chat.feedback(answer, helpful=False, comment="It counted by report date.")
        chat.feedback(answer, helpful=True)  # changed their mind: a second line

    down, up = [json.loads(line)
                for line in (tmp_path / "feedback.jsonl").read_text().splitlines()]
    assert down["run_id"] == answer.run_id and down["helpful"] is False
    assert down["question"] == "How many claims in Q4 2025?" and down["role"] == "head_of_claims"
    assert down["comment"] == "It counted by report date." and down["version"] == chat.version
    assert up["helpful"] is True and up["comment"] is None
    trace = (tmp_path / "traces" / f"{chat.session_id}.jsonl").read_text()
    assert trace.count('"event": "feedback"') == 2
    # Both ratings are scores on the question's own Langfuse trace.
    assert [(s["name"], s["value"], s["comment"]) for s in scores] == [
        ("user_feedback", 0, "It counted by report date."), ("user_feedback", 1, None)]
    assert scores[0]["trace_id"] and scores[0]["trace_id"] == scores[1]["trace_id"]
