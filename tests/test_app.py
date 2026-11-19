"""The UI: source labels, step labels, saved runs, the guided demo, and the app itself run
headless.

The app tests use Streamlit's test runner on the guided demo and the saved runs, and in live
mode with a stand-in for the agent, so they never call Claude.
"""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.guide import GUIDE, INTRO_TITLE, OUTRO_TITLE
from app.sources import (
    AGREED,
    CUSTOM,
    DEMO_RUNS,
    RESULTS_DIR,
    citation_label,
    compliance_reviews,
    from_agreed_metrics,
    key_number_html,
    load_saved_runs,
    markdown_text,
    source_label,
    step_label,
    verdict_rows,
    verdict_title,
)

APP = str(Path(__file__).resolve().parent.parent / "app" / "main.py")
METRIC_SQL = "WITH source AS (SELECT 1)\nSELECT count(*) AS value FROM source"
CALLS = [{"tool": "query_metric", "source": "agreed_metric", "sql": METRIC_SQL},
         {"tool": "run_sql", "source": "custom_query", "sql": "SELECT 2"}]


def test_only_sql_an_agreed_metric_produced_is_labeled_agreed():
    assert source_label(METRIC_SQL.replace("\n", "   ") + ";", CALLS) == AGREED
    assert source_label("SELECT 2", CALLS) == CUSTOM
    assert source_label("SELECT count(*) AS value FROM source", CALLS) == CUSTOM
    assert source_label(None, CALLS) is None


STATES = [["NSW", 7.948717], ["VIC", 7.031], ["QLD", 6.7712], ["WA", 6.49]]


def test_a_result_made_only_of_an_agreed_metrics_numbers_is_labeled_agreed():
    """The agent computes the agreed metric, then writes its own shorter SQL for the answer:
    the label follows the numbers, not the SQL text."""
    rounded = [["WA", 6.49], ["NSW", 7.95], ["QLD", 6.77], ["VIC", 7.03]]  # any row order
    assert source_label("SELECT 2", CALLS, rounded, [STATES]) == AGREED
    assert from_agreed_metrics([[7.95, "nsw"], [7.03, "vic"]], [STATES])  # the top 2 of 4
    # A metric's result may carry a label the answer leaves out, such as the month.
    by_month = [["2026-03-01", "NSW", 585.35], ["2026-03-01", "ACT", 91.0]]
    assert from_agreed_metrics([["ACT", 91], ["NSW", 585.35]], [by_month])
    assert from_agreed_metrics([["2026-03", "NSW", 585.4]], [by_month])
    # A fraction written as a percentage is the same number; one total is its only row.
    assert from_agreed_metrics([["home", 61.3]], [[["home", 0.61328], ["motor", 0.567]]])
    assert from_agreed_metrics([["NSW Q2 2026", 6668.69]], [[[6668.687419]]])
    # Two agreed metrics side by side: each number comes from one of them.
    assert from_agreed_metrics([["home", 0.613, 20306]],
                               [[["home", 0.61328]], [["home", 20305.85], ["motor", 9100.0]]])


def test_a_result_with_a_number_of_its_own_stays_a_custom_query():
    assert source_label("SELECT 2", CALLS, [["NSW", 7.95], ["VIC", 6.2]], [STATES]) == CUSTOM
    # A corrected figure (duplicates removed) is the agent's number, not the agreed one.
    assert not from_agreed_metrics([["home", 0.6049]], [[["home", 0.61328], ["motor", 0.567]]])
    # So is a claim count beside the agreed average.
    assert not from_agreed_metrics([["NSW", 217, 6668.69]], [[["NSW", 6668.687419]]])
    # A number with no label can't be tied to one of several rows, nor can an unknown label.
    assert not from_agreed_metrics([[7.95]], [STATES])
    assert not from_agreed_metrics([["New South Wales", 7.95]], [STATES])
    assert not from_agreed_metrics([["NSW", 7.95]], [STATES + [["NSW", 3.0]]])  # two NSW rows
    # No numbers, no rows, no metric, or a result that couldn't be re-run: nothing to confirm.
    assert not from_agreed_metrics([["NSW"], ["VIC"]], [STATES])
    assert not from_agreed_metrics([], [STATES]) and not from_agreed_metrics(STATES, [])
    assert source_label("SELECT 2", CALLS, None, [STATES]) == CUSTOM


