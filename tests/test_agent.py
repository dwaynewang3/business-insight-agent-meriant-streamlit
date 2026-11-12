"""The minimal agent, run against a scripted stand-in for Claude, so no API calls are made.

These tests check the loop rather than the model: the requests it sends (settings, caching,
an append-only conversation), how it runs queries and returns errors, the caps on queries
and cost, follow-up questions, and what it records.
"""

import json

import pytest

from agent import costs
from agent.costs import call_cost, price_of
from agent.graph import AgentConfig, Limits, Session, SessionFull
from agent.llm import FALLBACK_BETA
from agent.report import REPORT_SCHEMA, ReportError, parse_report
from tests.fakes import FakeClaude, reply, report, sql_call, thinking


@pytest.fixture
def warehouse(guarded_warehouse):
    return guarded_warehouse


@pytest.fixture(autouse=True)
def ledger(tmp_path, monkeypatch):
    path = tmp_path / "spend.jsonl"
    monkeypatch.setattr(costs, "LEDGER", path)
    monkeypatch.delenv("SPEND_LIMIT_USD", raising=False)
    return path


def session(warehouse, tmp_path, fake, role="head_of_claims", limits=None,
            toolset="full") -> Session:
    config = AgentConfig(warehouse=warehouse, limits=limits or Limits(), toolset=toolset,
                         transport="inprocess")
    return Session(role, config=config, client=fake, trace_dir=tmp_path / "traces")


def test_answers_a_question_with_one_query(warehouse, tmp_path):
    fake = FakeClaude(
        reply(thinking(), sql_call("SELECT count(*) AS claims FROM claims"),
              stop_reason="tool_use"),
        reply(thinking(), report("SELECT count(*) AS claims FROM claims")),
    )
    answer = session(warehouse, tmp_path, fake).ask("How many claims are there?")

    assert answer.error is None
    assert answer.report["answer_sql"] == "SELECT count(*) AS claims FROM claims"
    assert [call["rows"] for call in answer.tool_calls] == [1]
    assert answer.models_served == ["claude-sonnet-5-5"] and not answer.fell_back
    # The query result went back as the tool result, before the second call.
    result = fake.requests[1]["messages"][-1]["content"][0]
    assert result["type"] == "tool_result" and result["is_error"] is False
    assert json.loads(result["content"])["columns"] == ["claims"]


def test_requests_use_the_planned_settings(warehouse, tmp_path):
    fake = FakeClaude(reply(report()))
    session(warehouse, tmp_path, fake).ask("How many claims are there?")
    params = fake.requests[0]

    assert params["model"] == "claude-sonnet-5-5"
    assert params["thinking"]["type"] == "adaptive"
    assert params["output_config"]["effort"] == "medium"
    assert params["output_config"]["format"]["schema"] == REPORT_SCHEMA
    assert params["cache_control"] == {"type": "ephemeral"}  # the growing conversation
    assert params["system"][-1]["cache_control"] == {"type": "ephemeral"}  # shared by sessions
    assert params["fallbacks"] == "default" and params["betas"] == [FALLBACK_BETA]
    assert "tool_choice" not in params  # forcing a tool is rejected on Sonnet 5.5
    names = [tool["name"] for tool in params["tools"]]
    assert names == sorted(names) == ["check_claim_compliance", "check_data_quality",
                                      "describe_table", "get_metric", "get_policy_clause",
                                      "query_metric", "run_sql", "search_catalog",
                                      "search_policies"]
    not_strict = ("check_claim_compliance", "get_policy_clause", "search_policies")
    for tool in params["tools"]:  # closed schemas; strict except the policy tools (grammar size)
        assert tool["input_schema"]["additionalProperties"] is False
        assert tool["strict"] is (tool["name"] not in not_strict)


def test_role_and_extract_date_go_in_the_first_message_not_the_system_prompt(warehouse, tmp_path):
    fake = FakeClaude(reply(report()), reply(report()))
    chat = session(warehouse, tmp_path, fake, role="actuarial_analyst")
    chat.ask("First question")
    chat.ask("Follow-up")

    first = fake.requests[0]["messages"][0]["content"]
    assert "Actuarial analyst" in first[0]["text"] and "2026-09-30" in first[0]["text"]
    assert first[1]["text"] == "First question"
    follow_up = fake.requests[1]["messages"][-1]["content"]
    assert [block["text"] for block in follow_up] == ["Follow-up"]
    assert "Actuarial analyst" not in fake.requests[0]["system"][0]["text"]


