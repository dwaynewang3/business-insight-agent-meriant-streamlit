"""The UI's logic, apart from Streamlit so it can be tested.

- Source labels: a query is an "Agreed metric" if its result is the result of an agreed metric
  computed in this run: the same rows and the same numbers, allowing only for rounding. The
  agent usually gets its number from an agreed metric and then writes a shorter query of its
  own as the answer's SQL, so the SQL text rarely matches while the numbers do. Code decides
  this by running both queries, not the model, so the model can't label its own query as an
  agreed metric.
- Step labels: what to show for each trace event while a question runs.
- Key numbers: a rounded number is marked, with the exact value from its finding's query on
  hover, and a number its query doesn't contain is marked "not confirmed". The exact value
  comes from the query, not the model.
- Saved runs: the eval results, shown without an API key. Runs on the earlier US
  version of the data are in `archive-us-data/`, shown as history. Each run's charts and data
  are re-run on the warehouse it queried (the dev data, or the held-out test data).
"""

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path

from agent.citations import is_returned, returned_clauses
from agent.key_numbers import Result, as_number, is_rounded, scaled_match, source_value
from app.guide import GUIDE
from mcp_servers.warehouse.access import restricted_path

AGREED, CUSTOM = "Agreed metric", "Custom query"
RESULTS_DIR = Path("evals/results")
DEV_WAREHOUSE = Path("data/dev.duckdb")  # for runs saved before records named their warehouse
ARCHIVE = "archive-us-data"  # runs on the earlier US version of the data
VERDICT_ICONS = {"supported": "✅", "ruled_out": "❌", "inconclusive": "❔"}
# The guided demo's runs (app/guide.py), in its order, as run folder/case. They're also listed
# first among the saved runs.
DEMO_RUNS = tuple(step.run for step in GUIDE)


def _normalized(sql: str) -> str:
    return re.sub(r"\s+", " ", sql or "").strip().rstrip(";").lower()


def agreed_sql(tool_calls: list[dict]) -> list[str]:
    """The SQL of each agreed metric computed in this run, once each."""
    return list(dict.fromkeys(call["sql"] for call in tool_calls
                              if call.get("source") == "agreed_metric" and call.get("sql")))


_MONTH_START = re.compile(r"(\d{4}-\d{2})-01(?:[ t]00:00:00)?")


def _split(row: list) -> tuple[frozenset[str], list[float]]:
    """A result row as its labels (state, month, product) and its numbers. The first day of
    a month reads as the month, so 2026-06-01 and 2026-06 are the same label."""
    labels, numbers = set(), []
    for cell in row:
        if (number := as_number(cell)) is not None:
            numbers.append(number)
        elif cell is not None:
            text = str(cell).strip().lower()
            month = _MONTH_START.fullmatch(text)
            labels.add(month[1] if month else text)
    return frozenset(labels), numbers


def from_agreed_metrics(rows: list, agreed_results: list[list] | tuple) -> bool:
    """Whether every number in a query's result is an agreed metric's number for the same row.

    Each row is matched to an agreed result's row by its labels: the one row that carries all
    of them (a metric's result may carry more, such as the month), or the only row of a
    one-row result. A label that fits no row or several rows matches nothing. Each number
    must then be one of that row's numbers, allowing only for how it's written: rounded, or a
    fraction as a percentage. So the answer may show fewer rows than the metric returned (the
    top 3 of 8 states), but a single number of its own, such as a claim count beside the
    agreed average or a figure with duplicate payments removed, makes it a custom query."""
    results = [[_split(row) for row in agreed] for agreed in agreed_results if agreed]
    found = False
    for row in rows or []:
        labels, numbers = _split(row)
        exact = []
        for result in results:
            fits = result if len(result) == 1 else [r for r in result if labels <= r[0]]
            if len(fits) == 1:
                exact += fits[0][1]
        for number in numbers:
            if not any(scaled_match(number, cell, "") is not None for cell in exact):
                return False
            found = True
    return found


def source_label(sql: str | None, tool_calls: list[dict], rows: list | None = None,
                 agreed_rows: list[list] | tuple = ()) -> str | None:
    """rows: the query's result; agreed_rows: the result of each agreed metric in this run.
    Without them (the queries can't be re-run), only the SQL text can match."""
    if not sql:
        return None
    if _normalized(sql) in {_normalized(agreed) for agreed in agreed_sql(tool_calls)}:
        return AGREED
    if rows is not None and from_agreed_metrics(rows, agreed_rows):
        return AGREED
    return CUSTOM