def test_steps_read_as_plain_progress_lines():
    assert step_label({"event": "tool_call", "tool": "query_metric",
                       "input": {"metric": "loss_ratio"}, "rows": 2}) == \
        "Computing the agreed metric loss_ratio (2 rows)"
    assert "failed" in step_label({"event": "tool_call", "tool": "run_sql", "error": "x"})
    assert step_label({"event": "model_call", "cost_usd": 0.012}).startswith("Claude")
    assert step_label({"event": "answer"}) is None


def test_rounded_key_numbers_are_marked_with_the_exact_value_from_the_query():
    rows = [("motor", 0.5362451, 1287), ("home", 0.5979165, 783)]
    result = (["product", "loss_ratio", "claims"], rows)
    motor = "product = motor"
    rounded = key_number_html({"label": "Motor loss ratio", "value": 53.6, "unit": "%",
                               "column": "loss_ratio", "row": motor}, result)
    assert rounded.startswith("Motor loss ratio: 53.6 %")
    assert 'title="Rounded. Exact value from the query: 53.6245">(rounded)</abbr>' in rounded
    exact = key_number_html({"label": "Motor claims", "value": 1287, "unit": "claims",
                             "column": "claims", "row": motor}, result)
    assert exact == "Motor claims: 1,287 claims"
    # A saved report from before numbers named their cell is matched against the whole result.
    assert "(rounded)" in key_number_html(
        {"label": "Motor loss ratio", "value": 53.6, "unit": "%"}, result)
    # Not in the query (or no query): shown as written, with no claim to an exact value.
    assert "rounded" not in key_number_html({"label": "x", "value": 9.9, "unit": "%"}, result)
    assert "rounded" not in key_number_html({"label": "x", "value": 53.6, "unit": "%"}, None)


def test_a_key_number_its_cell_doesnt_hold_is_marked_not_confirmed():
    result = (["product", "loss_ratio", "claims"],
              [["motor", 0.536245, 1287], ["home", 0.597917, 783]])
    missing = key_number_html({"label": "Home claims", "value": 2210, "unit": "claims"}, result)
    assert missing.endswith("(not confirmed)</abbr>")
    # Home's count put on the motor row: in the result, but not in its cell.
    swapped = key_number_html({"label": "Motor claims", "value": 783, "unit": "claims",
                               "column": "claims",
                               "row": "product = motor"}, result)
    assert swapped.endswith("(not confirmed)</abbr>")
    assert "not confirmed" not in key_number_html(
        {"label": "Motor claims", "value": 1287, "unit": "claims"}, result)
    # An empty result (or a finding without SQL) confirms nothing; no result says nothing.
    assert "not confirmed" in key_number_html({"label": "x", "value": 1, "unit": ""}, ([], []))
    assert "not confirmed" not in key_number_html({"label": "x", "value": 1, "unit": ""}, None)
    assert step_label({"event": "number_check", "checked": 3, "unconfirmed": [{}]}) == \
        "Checked 3 key numbers against their queries: 1 not found"


def test_model_text_cant_start_latex_or_inject_html():
    assert markdown_text("From $10,626 to $13,368") == "From \\$10,626 to \\$13,368"
    assert markdown_text("<b>x</b> $1", html_too=True) == "&lt;b&gt;x&lt;/b&gt; \\$1"
    marked = key_number_html({"label": "<img src=x>", "value": 1, "unit": "$"}, None)
    assert "<img" not in marked and "\\$" in marked


def test_saved_runs_list_follow_ups_with_both_questions(tmp_path):
    cases = tmp_path / "20261009-000000-test" / "cases"
    cases.mkdir(parents=True)
    (cases / "a.json").write_text(json.dumps(
        {"question": "Now for home.", "first": {"question": "Motor by state?"},
         "report": {"answer": "x"}}))
    (cases / "b.json").write_text(json.dumps({"question": "Failed", "report": None}))
    runs = load_saved_runs(tmp_path)
    assert len(runs) == 1 and runs[0].title.startswith("Motor by state? → Now for home.")