def test_follow_ups_extend_the_same_conversation_without_editing_it(warehouse, tmp_path):
    fake = FakeClaude(
        reply(thinking(), sql_call("SELECT 1 AS x"), stop_reason="tool_use"),
        reply(thinking(), report()),
        reply(report()),
    )
    chat = session(warehouse, tmp_path, fake)
    chat.ask("Loss ratio by product in 2025?")
    chat.ask("Now break that down by state.")

    first_turn, second_turn = fake.requests[1]["messages"], fake.requests[2]["messages"]
    assert second_turn[: len(first_turn)] == first_turn  # append-only
    # The assistant's thinking blocks went back unchanged.
    assert second_turn[1]["content"][0] == thinking()
    # The system prompt and tools never change, so the prompt cache keeps working.
    assert len({json.dumps([r["system"], r["tools"]]) for r in fake.requests}) == 1


def test_a_rejected_query_goes_back_to_the_model_as_an_error(warehouse, tmp_path):
    fake = FakeClaude(
        reply(sql_call("DELETE FROM claims"), stop_reason="tool_use"),
        reply(sql_call("SELECT * FROM read_text('.env')", "tu_2"), stop_reason="tool_use"),
        reply(report(None, status="declined")),
    )
    answer = session(warehouse, tmp_path, fake).ask("Delete the claims")

    errors = [r["messages"][-1]["content"][0] for r in fake.requests[1:]]
    assert all(e["is_error"] for e in errors)
    assert "Only SELECT queries are allowed" in errors[0]["content"]
    assert answer.report["status"] == "declined"
    assert all("error" in call for call in answer.tool_calls)


def test_the_model_is_asked_to_report_once_the_query_budget_is_used(warehouse, tmp_path):
    fake = FakeClaude(
        reply(sql_call("SELECT 1 AS x"), stop_reason="tool_use"),
        reply(sql_call("SELECT 2 AS x", "tu_2"), stop_reason="tool_use"),
        reply(report()),
    )
    limits = Limits(max_tool_calls=2, hard_tool_calls=4)
    answer = session(warehouse, tmp_path, fake, limits=limits).ask("Question")

    first, second = (r["messages"][-1]["content"] for r in fake.requests[1:])
    assert [b["type"] for b in first] == ["tool_result"]
    assert [b["type"] for b in second] == ["tool_result", "text"]
    assert "Write the report now" in second[-1]["text"]
    assert answer.error is None


def test_a_question_stops_at_the_hard_query_cap_and_follow_ups_still_work(warehouse, tmp_path):
    fake = FakeClaude(
        reply(sql_call("SELECT 1 AS x"), stop_reason="tool_use"),
        reply(sql_call("SELECT 2 AS x", "tu_2"), stop_reason="tool_use"),
        reply(report()),
    )
    chat = session(warehouse, tmp_path, fake, limits=Limits(max_tool_calls=1, hard_tool_calls=1))
    answer = chat.ask("Question")
    assert answer.report is None and "kept querying" in answer.error
    assert len(answer.tool_calls) == 1

    assert chat.ask("Follow-up").error is None
    # The unanswered tool call was closed with an error result before the follow-up.
    closing = fake.requests[2]["messages"][-2]["content"][0]
    assert closing["tool_use_id"] == "tu_2" and closing["is_error"] is True


def test_a_refusal_ends_the_question_without_breaking_the_session(warehouse, tmp_path):
    fake = FakeClaude(reply(stop_reason="refusal"), reply(report()))
    chat = session(warehouse, tmp_path, fake)
    assert "declined to answer" in chat.ask("Question").error
    assert chat.ask("Another question").error is None
    roles = [m["role"] for m in fake.requests[1]["messages"]]
    assert roles == ["user", "user"]  # the refused turn left nothing behind


def test_a_cut_off_response_is_an_error_not_a_wrong_answer(warehouse, tmp_path):
    fake = FakeClaude(reply({"type": "text", "text": '{"status": "ans'}, stop_reason="max_tokens"))
    answer = session(warehouse, tmp_path, fake).ask("Question")
    assert answer.report is None and "token limit" in answer.error


