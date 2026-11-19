"""The agent: a LangGraph loop that calls Claude, runs the tools it asks for, and ends with a
structured report. Proposed actions wait for a person.

    START -> call_model -> (tool calls?) -> run_tools -> call_model ... -> check_report
          -> (numbers not confirmed?) -> call_model ... -> finish -> END

Each user session is one LangGraph thread, so a follow-up question is appended to the same
conversation and the model can tell what "that" refers to. The message list is append-only:
earlier turns are never edited, which keeps the prompt cache and the thinking blocks valid.
A session holds a set number of questions (10 by default), so its conversation, and the cost
of each question, can't grow without end; after that the user starts a new one.

Every question has caps on tool calls and cost. Near the tool-call cap the model is asked to
write its report with what it has; past the hard caps the question ends with an error. A call
that repeats an earlier one in the same question, with the same input, isn't run again: the
model gets the earlier result back.

Before a report goes out, code re-runs each finding's SQL and checks that its key numbers are
in the result (agent/key_numbers.py). Numbers it can't confirm go back to the model once, to
fix the query or the number. If that repair fails (a cap, an API error), the first report
stands; either way the answer carries the check's result, so the UI can mark what's
unconfirmed.

The model has no tool that writes. When a report proposes tickets or alerts, they go to a
small approval graph on a thread of their own, which pauses until a person decides (LangGraph
interrupt). The conversation itself never pauses, so the user can keep asking questions while
actions wait. Each pause is saved by the checkpointer, so it survives a UI rerun when the
checkpoints go to SQLite. When the session ends, the user gets one last chance, and anything
still undecided is dropped. Only the actions a person approves are sent, by this code, to the
actions MCP server.
"""

import json
import operator
import os
import sqlite3
import time
import uuid
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, TypedDict

import anthropic
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from mcp_servers.warehouse import Limits as QueryLimits
from mcp_servers.warehouse import reads_no_table, run_query
from mcp_servers.warehouse.access import warehouse_for
from mcp_servers.warehouse.masking import Masker

from . import __version__
from .compliance import ComplianceToolbox, ReviewConfig
from .context import fingerprint, session_context, system_prompt, warehouse_dates
from .costs import SpendLimitReached
from .key_numbers import check_numbers
from .llm import ModelSettings, call_claude, request_params
from .report import REPORT_SCHEMA, ReportError, parse_report
from .tools import (
    POLICY_TOOLS,
    TOOLSETS,
    McpToolbox,
    ToolBelt,
    actions_server,
    policies_server,
    warehouse_server,
)
from .tracing import Tracer, langfuse_client

DEFAULT_WAREHOUSE = Path("data/dev.duckdb")
DEFAULT_POLICY_KB = Path("data/policies.duckdb")
END_NOTE = "The session ended: anything not approved by then was dropped, so it wasn't sent."
# Saved runs showed the model re-running an identical call turn after turn: 181 of 517 calls,
# in half the questions, repeated an earlier one (docs/results.md). Refusing a repeat made the
# model change the query trivially to run it anyway (2026-11-17), so a repeat gets the earlier
# result again, without running it.
REPEAT_NOTE = ("This exact call already ran in this question, and the data hasn't changed, so "
               "here is the same result again. There's no need to re-run a query to check it: "
               "code re-runs every finding's evidence_sql before the answer goes out.\n\n")
TABLELESS_NOTE = ("Not run: this query reads no warehouse table, so its result shows nothing "
                  "about the data. An answer from policy clauses needs no query (answer_sql "
                  "null, evidence_sql empty), and values you already have don't need restating.")
# The number check needs every row, to compare column totals; the model never sees these rows.
CHECK_LIMITS = QueryLimits(max_rows=10_000, max_chars=10_000_000)


class SessionFull(RuntimeError):
    """The session has used its questions; start a new one."""


@dataclass(frozen=True)
class Limits:
    max_tool_calls: int = 20  # past this, the model is asked to write its report
    hard_tool_calls: int = 24  # past this, the question ends with an error
    max_cost_usd: float = 0.50  # per question (DEV_PLAN.md success criteria)
    number_repairs: int = 1  # times a report's unconfirmed key numbers go back to the model
    max_repeats: int = 3  # repeated calls, after which the model is asked to write its report