def markdown_text(text: str, html_too: bool = False) -> str:
    """Model text for st.markdown. Streamlit reads "$...$" as LaTeX, which garbles amounts
    such as "$10,626 to $13,368", so dollar signs are escaped. With html_too, for markdown
    that allows HTML, tags are escaped too: the model's text can echo claim notes, which are
    untrusted data."""
    return (html.escape(text) if html_too else text).replace("$", "\\$")


def exact_text(value: float) -> str:
    """An exact value with about six significant digits: 53.6245, 441,201.8."""
    decimals = max(2, 6 - len(str(int(abs(value)))))
    return f"{value:,.{decimals}f}".rstrip("0").rstrip(".")


def key_number_html(number: dict, result: Result | None) -> str:
    """A key number as written, marked "rounded" with the exact value on hover when it's a
    rounding of its cell in its finding's query result, and "not confirmed" when that cell
    doesn't hold it. With result None (the query wasn't re-run, or failed), it's shown as
    written. For markdown that allows HTML."""
    shown = markdown_text(f"{number['label']}: {number['value']:,} {number['unit']}",
                          html_too=True)
    if result is None:
        return shown
    exact = source_value(number, result)
    if exact is None:
        return (f'{shown} <abbr title="Not found in its place in the result of this '
                f'finding\'s query, so it can\'t be traced to the SQL shown">(not confirmed)'
                f'</abbr>')
    if not is_rounded(float(number["value"]), exact):
        return shown
    return (f'{shown} <abbr title="Rounded. Exact value from the query: '
            f'{exact_text(exact)}">(rounded)</abbr>')


def citation_label(citation: dict, tool_calls: list[dict],
                   in_force: tuple[str, str | None] | None = None) -> str:
    """A cited clause, with the dates its version was in force (from the knowledge base) and
    whether a tool returned it in this answer (code decides)."""
    mark = ("returned by a tool in this answer"
            if is_returned(citation, returned_clauses(tool_calls))
            else "not returned by any tool in this answer")
    version = f", v{citation['version']}" if citation["version"] else ", no version given"
    dates = ""
    if in_force:
        start, end = in_force
        dates = f", in force {start} to {end}" if end else f", in force from {start}"
    return f"{citation['clause_id']}{version}{dates} ({mark})"


STATUS_ICONS = {"BREACH": "❌", "NEEDS_REVIEW": "⚠️", "PASS": "✅", "NOT_APPLICABLE": "–",
                "NOT_ASSESSED": "❔"}
VERDICTS = {"NON_COMPLIANT": "Non-compliant", "NEEDS_REVIEW": "Needs review",
            "COMPLIANT": "Compliant"}


def compliance_reviews(tool_calls: list[dict]) -> list[dict]:
    """The compliance reviews run in this answer, for the verdict card."""
    return [call["compliance"] for call in tool_calls
            if call.get("tool") == "check_claim_compliance" and call.get("compliance")
            and call["compliance"].get("findings")]


def verdict_title(review: dict) -> str:
    counts = {s: sum(f["status"] == s for f in review["findings"])
              for s in ("BREACH", "NEEDS_REVIEW")}
    breaches = "breach" if counts["BREACH"] == 1 else "breaches"
    parts = [f"{n} {label}" for n, label in ((counts["BREACH"], breaches),
                                             (counts["NEEDS_REVIEW"], "to review")) if n]
    return (f"Compliance review of {review['claim_id']}: "
            f"{VERDICTS.get(review['overall'], review['overall'])}"
            + (f" ({', '.join(parts)})" if parts else ""))


def verdict_rows(review: dict) -> list[dict]:
    """One row per finding, problems first: breaches, then items to review, then the rest."""
    order = {"BREACH": 0, "NEEDS_REVIEW": 1, "NOT_ASSESSED": 2, "PASS": 3, "NOT_APPLICABLE": 4}
    rows = []
    for finding in sorted(review["findings"], key=lambda f: order.get(f["status"], 5)):
        clauses = ", ".join(f"{c['clause_id']} v{c['version']}" if c.get("version")
                            else f"{c['clause_id']} (not supplied)"
                            for c in finding.get("clauses") or [])
        rows.append({
            "Area": finding["check"].replace("_", " "),
            "Status": f"{STATUS_ICONS.get(finding['status'], '')} "
                      f"{finding['status'].replace('_', ' ').lower()}".strip(),
            "Severity": "" if finding["severity"] == "NONE" else finding["severity"].lower(),
            "Rule": finding["rule"] + (" (failed the code checks)"
                                       if finding.get("validation_failed") else ""),
            "Clauses": clauses})
    return rows