def test_archived_runs_on_the_earlier_data_come_last_and_are_labelled(tmp_path):
    for folder, question in (("archive-us-data/20261009-000000-old", "Old question"),
                             ("20261016-000000-new", "New question")):
        cases = tmp_path / folder / "cases"
        cases.mkdir(parents=True)
        (cases / "a.json").write_text(json.dumps({"question": question,
                                                   "report": {"answer": "x"}}))
    runs = load_saved_runs(tmp_path)
    assert [(r.title.split("  ·  ")[0], r.archived) for r in runs] == [
        ("New question", False), ("[US data, archived] Old question", True)]


def test_saved_runs_replay_on_the_warehouse_they_queried(tmp_path):
    built = tmp_path / "test.duckdb"
    built.touch()
    built.with_name("test_restricted.duckdb").touch()
    cases = tmp_path / "20261019-000000-test-final" / "cases"
    cases.mkdir(parents=True)
    for name, warehouse in (("a", str(built)), ("b", str(tmp_path / "missing.duckdb")),
                            ("c", None)):
        (cases / f"{name}.json").write_text(json.dumps(
            {"question": name, "report": {"answer": "x"}, "warehouse": warehouse}))
    runs = {r.record["question"]: r for r in load_saved_runs(tmp_path)}
    assert runs["a"].warehouse == built and runs["a"].data_note() is None
    assert "isn't built" in runs["b"].data_note()
    assert runs["c"].warehouse == Path("data/dev.duckdb")  # saved before records named it


needs_data = pytest.mark.skipif(
    not (Path("data/dev.duckdb").exists() and Path("data/dev_restricted.duckdb").exists()
         and list(Path("evals/results").rglob("cases/*.json"))),
    reason="needs `make data` and saved eval results")


def shown(app) -> str:
    return " ".join(e.value for kind in (app.subheader, app.markdown, app.caption) for e in kind)


def click(app, label: str):
    return next(b for b in app.button if b.label.startswith(label)).click().run()


@needs_data
def test_saved_runs_mode_shows_a_saved_run_without_an_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    app = AppTest.from_file(APP, default_timeout=60).run()
    app.radio[0].set_value("Saved runs").run()
    assert not app.exception
    assert len(app.selectbox[0].options) > len(GUIDE)  # every saved run
    assert "How I read the question" in shown(app) and "Data as of 2026-09-30" in shown(app)