@dataclass(frozen=True)
class AgentConfig:
    warehouse: Path = DEFAULT_WAREHOUSE  # the full warehouse; most roles get its restricted copy
    settings: ModelSettings = field(default_factory=ModelSettings)
    limits: Limits = field(default_factory=Limits)
    toolset: str = "full"  # a name from agent.tools.TOOLSETS
    transport: str = "stdio"  # how to reach the MCP servers: stdio or inprocess
    checkpoints: Path | None = None  # a SQLite file, so pauses survive restarts; None: memory
    actions_store: Path | None = None  # where approved actions go; None: logs/actions.jsonl
    # The policy knowledge base (`make data`); None leaves out the policy tools. Tests point
    # POLICY_KB at one built with the hash test embedder.
    policies: Path | None = field(
        default_factory=lambda: Path(os.environ.get("POLICY_KB", DEFAULT_POLICY_KB)))
    # How check_claim_compliance reviews a claim: full context, the best measured in B7
    # (docs/compliance_results.md; chosen 2026-10-18). v0 and v1 remain for comparison.
    compliance_variant: str = "full"
    # Questions per session (DEV_PLAN.md section 6): earlier turns come from the prompt cache,
    # but each one still adds to every later request, so a long session gets slow and costly.
    max_questions: int = 10


class AgentState(TypedDict):
    messages: Annotated[list[dict], operator.add]  # the whole conversation, append-only
    asked: Annotated[int, operator.add]  # questions asked in this session
    run_id: str  # one question and its answer
    model_calls: list[dict]  # this question's calls, with tokens, cost and model
    tool_calls: list[dict]  # this question's queries
    stop_reason: str | None
    number_checks: list[dict]  # this question's key-number checks, one per report
    draft: dict | None  # the last report checked, kept if a repair fails
    outcome: dict | None  # {"report", "error", "numbers"}, set when the question ends
    proposals: Annotated[list[str], operator.add]  # run IDs whose reports proposed actions


class ApprovalState(TypedDict):
    run_id: str  # the question whose report proposed the actions
    question: str
    report: dict
    decisions: list[dict] | None  # what happened to each proposed action


@dataclass
class Answer:
    """One question's result: the report (or why there isn't one), and what it took."""

    question: str
    run_id: str
    session_id: str
    report: dict | None
    error: str | None
    cost_usd: float
    seconds: float
    model_calls: list[dict]
    tool_calls: list[dict]
    pending_actions: list[dict] = field(default_factory=list)  # this answer's, waiting
    # The report's key numbers checked against their findings' SQL: checked, confirmed and
    # the unconfirmed ones, after any repair. None when there's no report.
    numbers: dict | None = None

    @property
    def models_served(self) -> list[str]:
        return sorted({call["model_served"] for call in self.model_calls})

    @property
    def fell_back(self) -> bool:
        return any(call["fallback"] for call in self.model_calls)


def _question_cost(state: AgentState) -> float:
    return sum(call["cost_usd"] for call in state["model_calls"])


def repair_request(unconfirmed: list[dict]) -> str:
    """What the model is told when code can't confirm some of its key numbers."""
    lines = [f"- Finding {item['finding'] + 1}, {item['label']}: {item['value']} "
             f"{item['unit'] or ''}".rstrip() + f". {item['reason']}" for item in unconfirmed]
    return (
        "Code re-ran each finding's evidence_sql and couldn't confirm these key numbers in the "
        "cell each one names (its column and row, or the column's total or average, allowing "
        "for rounding):\n"
        + "\n".join(lines)
        + "\n\nFor each one, correct the cell it names, change that finding's evidence_sql so "
        "the cell holds the number, or correct or remove the number. You may run queries. "
        "Then write the whole report again."
    )