def step_label(event: dict) -> str | None:
    """A short line for a trace event, or None for events that aren't steps."""
    kind = event.get("event")
    if kind == "tool_call":
        tool = event.get("tool", "tool")
        detail = event.get("input", {})
        if tool == "run_sql":
            text = "Running a query"
        elif tool == "query_metric":
            text = f"Computing the agreed metric {detail.get('metric', '')}".rstrip()
        elif tool == "get_metric":
            text = f"Looking up the definition of {detail.get('name') or 'every metric'}"
        elif tool == "check_data_quality":
            text = f"Checking data quality in {detail.get('table', 'a table')}"
        elif tool == "describe_table":
            text = f"Reading the {detail.get('table', '')} table's columns"
        elif tool == "search_catalog":
            text = f"Searching the catalog for \"{detail.get('query', '')}\""
        elif tool == "search_policies":
            text = f"Searching the policies for \"{detail.get('query', '')}\""
        elif tool == "get_policy_clause":
            text = f"Reading policy clause {detail.get('clause_id', '')}".rstrip()
        elif tool == "check_claim_compliance":
            text = f"Reviewing {detail.get('claim_id', 'a claim')} against the policies"
        else:
            text = f"Calling {tool}"
        if event.get("repeat"):
            return f"{text} again: the same call already ran, so it wasn't repeated"
        if "error" in event:
            return f"{text}: failed, so the agent will adjust"
        rows = event.get("rows")
        return f"{text}{f' ({rows} rows)' if rows is not None else ''}"
    if kind == "model_call":
        return f"Claude is reasoning (US${event.get('cost_usd', 0):.3f})"
    if kind == "number_check":
        missing = len(event.get("unconfirmed", []))
        return (f"Checked {event.get('checked', 0)} key numbers against their queries"
                + (f": {missing} not found" if missing else ": all confirmed"))
    return None


@dataclass(frozen=True)
class SavedRun:
    title: str
    path: Path
    record: dict
    archived: bool = False  # on the earlier US data: its SQL doesn't match today's warehouse
    warehouse: Path = DEV_WAREHOUSE  # the warehouse the run queried

    def data_note(self) -> str | None:
        """Why the run's charts and data can't be re-run, or None when they can."""
        if self.archived:
            return "the warehouse has changed since this run"
        if not (self.warehouse.exists() and restricted_path(self.warehouse).exists()):
            return (f"this run queried {self.warehouse}, which isn't built here "
                    "(`make data`, or `make test-data` for the held-out test data)")
        return None


def load_saved_runs(results_dir: Path = RESULTS_DIR) -> list[SavedRun]:
    """Every saved eval case with a report: the demo script's runs in its order, then the other
    runs on today's data, then the archived runs on the earlier US data, newest first within
    each."""
    runs, demo = [], {}
    for pattern, archived in (("*/cases/*.json", False), (f"{ARCHIVE}/*/cases/*.json", True)):
        for path in sorted(results_dir.glob(pattern), reverse=True):
            if not archived and path.parts[-3] == ARCHIVE:
                continue
            record = json.loads(path.read_text())
            if not record.get("report"):
                continue
            first = record.get("first", {}).get("question")
            question = f"{first} → {record['question']}" if first else record["question"]
            repeat = f" (run {record['repeat']})" if record.get("repeat", 1) > 1 else ""
            label = "[US data, archived] " if archived else ""
            warehouse = Path(record.get("warehouse") or DEV_WAREHOUSE)
            name = f"{path.parent.parent.name}/{path.stem}"
            if name in DEMO_RUNS:
                step = DEMO_RUNS.index(name) + 1
                demo[step] = SavedRun(f"Demo {step} of {len(DEMO_RUNS)}  ·  {question[:90]}",
                                      path, record, archived, warehouse)
                continue
            runs.append(SavedRun(f"{label}{question[:90]}{repeat}  ·  {path.parent.parent.name}",
                                 path, record, archived, warehouse))
    return [demo[step] for step in sorted(demo)] + runs