@needs_data
def test_without_a_key_the_app_shows_saved_answers_only(monkeypatch):
    """A hosted copy has no key: it can't offer live mode, so a visit can't spend anything."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    app = AppTest.from_file(APP, default_timeout=60).run()
    assert not app.exception
    assert app.radio[0].options == ["Guided demo", "Saved runs"] and not app.chat_input
    assert any("ANTHROPIC_API_KEY" in c.value for c in app.sidebar.caption)
    click(app, "Start the tour")
    assert not any("live" in b.label for b in app.button)


@needs_data
def test_the_app_opens_on_the_guided_demo_and_steps_through_every_answer(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    app = AppTest.from_file(APP, default_timeout=60).run()
    assert not app.exception and INTRO_TITLE in shown(app)
    assert not any(b.label.startswith("←") for b in app.button)  # nothing before the start
    for number, step in enumerate(GUIDE, start=1):
        click(app, "Start the tour" if number == 1 else "Next")
        text = shown(app)
        assert not app.exception, step.title
        assert f"{number} of {len(GUIDE)} · {step.title}" in text
        assert "What to look for" in text and "How I read the question" in text
    click(app, "Finish")
    assert OUTRO_TITLE in shown(app) and not any(b.label.startswith("Finish") for b in app.button)
    click(app, "← Back")
    assert GUIDE[-1].title in shown(app)
    # The sidebar's step list jumps anywhere, and the place is kept while another mode is open.
    app.sidebar.selectbox[0].set_value(3).run()
    assert GUIDE[2].title in shown(app)
    app.radio[0].set_value("Saved runs").run()
    app.radio[0].set_value("Guided demo").run()
    assert GUIDE[2].title in shown(app)


@needs_data
def test_the_guides_notes_match_what_its_saved_answers_show(monkeypatch):
    """Each note quotes facts from its saved run. If a run is re-recorded, the note must be
    checked again: the first version of step 1 promised a label the screen didn't show."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    app = AppTest.from_file(APP, default_timeout=60).run()
    facts = [
        ("**Agreed metric** · Data as of", "Investigation steps (4)", "June"),
        ("**Custom query** · Data as of", "\\$14,027", "\\$20,890", "WX-003", "September"),
        ("198", "\\$2.62M", "\\$1.31M", "Proposed ticket", "❔"),
        ("can't list policyholder names", "Investigation steps (0)"),
        ("POL-MTR-002 §3.4, v5.3", "v6.0", "Investigation steps (14)"),
        ("Non-compliant (2 breaches)", "shows 1 breach"),
        ("GC-004", "GC-005", "GC-019", "§4.7"),
        ("And for the first half of 2026?", "57.3%", "60.8%", "Proposed ticket"),
    ]
    for step, expected in zip(GUIDE, facts, strict=True):
        click(app, "Start the tour" if step is GUIDE[0] else "Next")
        # Everything on the screen except the guide's own notes, which quote the same facts.
        notes = ("**What to look for**", "**Try it**", step.intro)
        text = " ".join(str(e.value) for kind in (app.markdown, app.caption, app.info,
                                                  app.warning)
                        for e in kind if not str(e.value).startswith(notes))
        text += " ".join(e.label for e in app.expander)
        for fact in expected:
            assert fact in text, (step.title, fact)
    # The 11 unneeded queries of step 5: three policy calls, then SQL only.
    run = load_saved_runs()[4]
    assert [call["tool"] for call in run.record["tool_calls"]].count("run_sql") == 11


def test_replay_starts_with_the_demo_scripts_runs_in_order():
    for name in DEMO_RUNS:  # each one is a saved run in the repository
        folder, case = name.split("/")
        assert (RESULTS_DIR / folder / "cases" / f"{case}.json").exists(), name
    runs = load_saved_runs()
    assert [run.title.split("  ·  ")[0] for run in runs[:len(DEMO_RUNS)]] == [
        f"Demo {step} of {len(DEMO_RUNS)}" for step in range(1, len(DEMO_RUNS) + 1)]
    assert "motor claim frequency by state" in runs[0].title
    assert not any(run.title.startswith("Demo ") for run in runs[len(DEMO_RUNS):])


ACTIONS = [
    {"type": "ticket", "title": "Remove duplicate payments", "reason": "159 rows loaded twice"},
    {"type": "alert", "title": "Shop RS-010 cost outlier", "reason": "Costs 60% above peers"},
]


class FakeSession:
    """Stands in for the agent in live mode: every answer proposes the same two actions."""

    instances: list["FakeSession"] = []

    def __init__(self, role, config=None, purpose="dev"):
        from agent.graph import AgentConfig

        self.role, self.groups, self.asked, self.ended, self.closed = role, {}, 0, None, False
        self.ratings = []
        self.config = config or AgentConfig()
        FakeSession.instances.append(self)

    @property
    def questions_left(self):
        return self.config.max_questions - self.asked

    def ask(self, question, on_event=None):
        from agent.graph import Answer

        self.asked += 1
        run_id = f"r-{self.asked}"
        report = {"status": "answered", "question_type": "why", "answer": f"Answer {self.asked}.",
                  "interpretation": "How I read it.", "answer_sql": None, "findings": [],
                  "hypotheses": [], "data_quality_issues": [], "charts": [],
                  "proposed_actions": ACTIONS, "open_questions": []}
        self.groups[run_id] = {"run_id": run_id, "question": question,
                               "proposed_actions": ACTIONS}
        return Answer(question, run_id, "s-test", report, None, 0.01, 1.0, [], [], list(ACTIONS))

    @property
    def pending(self):
        return list(self.groups.values())

    def decide(self, run_id, approved, note=None, rest="rejected"):
        group = self.groups.pop(run_id)
        return [{**action, "status": "created" if number in approved else rest}
                for number, action in enumerate(group["proposed_actions"])]

    def end(self, approved=None):
        self.ended = approved
        return {run_id: self.decide(run_id, (approved or {}).get(run_id, ()), rest="dropped")
                for run_id in list(self.groups)}

    def feedback(self, answer, helpful, comment=None):
        self.ratings.append((answer.run_id, helpful, comment))

    def close(self):
        self.closed = True