def test_no_call_is_made_once_the_spend_limit_is_reached(warehouse, tmp_path, ledger, monkeypatch):
    costs.record_spend({"cost_usd": 1.5})
    monkeypatch.setenv("SPEND_LIMIT_USD", "1.5")
    fake = FakeClaude()
    answer = session(warehouse, tmp_path, fake).ask("Question")
    assert fake.requests == [] and "SPEND_LIMIT_USD" in answer.error


def test_a_question_stops_at_its_cost_cap(warehouse, tmp_path):
    expensive = {"input_tokens": 100_000, "output_tokens": 0}  # $0.20 a call
    fake = FakeClaude(*[reply(sql_call("SELECT 1 AS x", f"tu_{i}"), stop_reason="tool_use",
                              usage=expensive) for i in range(5)])
    answer = session(warehouse, tmp_path, fake, limits=Limits(max_cost_usd=0.5)).ask("Question")
    assert "cost cap" in answer.error
    assert len(fake.requests) == 3 and answer.cost_usd == pytest.approx(0.6)


def test_every_call_is_recorded_in_the_spend_ledger_and_the_trace(warehouse, tmp_path, ledger):
    fake = FakeClaude(reply(sql_call("SELECT 1 AS x"), stop_reason="tool_use"), reply(report()))
    chat = session(warehouse, tmp_path, fake)
    answer = chat.ask("Question")

    entries = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert len(entries) == 2 and costs.spent(ledger) == pytest.approx(answer.cost_usd)
    assert {e["run_id"] for e in entries} == {answer.run_id}
    events = [json.loads(line)["event"] for line in chat.tracer.path.read_text().splitlines()]
    assert events == ["session_start", "question", "model_call", "tool_call", "model_call",
                      "answer"]


def test_a_fallback_model_is_flagged(warehouse, tmp_path):
    fake = FakeClaude(reply(report(), model="claude-sonnet-5"))
    answer = session(warehouse, tmp_path, fake).ask("Question")
    assert answer.fell_back and answer.models_served == ["claude-sonnet-5"]


def test_cost_comes_from_token_counts_and_each_models_prices():
    usage = {"input_tokens": 1_000_000, "output_tokens": 1_000_000,
             "cache_read_input_tokens": 1_000_000, "cache_creation_input_tokens": 1_000_000}
    assert call_cost("claude-sonnet-5-5", usage) == pytest.approx(2 + 10 + 0.2 + 2.5)
    assert price_of("claude-sonnet-5") == costs.PRICES["claude-sonnet-5"]
    assert price_of("claude-opus-5-5") == costs.PRICES["claude-opus-5-5"]
    assert price_of("some-new-model") == costs.UNKNOWN_MODEL_PRICE  # never under-counted
    # A turn served by a fallback model is priced per iteration.
    fallback = {"input_tokens": 0, "output_tokens": 0, "iterations": [
        {"type": "message", "model": "claude-sonnet-5-5", "input_tokens": 1_000_000,
         "output_tokens": 0},
        {"type": "fallback_message", "model": "claude-opus-4-8", "input_tokens": 1_000_000,
         "output_tokens": 0},
    ]}
    assert call_cost("claude-sonnet-5-5", fallback) == pytest.approx(2 + 5)


def test_parse_report_rejects_a_missing_or_partial_report():
    assert parse_report(report()["text"])["status"] == "answered"
    for text in ["", '{"status": "ans', '{"status": "maybe"}', '{"status": "answered"}']:
        with pytest.raises(ReportError):
            parse_report(text)


def test_progress_events_reach_a_listener_while_the_question_runs(warehouse, tmp_path):
    fake = FakeClaude(reply(sql_call("SELECT 1 AS x"), stop_reason="tool_use"), reply(report()))
    seen = []
    chat = session(warehouse, tmp_path, fake)
    chat.ask("Question", on_event=lambda event: seen.append(event["event"]))
    assert seen == ["question", "model_call", "tool_call", "model_call", "answer"]
    assert chat.tracer.listeners == []  # removed afterwards


