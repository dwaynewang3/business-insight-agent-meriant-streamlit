"""The Business Insights Agent's UI.

    make demo      (or: uv run streamlit run app/main.py --server.address localhost)

Three modes:
- Guided demo: eight saved answers in order, each with a note on what to look for and what to
  open (app/guide.py). It's where the app starts, and it needs no API key.
- Saved runs: every saved run (the eval results). It needs no API key either, only the
  warehouse (`make data`) to show data and charts.
- Live: a conversation with the agent, as one of the four roles. Proposed tickets and alerts
  wait for your approval while you keep asking questions. Starting a new conversation or
  switching role gives you one last chance; anything not approved then is dropped. Each answer
  can be rated, thumbs up or down. Live is offered only when ANTHROPIC_API_KEY is set, so a
  hosted copy without a key shows saved answers only and costs nothing to visit. With a key,
  each guided step can also be asked live.

Every answer shows its sources in three layers: for everyone, how the question was read, an
"Agreed metric" or "Custom query" label and the data date; for technical users, Show SQL and
Show data; for auditors, the run ID. The label is "Agreed metric" when every number in the
query's result is one an agreed metric returned in the same answer, which code checks by
running both.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)  # the warehouse, logs and results paths are relative to the project

import duckdb  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
import streamlit.components.v1 as components  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from agent.citations import extract_citations  # noqa: E402
from agent.context import warehouse_dates  # noqa: E402
from agent.graph import AgentConfig, Session  # noqa: E402
from app.guide import GUIDE, INTRO, INTRO_TITLE, OUTRO, OUTRO_TITLE  # noqa: E402
from app.setup import build_data, data_missing  # noqa: E402
from app.sources import (  # noqa: E402
    VERDICT_ICONS,
    agreed_sql,
    citation_label,
    compliance_reviews,
    key_number_html,
    load_saved_runs,
    markdown_text,
    source_label,
    step_label,
    verdict_rows,
    verdict_title,
)
from mcp_servers.warehouse.access import ROLES  # noqa: E402
from mcp_servers.warehouse.tools import ToolFailure, Warehouse  # noqa: E402

WAREHOUSE = Path("data/dev.duckdb")
# The policy knowledge base, as the agent finds it (POLICY_KB; tests use a small one).
POLICY_KB = Path(os.environ.get("POLICY_KB", "data/policies.duckdb"))
ROLE_NAMES = {"head_of_claims": "Head of Claims", "claims_ops_manager": "Claims operations manager",
              "actuarial_analyst": "Actuarial analyst", "fraud_team_lead": "Fraud team lead"}
ROLE_NAMES_ARCHIVED = {"claims_vp": "Claims VP (role on the earlier US data)"}

load_dotenv()
st.set_page_config(page_title="Business Insights Agent", page_icon="📊", layout="wide")


@st.cache_resource(show_spinner=False)
def first_start_build() -> list[str]:
    """Runs once per server, however many visitors arrive while it's building."""
    return build_data()


if data_missing():  # a host that only runs the app, such as Streamlit Community Cloud
    with st.spinner("First visit since this copy started: building the demo data, which "
                    "takes a minute or two…"):
        for part in first_start_build():
            st.warning(f"Couldn't build {part}, so the answers that need it show without it.")


@st.cache_resource
def warehouse_for(role: str, path: Path) -> Warehouse:
    return Warehouse(role, path)


@st.cache_data
def clause_text(clause_id: str | None, version: str | None) -> tuple | None:
    """A clause's text and the dates its version was in force, from the policy knowledge base
    (no model needed), or None. Without a version, the latest one."""
    if not POLICY_KB.exists() or not clause_id:
        return None
    with duckdb.connect(str(POLICY_KB), read_only=True) as con:
        row = con.execute("SELECT context_text, effective_from, effective_to FROM policy_chunks "
                          "WHERE clause_id = ? AND (version = ? OR ? IS NULL) "
                          "ORDER BY effective_from DESC LIMIT 1",
                          [clause_id, version, version]).fetchone()
    return (row[0], (str(row[1]), str(row[2]) if row[2] else None)) if row else None


@st.cache_data
def data_date(path: Path) -> str:
    return warehouse_dates(path)["extract_date"]


def query(role: str, sql: str, warehouse: Path = WAREHOUSE) -> pd.DataFrame | str:
    """Rows for display, run as the role through the SQL guard, or the reason it failed."""
    try:
        result = warehouse_for(role, warehouse).run_sql(sql)
    except ToolFailure as failure:
        return str(failure)
    return pd.DataFrame(result["rows"], columns=result["columns"])