def build_graph(
    client: anthropic.Anthropic,
    config: AgentConfig,
    system: str,
    toolbox: ToolBelt | McpToolbox,
    tracer: Tracer,
    checkpointer,
    check: Callable[[dict], dict],
):
    """check: a report's key numbers against their findings' SQL (agent.key_numbers)."""
    settings, limits = config.settings, config.limits

    def call_model(state: AgentState) -> dict:
        if _question_cost(state) >= limits.max_cost_usd:
            return _fail(f"Stopped: this question reached its ${limits.max_cost_usd:.2f} cost cap.")
        params = request_params(settings, system, toolbox.definitions, state["messages"])
        labels = {"session_id": tracer.session_id, "run_id": state["run_id"],
                  "purpose": tracer.purpose}
        with tracer.span("claude", as_type="generation", model=settings.model,
                         model_parameters={"effort": settings.effort}) as generation:
            try:
                message, record = call_claude(client, params, labels)
            except SpendLimitReached as error:
                generation.update(level="ERROR", status_message=str(error))
                return _fail(str(error))
            except anthropic.APIError as error:
                generation.update(level="ERROR", status_message=repr(error))
                tracer.event("api_error", run_id=state["run_id"], error=repr(error))
                return _fail(f"API error: {error}")
            generation.update(
                model=record["model_served"],
                usage_details={"input": record["input_tokens"],
                               "output": record["output_tokens"],
                               "cache_read_input_tokens": record["cache_read_input_tokens"],
                               "cache_creation_input_tokens":
                                   record["cache_creation_input_tokens"]},
                cost_details={"total": record["cost_usd"]},
                output=[{"tool": b.name, "input": b.input} for b in message.content
                        if b.type == "tool_use"] or message.stop_reason,
                metadata={"stop_reason": message.stop_reason, "fallback": record["fallback"],
                          "request_id": record["request_id"]},
            )
        tracer.event("model_call", **record)
        update: dict = {"model_calls": [*state["model_calls"], record],
                        "stop_reason": message.stop_reason}
        if message.stop_reason in ("end_turn", "tool_use"):
            # Thinking blocks go back unchanged, so the conversation stays valid.
            content = [block.to_dict(mode="json") for block in message.content]
            update["messages"] = [{"role": "assistant", "content": content}]
        return update

    def run_tools(state: AgentState) -> dict:
        calls = [b for b in state["messages"][-1]["content"] if b["type"] == "tool_use"]
        done, results, model_calls = list(state["tool_calls"]), [], list(state["model_calls"])
        for call in calls:
            earlier = (_earlier_result(state["messages"], results, call)
                       if any(_same_call(call, made) for made in done) else None)
            if earlier is not None:
                # A read-only snapshot gives the same result again, so the call isn't run.
                record = {"tool": call["name"], "input": call["input"], "repeat": True}
                done.append(record)
                tracer.event("tool_call", run_id=state["run_id"], **record)
                results.append({"type": "tool_result", "tool_use_id": call["id"],
                                "content": REPEAT_NOTE + earlier["content"],
                                "is_error": earlier.get("is_error", False)})
                continue
            if call["name"] == "run_sql" and reads_no_table(call["input"].get("sql", "")):
                # Placeholders such as SELECT 1, written to give a policy answer a query.
                record = {"tool": call["name"], "input": call["input"], "error": TABLELESS_NOTE}
                done.append(record)
                tracer.event("tool_call", run_id=state["run_id"], **record)
                results.append({"type": "tool_result", "tool_use_id": call["id"],
                                "content": TABLELESS_NOTE, "is_error": True})
                continue
            with tracer.span(call["name"], as_type="tool", input=call["input"]) as span:
                outcome = toolbox.call(call["name"], call["input"], state["run_id"])
                kept = ("source", "rows", "truncated", "error")  # no result rows leave the machine
                span.update(output={k: v for k, v in outcome.record.items() if k in kept},
                            level="ERROR" if outcome.is_error else "DEFAULT")
            # A tool that calls a model (the compliance review) reports its calls, which
            # count toward this question's cost like the agent's own.
            record = dict(outcome.record)
            for model_call in record.pop("model_calls", []):
                model_calls.append(model_call)
                tracer.event("model_call", **model_call)
            done.append(record)
            tracer.event("tool_call", run_id=state["run_id"], **record)
            results.append({"type": "tool_result", "tool_use_id": call["id"],
                            "content": outcome.content, "is_error": outcome.is_error})
        # A text block after the tool results, in the same user message.
        if len(done) >= limits.max_tool_calls:
            results.append({"type": "text", "text": (
                "You've used this question's query budget. Write the report now with what "
                "you have, and note anything you couldn't check."
            )})
        elif sum(record.get("repeat", False) for record in done) >= limits.max_repeats:
            results.append({"type": "text", "text": (
                "You've asked again for results you already have. Write the report now with "
                "what you have."
            )})
        return {"messages": [{"role": "user", "content": results}], "tool_calls": done,
                "model_calls": model_calls}

    def last_report(state: AgentState) -> dict:
        """The report in the model's last turn; raises ReportError if it isn't valid."""
        texts = [b["text"] for b in state["messages"][-1]["content"] if b["type"] == "text"]
        return parse_report(texts[-1] if texts else "")

    def check_report(state: AgentState) -> dict:
        """Check the report's key numbers against their findings' own SQL, in code. Numbers it
        can't confirm go back to the model, up to limits.number_repairs times."""
        try:
            report = last_report(state)
        except ReportError:
            return {}  # finish reports why
        result = check(report)
        if result["checked"]:
            tracer.event("number_check", run_id=state["run_id"], **result)
        update: dict = {"number_checks": [*state["number_checks"], result], "draft": report}
        if result["unconfirmed"] and len(state["number_checks"]) < limits.number_repairs:
            update["messages"] = [{"role": "user", "content": [
                {"type": "text", "text": repair_request(result["unconfirmed"])}]}]
        return update

    def finish(state: AgentState) -> dict:
        update: dict = {}
        report, error = None, None
        stop = state["stop_reason"]
        if state.get("outcome"):
            error = state["outcome"]["error"]
        elif stop == "tool_use":
            # Past the hard cap. Answer the pending calls, so a follow-up can still be asked.
            calls = [b for b in state["messages"][-1]["content"] if b["type"] == "tool_use"]
            update["messages"] = [{"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": call["id"], "is_error": True,
                 "content": "Stopped: no queries left for this question."} for call in calls]}]
            error = (f"Stopped: the model kept querying past {limits.hard_tool_calls} queries "
                     "without writing a report.")
        elif stop == "end_turn":
            try:
                report = last_report(state)
            except ReportError as failure:
                error = f"Invalid report: {failure}"
        else:
            error = {"max_tokens": "The response was cut off at the token limit.",
                     "refusal": "The model declined to answer (refusal).",
                     }.get(stop, f"Unexpected stop reason: {stop}")
        if report is None and state.get("draft") is not None:
            # The repair failed; the checked report stands, with its numbers marked.
            tracer.event("repair_failed", run_id=state["run_id"], error=error)
            report, error = state["draft"], None
        checks = state.get("number_checks") or []
        update["outcome"] = {"report": report, "error": error,
                             "numbers": checks[-1] if report is not None and checks else None}
        if report is not None and report["proposed_actions"]:
            update["proposals"] = [state["run_id"]]
        return update

    def after_model(state: AgentState) -> str:
        if state.get("outcome"):
            return "finish"
        if state["stop_reason"] == "tool_use" and len(state["tool_calls"]) < limits.hard_tool_calls:
            return "run_tools"
        if state["stop_reason"] == "end_turn":
            return "check_report"
        return "finish"

    def after_check(state: AgentState) -> str:
        return "call_model" if state["messages"][-1]["role"] == "user" else "finish"

    graph = StateGraph(AgentState)
    graph.add_node("call_model", call_model)
    graph.add_node("run_tools", run_tools)
    graph.add_node("check_report", check_report)
    graph.add_node("finish", finish)
    graph.add_edge(START, "call_model")
    graph.add_conditional_edges("call_model", after_model,
                                ["run_tools", "check_report", "finish"])
    graph.add_edge("run_tools", "call_model")
    graph.add_conditional_edges("check_report", after_check, ["call_model", "finish"])
    graph.add_edge("finish", END)
    return graph.compile(checkpointer=checkpointer)