@pytest.mark.parametrize("model, effort", [("claude-sonnet-5-5", "low"),
                                           ("claude-opus-5-5", "medium"),
                                           ("claude-haiku-4-5", None)])
def test_each_experiment_2_model_gets_the_settings_it_accepts(model, effort):
    from agent.llm import ModelSettings, request_params

    params = request_params(ModelSettings(model=model, effort=effort or "medium"), "system",
                            [], [])
    if model.startswith("claude-haiku"):
        assert params["thinking"]["type"] == "enabled"
        assert 1024 <= params["thinking"]["budget_tokens"] < params["max_tokens"]
        assert "effort" not in params["output_config"] and "fallbacks" not in params
    else:
        assert params["thinking"]["type"] == "adaptive"
        assert params["output_config"]["effort"] == effort and params["fallbacks"] == "default"
    assert params["output_config"]["format"]["type"] == "json_schema"


def test_experiment_tool_sets_leave_out_the_policy_tools(warehouse, tmp_path):
    for toolset, expected in (("sql_only", ["run_sql"]),
                              ("semantic_off", ["check_data_quality", "describe_table",
                                                "run_sql"])):
        with session(warehouse, tmp_path, FakeClaude(), toolset=toolset) as chat:
            assert chat.toolbox.names == expected


def report_with_numbers(sql: str, *values: float) -> dict:
    """A report with one finding whose key numbers are `values`, backed by `sql`."""
    body = json.loads(report()["text"])
    body["findings"] = [{"claim": "c", "evidence_sql": sql, "confidence": "high",
                         "key_numbers": [{"label": f"n{i}", "value": v, "unit": "claims"}
                                         for i, v in enumerate(values)]}]
    return {"type": "text", "text": json.dumps(body)}


def test_confirmed_key_numbers_go_out_without_another_call(warehouse, tmp_path):
    fake = FakeClaude(reply(report_with_numbers("SELECT 7 AS n", 7)))
    answer = session(warehouse, tmp_path, fake).ask("Question")
    assert len(fake.requests) == 1
    assert answer.numbers == {"checked": 1, "confirmed": 1, "unconfirmed": []}


def test_unconfirmed_key_numbers_go_back_to_the_model_once(warehouse, tmp_path):
    fake = FakeClaude(reply(report_with_numbers("SELECT 7 AS n", 7, 9)),
                      reply(report_with_numbers("SELECT 7 AS n, 9 AS m", 7, 9)))
    answer = session(warehouse, tmp_path, fake).ask("Question")

    request = fake.requests[1]["messages"][-1]
    assert request["role"] == "user" and "Finding 1, n1: 9 claims" in request["content"][0]["text"]
    assert answer.report["findings"][0]["evidence_sql"] == "SELECT 7 AS n, 9 AS m"
    assert answer.numbers["confirmed"] == 2 and answer.error is None


def test_numbers_still_unconfirmed_after_the_repair_are_reported_not_retried(warehouse, tmp_path):
    fake = FakeClaude(*[reply(report_with_numbers("SELECT 7 AS n", 7, 9)) for _ in range(2)])
    answer = session(warehouse, tmp_path, fake).ask("Question")
    assert len(fake.requests) == 2
    assert [n["label"] for n in answer.numbers["unconfirmed"]] == ["n1"]


def test_a_failed_repair_keeps_the_checked_report(warehouse, tmp_path):
    fake = FakeClaude(reply(report_with_numbers("SELECT 7 AS n", 9)), reply(stop_reason="refusal"))
    answer = session(warehouse, tmp_path, fake).ask("Question")
    assert answer.error is None and answer.report["findings"][0]["key_numbers"][0]["value"] == 9
    assert answer.numbers["unconfirmed"][0]["reason"] == "Not in the result of its finding's SQL."


def test_a_session_holds_a_set_number_of_questions(warehouse, tmp_path):
    config = AgentConfig(warehouse=warehouse, transport="inprocess", max_questions=2)
    with Session("head_of_claims", config=config, client=FakeClaude(reply(report()),
                 reply(report())), trace_dir=tmp_path / "traces") as chat:
        assert chat.questions_left == 2
        chat.ask("First")
        chat.ask("Second")
        assert chat.questions_left == 0
        with pytest.raises(SessionFull):
            chat.ask("Third")