@st.cache_data
def result_rows(role: str, sql: str, warehouse: Path = WAREHOUSE) -> list | None:
    """A query's whole result, for comparing with an agreed metric's, or None when it fails
    or is cut short at the row limit."""
    try:
        result = warehouse_for(role, warehouse).run_sql(sql)
    except ToolFailure:
        return None
    return None if result["truncated"] else result["rows"]


LABEL_HELP = ("**Agreed metric:** every number in this result is one the company's agreed "
              "metric returned for the same row in this answer (rounding aside). Code checks "
              "it by running both queries; the model can't set it. **Custom query:** at "
              "least one number comes from SQL the agent wrote itself, so check the SQL.")


def show_steps(tool_calls: list[dict]) -> None:
    with st.expander(f"Investigation steps ({len(tool_calls)})"):
        for call in tool_calls:
            st.write("· " + (step_label({"event": "tool_call", **call}) or call["tool"]))


def show_report(report: dict | None, error: str | None, tool_calls: list[dict], role: str,
                key: str, run_id: str = "", cost: float | None = None,
                seconds: float | None = None, warehouse: Path = WAREHOUSE,
                data_note: str | None = None) -> None:
    """One answer with its sources, re-running its SQL on the warehouse it queried. With a
    data_note (an archived run, or a warehouse that isn't built), the SQL is shown but not
    re-run, and the note says why."""
    live_data = data_note is None
    if report is None:
        st.error(f"No answer: {error}")
        return
    answer = markdown_text(report["answer"])
    if report["status"] == "needs_clarification":
        st.info(answer)
    elif report["status"] == "declined":
        st.warning(answer)
    else:
        st.markdown(answer)

    # The result of each agreed metric computed in this answer, to compare other results with.
    agreed = [rows for sql in agreed_sql(tool_calls)
              if (rows := result_rows(role, sql, warehouse)) is not None] if live_data else []

    def label_for(sql: str | None) -> str | None:
        rows = result_rows(role, sql, warehouse) if live_data and sql else None
        return source_label(sql, tool_calls, rows, agreed)

    label = label_for(report.get("answer_sql"))
    st.caption(f"**How I read the question:** {markdown_text(report['interpretation'])}")
    as_of = live_data and f"Data as of {data_date(warehouse)}"
    st.caption(" · ".join(part for part in (label and f"**{label}**", as_of) if part),
               help=LABEL_HELP if label else None)

    if citations := extract_citations(report):
        with st.expander(f"Policy clauses ({len(citations)})"):
            for citation in citations:
                found = clause_text(citation.get("clause_id"), citation.get("version"))
                label = citation_label(citation, tool_calls, found[1] if found else None)
                st.markdown(f"- **{markdown_text(label)}**")
                if found:
                    st.caption(markdown_text(found[0]))

    for review in compliance_reviews(tool_calls):
        with st.container(border=True):
            st.markdown(f"**{markdown_text(verdict_title(review))}**")
            as_of = review.get("as_of") or {}
            st.caption(f"Policies as in force on {as_of.get('coverage')} (cover and "
                       f"settlement) and {as_of.get('procedure')} (procedures)")
            st.dataframe(verdict_rows(review), hide_index=True)

    if report.get("hypotheses"):
        st.markdown("**Explanations tested**")
        for item in report["hypotheses"]:
            st.markdown(f"{VERDICT_ICONS.get(item['verdict'], '•')} "
                        f"**{markdown_text(item['hypothesis'])}**: "
                        f"{markdown_text(item['evidence'])}")
    for issue in report.get("data_quality_issues", []):
        st.warning(f"**Data quality:** {markdown_text(issue['issue'])} "
                   f"{markdown_text(issue['impact'])}")

    if not live_data and report.get("charts"):
        st.caption(f"Charts aren't redrawn: {data_note}.")
    for number, chart in enumerate(report.get("charts", []) if live_data else []):
        data = query(role, chart["sql"], warehouse)
        if isinstance(data, pd.DataFrame) and {chart["x"], chart["y"]} <= set(data.columns):
            st.markdown(f"**{chart['title']}**")
            draw = st.line_chart if chart["type"] == "line" else st.bar_chart
            draw(data, x=chart["x"], y=chart["y"])
        elif number == 0:
            st.caption(f"Chart '{chart['title']}' couldn't be drawn.")

    if report.get("findings"):
        with st.expander("Evidence"):
            for finding in report["findings"]:
                # Each finding's own query supplies the exact value behind a rounded number,
                # and shows which numbers it doesn't contain. A finding without SQL confirms
                # nothing; a query that fails here can't say either way.
                rows = None
                if live_data and finding["key_numbers"]:
                    data = query(role, finding["evidence_sql"], warehouse) \
                        if finding.get("evidence_sql") else pd.DataFrame()
                    if isinstance(data, pd.DataFrame):
                        rows = data.astype(object).values.tolist()
                numbers = ", ".join(key_number_html(n, rows) for n in finding["key_numbers"])
                source = label_for(finding.get("evidence_sql"))
                st.markdown(f"- {markdown_text(finding['claim'], html_too=True)}"
                            + (f" ({numbers})" if numbers else "")
                            + (f" · *{source}*" if source else ""),
                            unsafe_allow_html=True)

    if report.get("answer_sql"):
        with st.expander("Show SQL"):
            st.code(report["answer_sql"], language="sql")
        with st.expander("Show data"):
            data = query(role, report["answer_sql"], warehouse) if live_data else (
                f"Not available: {data_note}.")
            if isinstance(data, str):
                st.caption(data)
            else:
                st.dataframe(data, hide_index=True)
                st.download_button("Download CSV", data.to_csv(index=False), "answer.csv",
                                   key=f"{key}-csv")
    show_steps(tool_calls)
    details = [f"Run {run_id}" if run_id else "",
               f"API cost US${cost:.3f}" if cost is not None else "",
               f"{seconds:.0f} s" if seconds is not None else ""]
    st.caption(" · ".join(d for d in details if d))