def build_approval_graph(tracer: Tracer, checkpointer, act: Callable[[dict, dict, str], dict]):
    """One report's proposed actions, waiting for a person on a thread of their own."""

    def approve(state: ApprovalState) -> dict:
        """Pause until a person decides, then send only the approved actions. LangGraph
        re-runs this node from the top on resume, so nothing happens before the pause."""
        report = state["report"]
        actions = report["proposed_actions"]
        choice = interrupt({"run_id": state["run_id"], "question": state["question"],
                            "proposed_actions": actions})
        approved = set(choice["approved"])
        decisions = []
        for number, action in enumerate(actions):
            if number in approved:
                with tracer.span(f"create_{action['type']}", as_type="tool",
                                 input={"title": action["title"], "reason": action["reason"]}
                                 ) as span:
                    result = act(action, report, state["run_id"])
                    span.update(output=result,
                                level="ERROR" if result["status"] == "failed" else "DEFAULT")
                decisions.append({**action, **result})
            else:
                decisions.append({**action, "status": choice["rest"]})
        tracer.event("decisions", run_id=state["run_id"], decisions=decisions)
        return {"decisions": decisions}

    graph = StateGraph(ApprovalState)
    graph.add_node("approve", approve)
    graph.add_edge(START, "approve")
    graph.add_edge("approve", END)
    return graph.compile(checkpointer=checkpointer)