@pytest.fixture
def live_app(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr("agent.graph.Session", FakeSession)
    FakeSession.instances.clear()
    app = AppTest.from_file(APP, default_timeout=60).run()
    app.radio[0].set_value("Live").run()
    return app


def proposal_boxes(app) -> int:
    return sum("**Proposed actions**" in m.value for m in app.markdown)


@needs_data
def test_actions_wait_across_questions_and_get_a_last_chance(live_app):
    app = live_app
    app.chat_input[0].set_value("Why did paid amounts jump?").run()
    app.chat_input[0].set_value("And in April?").run()
    assert not app.exception and proposal_boxes(app) == 2  # both still waiting

    app.sidebar.button[0].click().run()  # New conversation
    assert any("Before this conversation ends" in w.value for w in app.warning)
    assert proposal_boxes(app) == 0 and not app.chat_input  # only the last chance is offered
    app.checkbox(key="end-r-1-0").check()
    next(b for b in app.button if b.label.startswith("Send approved")).click().run()

    session = FakeSession.instances[0]
    assert session.ended == {"r-1": [0], "r-2": []} and session.closed
    assert any("1 action(s) sent, 3 not sent" in i.value for i in app.info)
    assert len(FakeSession.instances) == 2 and proposal_boxes(app) == 0


@needs_data
def test_going_back_from_a_role_switch_keeps_the_conversation(live_app):
    app = live_app
    role = app.selectbox(key="role_select").value
    app.chat_input[0].set_value("Why did paid amounts jump?").run()
    other = next(option for option in ("fraud_team_lead", "head_of_claims") if option != role)
    app.selectbox(key="role_select").set_value(other).run()
    assert any("Before this conversation ends" in w.value for w in app.warning)

    next(b for b in app.button if b.label == "Back to the conversation").click().run()
    assert not app.exception and app.selectbox(key="role_select").value == role
    assert proposal_boxes(app) == 1 and len(FakeSession.instances) == 1


REVIEW_CALL = {
    "tool": "check_claim_compliance", "input": {"claim_id": "GC-010"}, "source": None,
    "clauses": [["POL-MTR-002:3.4", "5.3"]],
    "compliance": {"claim_id": "GC-010", "variant": "full", "overall": "NON_COMPLIANT",
                   "as_of": {"coverage": "2026-02-10", "procedure": "2026-02-20"},
                   "findings": [
                       {"check": "cover", "status": "PASS", "severity": "NONE",
                        "rule": "Cover in force.", "clauses": [], "validation_failed": False},
                       {"check": "exclusions", "status": "BREACH", "severity": "HIGH",
                        "rule": "Expired licence is an absolute exclusion.",
                        "clauses": [{"clause_id": "POL-MTR-002:3.4", "version": "5.3"},
                                    {"clause_id": "POL-XYZ-001:1.1", "version": None}],
                        "validation_failed": False},
                       {"check": "service_levels", "status": "NEEDS_REVIEW",
                        "severity": "MEDIUM", "rule": "Update gap.", "clauses": [],
                        "validation_failed": True}]}}


def test_a_compliance_review_reads_as_a_verdict_card_with_problems_first():
    [review] = compliance_reviews([{"tool": "run_sql"}, REVIEW_CALL])
    assert verdict_title(review) == ("Compliance review of GC-010: Non-compliant "
                                     "(1 breach, 1 to review)")
    rows = verdict_rows(review)
    assert [r["Area"] for r in rows] == ["exclusions", "service levels", "cover"]
    assert rows[0]["Status"] == "❌ breach" and rows[0]["Severity"] == "high"
    assert rows[0]["Clauses"] == "POL-MTR-002:3.4 v5.3, POL-XYZ-001:1.1 (not supplied)"
    assert rows[1]["Rule"].endswith("(failed the code checks)") and rows[2]["Severity"] == ""
    assert step_label({"event": "tool_call", **REVIEW_CALL}) == \
        "Reviewing GC-010 against the policies"


def test_clause_labels_give_the_dates_the_version_was_in_force():
    cited = {"clause_id": "POL-MTR-002:3.4", "version": "5.3"}
    assert citation_label(cited, [REVIEW_CALL], ("2025-07-01", "2026-03-01")) == (
        "POL-MTR-002:3.4, v5.3, in force 2025-07-01 to 2026-03-01 "
        "(returned by a tool in this answer)")
    assert citation_label({**cited, "version": "6.0"}, [], ("2026-03-01", None)) == (
        "POL-MTR-002:3.4, v6.0, in force from 2026-03-01 "
        "(not returned by any tool in this answer)")


class ReviewSession(FakeSession):
    """Answers with a compliance review and a citation, and proposes nothing."""

    def ask(self, question, on_event=None):
        from agent.graph import Answer

        report = {"status": "answered", "question_type": "other",
                  "answer": "GC-010 breaches the expired-licence exclusion "
                            "(POL-MTR-002 §3.4, v5.3).",
                  "interpretation": "One claim's compliance.", "answer_sql": None,
                  "findings": [], "hypotheses": [], "data_quality_issues": [], "charts": [],
                  "proposed_actions": [], "open_questions": []}
        return Answer(question, "r-1", "s-test", report, None, 0.05, 20.0, [], [REVIEW_CALL])


@needs_data
def test_the_app_shows_the_verdict_card_and_the_cited_clause(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr("agent.graph.Session", ReviewSession)
    app = AppTest.from_file(APP, default_timeout=60).run()
    app.radio[0].set_value("Live").run()
    app.chat_input[0].set_value("Was GC-010 handled in line with policy?").run()
    assert not app.exception
    text = " ".join(m.value for m in app.markdown)
    assert "Compliance review of GC-010: Non-compliant (1 breach, 1 to review)" in text
    assert "POL-MTR-002:3.4, v5.3, in force" in text
    assert len(app.dataframe) == 1


@needs_data
def test_a_conversation_that_used_its_questions_asks_for_a_new_one(live_app):
    app = live_app
    app.chat_input[0].set_value("Why did paid amounts jump?").run()
    chat = FakeSession.instances[-1]
    chat.asked = chat.config.max_questions
    app.run()
    assert len(app.chat_input) == 0
    assert any("used its 10 questions" in i.value for i in app.info)


@needs_data
def test_each_live_answer_can_be_rated_with_a_note_on_what_was_wrong(live_app):
    app = live_app
    app.chat_input[0].set_value("Why did paid amounts jump?").run()
    chat = FakeSession.instances[-1]
    assert chat.ratings == [] and not app.text_input

    app.feedback[0].set_value(0).run()  # thumbs down
    app.run()  # a rerun doesn't record it twice
    assert chat.ratings == [("r-1", False, None)]
    app.text_input[0].set_value("It missed the reload batch.").run()
    assert chat.ratings[-1] == ("r-1", False, "It missed the reload batch.")
    app.feedback[0].set_value(1).run()  # changed their mind
    assert chat.ratings[-1] == ("r-1", True, None) and len(chat.ratings) == 3
    assert not app.exception


@needs_data
def test_a_guided_step_can_be_asked_live_as_the_role_that_asked_it(live_app):
    app = live_app
    app.radio[0].set_value("Guided demo").run()
    click(app, "Start the tour")
    click(app, "Ask the agent this yourself")
    assert not app.exception and app.radio[0].value == "Live"
    chat = FakeSession.instances[-1]
    assert chat.role == "actuarial_analyst" and chat.asked == 1
    assert "What was the motor claim frequency by state in Q2 2026?" in " ".join(
        m.value for m in app.markdown)