@st.cache_resource(ttl=60)
def saved_runs() -> list:
    """Read once a minute, not on every click; nothing changes the runs it returns."""
    return load_saved_runs()


def replay_mode() -> None:
    runs = saved_runs()
    if not runs:
        st.info("No saved runs yet. Run the evals to create some: `make eval`.")
        return
    choice = st.selectbox("Saved run", range(len(runs)), format_func=lambda i: runs[i].title,
                          help="The runs marked Demo are the guided demo's, in order. The "
                               "rest are the saved evaluation runs, newest first.")
    show_saved_run(runs[choice], key=f"replay-{choice}")


def show_saved_run(run, key: str) -> None:
    """One saved run as a conversation: the question (and the one before a follow-up), the
    answer with its sources, and any actions it proposed."""
    record, archived = run.record, run.archived
    role = record["role"]
    on_test_data = not archived and run.warehouse != WAREHOUSE
    st.caption(f"Asked as: {(ROLE_NAMES | ROLE_NAMES_ARCHIVED).get(role, role)}"
               + (f" · on {run.warehouse}" if on_test_data else ""))
    if archived:
        st.info("This run is from the earlier US version of the data, kept as history. Its "
                "answer and SQL are shown as recorded; charts and data aren't re-run.")
    if "first" in record:
        with st.chat_message("user"):
            st.write(record["first"]["question"])
        with st.chat_message("assistant"):
            first = record["first"]
            if first["report"]:
                st.markdown(markdown_text(first["report"]["answer"]))
            else:
                st.error(first["error"])
    with st.chat_message("user"):
        st.write(record["question"])
    with st.chat_message("assistant"):
        show_report(record["report"], record["error"], record["tool_calls"], role,
                    key=key, run_id=record.get("run_id", ""),
                    cost=record.get("cost_usd"), seconds=record.get("seconds"),
                    warehouse=run.warehouse, data_note=run.data_note())
        actions = record.get("proposed_actions") or record["report"].get("proposed_actions", [])
        for action in actions:
            st.info(f"Proposed {action['type']}: **{markdown_text(action['title'])}**. "
                    f"{markdown_text(action['reason'])} "
                    "(Not created: actions need a person's approval in live mode.)")


def go_to_step(step: int) -> None:
    st.session_state.guide_step = step


def ask_live(role: str, question: str) -> None:
    """Hand a guided step's question to live mode, as the role that asked it."""
    state = st.session_state
    state.mode, state.role_select, state.queued_question = "Live", role, question


def guide_buttons(step: int, last: int, place: str) -> None:
    columns = iter(st.columns([1, 1.4, 5]))
    if step > 0:
        next(columns).button("← Back", key=f"guide-back-{place}", on_click=go_to_step,
                             args=(step - 1,))
    if step < last:
        label = "Start the tour →" if step == 0 else (
            "Next →" if step < last - 1 else "Finish →")
        next(columns).button(label, key=f"guide-next-{place}", type="primary",
                             on_click=go_to_step, args=(step + 1,))


def scroll_to_top(step: int) -> None:
    """Streamlit keeps the scroll position when the page reruns, so Next at the bottom of one
    answer would open the next step half-way down. The script runs once per step: the step
    number changes its text, and Streamlit reloads the frame only when the text changes."""
    components.html(
        f"""<script>
        // step {step}
        const page = window.parent.document.querySelector('[data-testid="stMain"]')
            || window.parent.document.querySelector('section.main');
        if (page) page.scrollTo(0, 0);
        </script>""", height=0)