def _fail(error: str) -> dict:
    return {"outcome": {"report": None, "error": error}, "stop_reason": None}


def _same_call(call: dict, earlier: dict) -> bool:
    """Whether a tool call repeats one made earlier in this question, with the same input."""
    return earlier["tool"] == call["name"] and (
        json.dumps(earlier["input"], sort_keys=True) == json.dumps(call["input"], sort_keys=True))


def _earlier_result(messages: list[dict], results: list[dict], call: dict) -> dict | None:
    """The tool_result block an earlier identical call got, in this turn or an earlier one,
    or None if there's none with text content to hand back."""
    returned = {block["tool_use_id"]: block
                for message in messages if message["role"] == "user"
                and isinstance(message["content"], list)
                for block in message["content"] if block.get("type") == "tool_result"}
    returned |= {block["tool_use_id"]: block for block in results}
    for message in reversed(messages):
        if message["role"] != "assistant":
            continue
        for block in message["content"]:
            if (block.get("type") == "tool_use" and block["id"] != call["id"]
                    and block["id"] in returned
                    and isinstance(returned[block["id"]].get("content"), str)
                    and _same_call(call, {"tool": block["name"], "input": block["input"]})):
                return returned[block["id"]]
    return None


class Session:
    """One user's conversation. Ask a question, then follow-ups in the same session.

    The app sets the role; the model can't change it. The session starts the warehouse MCP
    server for that role, which connects every role except the fraud team lead to the
    warehouse copy without personal data. Close the session (or use it in a `with` block) to
    stop the server.
    """

    def __init__(
        self,
        role: str,
        config: AgentConfig | None = None,
        client: anthropic.Anthropic | None = None,
        purpose: str = "dev",
        trace_dir: Path | None = None,
        session_id: str | None = None,  # reopen a saved session (needs config.checkpoints)
        langfuse=None,  # a Langfuse client; by default one is made if its keys are set
    ):
        self.role = role
        self.config = config or AgentConfig()
        self.client = client or anthropic.Anthropic(max_retries=3)
        self.session_id = session_id or f"s-{uuid.uuid4().hex[:12]}"
        self._thread = {"configurable": {"thread_id": self.session_id}, "recursion_limit": 100}
        self._actions: McpToolbox | None = None
        self._checkpoint_db = None
        self.system = system_prompt(self.config.warehouse)
        dates = warehouse_dates(self.config.warehouse)
        self.context = session_context(role, dates)
        settings = self.config.settings
        allowed = TOOLSETS[self.config.toolset]
        boxes = [McpToolbox(
            warehouse_server(role, self.config.warehouse, self.config.transport),
            None if allowed is None else [n for n in allowed if n not in POLICY_TOOLS])]
        if self.config.policies and (allowed is None or set(allowed) & set(POLICY_TOOLS)):
            boxes.append(McpToolbox(
                policies_server(self.config.policies, dates["extract_date"],
                                self.config.transport),
                None if allowed is None else [n for n in allowed if n in POLICY_TOOLS]))
        if self.config.policies and allowed is None:
            boxes.append(ComplianceToolbox(
                self.config.policies, self.client,
                ReviewConfig(warehouse_for(role, self.config.warehouse), settings),
                self.config.compliance_variant, purpose))
        self.toolbox = ToolBelt(boxes)
        self.version = f"{__version__}+" + fingerprint(
            self.system, self.toolbox.definitions, REPORT_SCHEMA, settings.model, settings.effort)
        langfuse = langfuse if langfuse is not None else langfuse_client()
        # What goes to Langfuse has policyholders' names and contact details masked.
        masker = Masker.from_warehouse(self.config.warehouse) if langfuse is not None else None
        self.tracer = Tracer(self.session_id, purpose, trace_dir, langfuse, masker)
        self.tracer.event("session_start", role=role, version=self.version,
                          model=settings.model, effort=settings.effort,
                          toolset=self.config.toolset, tools=self.toolbox.names,
                          warehouse=str(self.config.warehouse))
        checkpointer = self._checkpointer()
        self.graph = build_graph(self.client, self.config, self.system, self.toolbox,
                                 self.tracer, checkpointer, self._check_numbers)
        self.approvals = build_approval_graph(self.tracer, checkpointer, self._act)

    def _check_numbers(self, report: dict) -> dict:
        """The report's key numbers against their findings' SQL, run as this role."""
        warehouse = warehouse_for(self.role, self.config.warehouse)

        def result_for(sql: str):
            result = run_query(warehouse, sql, CHECK_LIMITS)
            return result.columns, result.rows

        return check_numbers(report, result_for)

    def _checkpointer(self):
        if self.config.checkpoints is None:
            return InMemorySaver()
        self.config.checkpoints.parent.mkdir(parents=True, exist_ok=True)
        self._checkpoint_db = sqlite3.connect(self.config.checkpoints, check_same_thread=False)
        return SqliteSaver(self._checkpoint_db)

    def _act(self, action: dict, report: dict, run_id: str) -> dict:
        """Send one approved action to the actions server. Started on first use, so sessions
        that never approve anything (such as eval runs) don't start it."""
        if self._actions is None:
            self._actions = McpToolbox(actions_server(self.config.actions_store,
                                                      self.config.transport))
        tool = "create_ticket" if action["type"] == "ticket" else "create_alert"
        evidence = [f["evidence_sql"] for f in report["findings"] if f["evidence_sql"]]
        outcome = self._actions.call(tool, {
            "title": action["title"], "reason": action["reason"], "evidence_sql": evidence[:5],
            "approved_by": self.role, "run_id": run_id,
        })
        if outcome.is_error:
            return {"status": "failed", "error": outcome.content}
        created = json.loads(outcome.content)
        # With a GitHub repository configured, the action is also an issue there.
        return {"status": "created", "id": created["id"]} | (
            {"url": created["url"]} if created.get("url") else {})

    def close(self) -> None:
        self.toolbox.close()
        self.tracer.close()
        if self._actions is not None:
            self._actions.close()
        if self._checkpoint_db is not None:
            self._checkpoint_db.close()

    def __enter__(self) -> "Session":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @property
    def questions_left(self) -> int:
        asked = self.graph.get_state(self._thread).values.get("asked", 0)
        return max(0, self.config.max_questions - asked)

    def ask(self, question: str, on_event: Callable[[dict], None] | None = None) -> Answer:
        """Answer one question. on_event, if given, is called with each trace event as it
        happens (model calls, tool calls), for showing progress. Raises SessionFull once the
        session has used its questions."""
        if not self.questions_left:
            raise SessionFull(f"This session has used its {self.config.max_questions} "
                              "questions. Start a new one to ask more.")
        if on_event is not None:
            self.tracer.listeners.append(on_event)
        try:
            return self._ask(question)
        finally:
            if on_event is not None:
                self.tracer.listeners.remove(on_event)

    def _ask(self, question: str) -> Answer:
        run_id = f"r-{uuid.uuid4().hex[:12]}"
        content = [{"type": "text", "text": question}]
        if not self.messages:
            content.insert(0, {"type": "text", "text": self.context})
        self.tracer.event("question", run_id=run_id, question=question)
        started = time.perf_counter()
        with self.tracer.question(run_id, question, self.role, self.version) as trace:
            state = self.graph.invoke(
                {"messages": [{"role": "user", "content": content}], "asked": 1,
                 "run_id": run_id, "model_calls": [], "tool_calls": [], "stop_reason": None,
                 "number_checks": [], "draft": None, "outcome": None},
                self._thread,
            )
            outcome = state["outcome"]
            report = outcome["report"] or {}
            trace.update(output={key: report.get(key) for key in
                                 ("status", "interpretation", "answer", "answer_sql")}
                         | {"error": outcome["error"]})
        answer = Answer(
            question=question,
            run_id=run_id,
            session_id=self.session_id,
            report=outcome["report"],
            error=outcome["error"],
            cost_usd=round(sum(c["cost_usd"] for c in state["model_calls"]), 6),
            seconds=round(time.perf_counter() - started, 2),
            model_calls=state["model_calls"],
            tool_calls=state["tool_calls"],
            numbers=outcome.get("numbers"),
        )
        if run_id in state.get("proposals", []):
            # The actions wait on their own thread, so the conversation can go on.
            self.approvals.invoke({"run_id": run_id, "question": question,
                                   "report": outcome["report"], "decisions": None},
                                  self._approval_thread(run_id))
            answer.pending_actions = list(outcome["report"]["proposed_actions"])
        self.tracer.event("answer", run_id=run_id, report=answer.report, error=answer.error,
                          cost_usd=answer.cost_usd, seconds=answer.seconds,
                          models_served=answer.models_served, fell_back=answer.fell_back)
        return answer

    def feedback(self, answer: Answer, helpful: bool, comment: str | None = None) -> None:
        """Record the user's rating of an answer: thumbs up or down, with an optional note."""
        self.tracer.feedback(answer.run_id, helpful, comment, question=answer.question,
                             role=self.role, version=self.version)

    def _approval_thread(self, run_id: str) -> dict:
        return {"configurable": {"thread_id": f"{self.session_id}:approval:{run_id}"}}

    def _paused(self, run_id: str) -> dict | None:
        """What a question's approval paused with: its run ID, question and actions."""
        for task in self.approvals.get_state(self._approval_thread(run_id)).tasks:
            for paused in task.interrupts:
                return paused.value
        return None

    @property
    def pending(self) -> list[dict]:
        """Proposed actions waiting for a decision, grouped by the question that proposed
        them, oldest first: [{"run_id", "question", "proposed_actions"}]."""
        proposals = self.graph.get_state(self._thread).values.get("proposals", [])
        return [paused for run_id in proposals if (paused := self._paused(run_id))]

    def decide(self, run_id: str, approved: Collection[int], note: str | None = None,
               rest: str = "rejected") -> list[dict]:
        """Approve the actions one question proposed at these positions, and mark the rest
        `rest`. Returns what happened to each one. The decision is traced in the same session
        as its question."""
        paused = self._paused(run_id)
        if paused is None:
            raise ValueError(f"No actions from {run_id} are waiting for a decision.")
        approved = sorted(approved)
        with self.tracer.trace(
                "approval", run_id, role=self.role, version=self.version,
                input={"proposed_actions": paused["proposed_actions"], "approved": approved},
                metadata={"note": note} if note else None) as trace:
            state = self.approvals.invoke(Command(resume={"approved": approved, "rest": rest}),
                                          self._approval_thread(run_id))
            decisions = state.get("decisions") or []
            trace.update(output={"decisions": decisions})
        return decisions

    def end(self, approved: dict[str, Collection[int]] | None = None) -> dict[str, list[dict]]:
        """The last chance before the session ends: send the actions approved here, by run
        ID and position, and drop everything else still waiting. Returns the decisions by
        run ID."""
        approved = approved or {}
        return {group["run_id"]: self.decide(group["run_id"], approved.get(group["run_id"], ()),
                                             note=END_NOTE, rest="dropped")
                for group in self.pending}

    @property
    def messages(self) -> list[dict]:
        """The whole conversation so far, as sent to the model."""
        return list(self.graph.get_state(self._thread).values.get("messages", []))