def guided_mode(live: bool) -> None:
    """The guided demo: an opening screen, one screen per saved answer with what to look for
    and what to open, and a closing screen. With an API key, each question can be asked live."""
    state = st.session_state
    runs = saved_runs()[:len(GUIDE)]
    if [run.title.split(" ")[0] for run in runs] != ["Demo"] * len(GUIDE):
        st.info("The guided demo's saved runs aren't in `evals/results/`. **Saved runs** "
                "lists what is there.")
        return
    last = len(GUIDE) + 1
    step = state.guide_step
    state.guide_at = step  # remembered while another mode is open
    scroll_to_top(step)
    st.progress(step / last)
    if step == 0:
        st.subheader(INTRO_TITLE)
        st.markdown(INTRO)
    elif step == last:
        st.subheader(OUTRO_TITLE)
        st.markdown(OUTRO)
        if live:
            st.markdown("This copy has an API key, so you can also pick **Live** in the "
                        "sidebar and ask anything. A question costs a few US cents.")
    else:
        guide, run = GUIDE[step - 1], runs[step - 1]
        st.subheader(f"{step} of {len(GUIDE)} · {guide.title}")
        st.markdown(guide.intro)
        with st.container(border=True):
            st.markdown("**What to look for**\n" + "\n".join(f"- {n}" for n in guide.look_for))
            if guide.try_it:
                st.markdown("**Try it**\n" + "\n".join(f"- {n}" for n in guide.try_it))
        guide_buttons(step, last, "top")
        show_saved_run(run, key=f"guide-{step}")
        if live:
            record = run.record
            question = record.get("first", {}).get("question") or record["question"]
            st.button("Ask the agent this yourself (live, a few US cents)",
                      key=f"guide-live-{step}", on_click=ask_live,
                      args=(record["role"], question),
                      help="Opens live mode as the same role and asks this question, so you "
                           "can watch the agent work and ask follow-ups.")
    guide_buttons(step, last, "bottom")


STATUS_TEXT = {"created": "created", "rejected": "rejected", "failed": "failed",
               "dropped": "not sent (the conversation ended before it was approved)"}


def show_decisions(decisions: list[dict]) -> None:
    for decision in decisions:
        issue = f" · [GitHub issue]({decision['url']})" if decision.get("url") else ""
        if decision.get("error"):  # why it failed, such as GitHub refusing the issue
            issue = f" · {markdown_text(decision['error'])}"
        st.caption(f"{decision['type'].title()} '{markdown_text(decision['title'])}': "
                   f"{STATUS_TEXT.get(decision['status'], decision['status'])} "
                   f"{decision.get('id', '')}{issue}")


def action_label(action: dict) -> str:
    return markdown_text(f"{action['type'].title()}: {action['title']}. {action['reason']}")


def start_session(role: str) -> None:
    state = st.session_state
    state.session = Session(role, AgentConfig(checkpoints=Path("logs/checkpoints.sqlite")),
                            purpose="demo")
    state.role, state.turns, state.decisions, state.ending = role, [], {}, None
    state.feedback = {}  # run ID -> the rating and note already recorded


def end_session(new_role: str) -> None:
    state = st.session_state
    state.session.close()
    start_session(new_role)


def last_chance(new_role: str) -> None:
    """Before the conversation ends: approve what's still waiting, or it's dropped."""
    state = st.session_state
    st.warning("**Before this conversation ends**, these proposed actions are still waiting. "
               "Anything you don't approve now is dropped and not sent.")
    with st.form("last-chance"):
        approved = {}
        for group in state.session.pending:
            st.markdown(f"From *{group['question']}*")
            approved[group["run_id"]] = [
                number for number, action in enumerate(group["proposed_actions"])
                if st.checkbox(action_label(action), key=f"end-{group['run_id']}-{number}")]
        send = st.form_submit_button("Send approved and end the conversation", type="primary")
        back = st.form_submit_button("Back to the conversation")
    if send:
        decisions = state.session.end(approved)
        sent = sum(d["status"] == "created" for group in decisions.values() for d in group)
        dropped = sum(d["status"] == "dropped" for group in decisions.values() for d in group)
        end_session(new_role)
        state.notice = f"Last conversation: {sent} action(s) sent, {dropped} not sent."
        st.rerun()
    if back:
        state.ending = None
        state.revert_role = state.role  # undo a role switch, before the selectbox is drawn
        st.rerun()


def show_feedback(answer) -> None:
    """Thumbs up or down on a live answer, with a note on what was wrong. Every change is
    recorded, so the last line for a run is the user's final word."""
    state = st.session_state
    rating = st.feedback("thumbs", key=f"feedback-{answer.run_id}")
    if rating is None:
        return
    note = None
    if rating == 0:
        note = st.text_input("What was wrong? (optional)",
                             key=f"feedback-note-{answer.run_id}") or None
    if state.feedback.get(answer.run_id) != (rating, note):
        state.session.feedback(answer, helpful=bool(rating), comment=note)
        state.feedback[answer.run_id] = (rating, note)


def live_mode(role: str) -> None:
    state = st.session_state
    if "session" not in state:
        start_session(role)
    elif state.role != role:  # switching role ends this conversation
        if state.session.pending:
            state.ending = "switch"
        else:
            end_session(role)
    if notice := state.pop("notice", None):
        st.info(notice)

    for number, (question, answer) in enumerate(state.turns):
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            show_report(answer.report, answer.error, answer.tool_calls, state.role,
                        key=f"live-{number}", run_id=answer.run_id, cost=answer.cost_usd,
                        seconds=answer.seconds)
            show_decisions(state.decisions.get(answer.run_id, []))
            show_feedback(answer)

    if state.ending:
        last_chance(role)
        return

    for group in state.session.pending:
        run_id = group["run_id"]
        with st.form(f"approval-{run_id}"):
            st.markdown(f"**Proposed actions** from *{group['question']}*. Nothing is created "
                        "unless you approve it. You can keep asking questions: these wait "
                        "until you end the conversation.")
            approved = [number for number, action in enumerate(group["proposed_actions"])
                        if st.checkbox(action_label(action), key=f"approve-{run_id}-{number}")]
            if st.form_submit_button("Submit decision"):
                state.decisions[run_id] = state.session.decide(run_id, approved)
                st.rerun()

    if not state.session.questions_left:
        st.info(f"This conversation has used its {state.session.config.max_questions} "
                "questions, which keeps answers fast and cheap. Start a new conversation in "
                "the sidebar to ask more.")
        return
    question = st.chat_input("Ask about claims, costs or data quality")
    question = question or state.pop("queued_question", None)  # handed over by the guided demo
    if question:
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"), st.status("Investigating…", expanded=True) as status:
            def on_event(event: dict) -> None:
                if line := step_label(event):
                    status.write(line)

            answer = state.session.ask(question, on_event=on_event)
            status.update(label="Done", state="complete", expanded=False)
        state.turns.append((question, answer))
        st.rerun()


st.title("Business Insights Agent")
st.caption("Answers \"what\" and \"why\" questions about Meridian General Insurance's claims data "
           "(a fictional Australian motor and home insurer), "
           "with the evidence behind every number.")
if "revert_role" in st.session_state:
    st.session_state.role_select = st.session_state.pop("revert_role")
GUIDED, SAVED, LIVE = "Guided demo", "Saved runs", "Live"
STEP_NAMES = [INTRO_TITLE, *(f"{number}. {step.title}" for number, step in
                             enumerate(GUIDE, start=1)), OUTRO_TITLE]

with st.sidebar:
    live = bool(os.environ.get("ANTHROPIC_API_KEY"))
    mode = st.radio("Mode", [GUIDED, SAVED, LIVE] if live else [GUIDED, SAVED], key="mode",
                    help="The guided demo and the saved runs need no API key. Live calls "
                         "Claude and costs a few cents a question.")
    if mode == GUIDED:
        if "guide_step" not in st.session_state:  # first visit, or back from another mode
            st.session_state.guide_step = st.session_state.get("guide_at", 0)
        st.selectbox("Step", range(len(STEP_NAMES)), format_func=STEP_NAMES.__getitem__,
                     key="guide_step")
    role = None
    if live:
        role = st.selectbox("Role", list(ROLES), format_func=ROLE_NAMES.get,
                            disabled=mode != LIVE, key="role_select",
                            help="Only the fraud team lead sees personal data. Switching role "
                                 "starts a new conversation.")
    else:
        st.caption("**These are saved answers.** The agent gave each one; its SQL, data and "
                   "charts are re-run here. Asking it new questions (live mode) needs "
                   "`ANTHROPIC_API_KEY` in `.env`.")
    if mode == LIVE and st.button("New conversation") and "session" in st.session_state:
        if st.session_state.session.pending:
            st.session_state.ending = "new"
        else:
            end_session(role)
        st.rerun()

if mode == LIVE:
    live_mode(role)
elif mode == SAVED:
    replay_mode()
else:
    guided_mode(live)
