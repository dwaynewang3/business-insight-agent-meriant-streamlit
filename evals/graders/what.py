"""Grade a "what" answer by re-running its SQL and comparing the result with the reference.

The grader never trusts numbers written in the answer text. It runs the report's
`answer_sql` through the SQL guard (the agent's SQL is untrusted) and compares the result
table with each reference query's result. Any one matching reference is a pass.

The comparison follows the rules at the top of evals/cases/what.yaml:
- Column names and order don't matter. Each reference column is matched to the agent's
  column whose values fit it.
- Keys are compared by kind: case-insensitive text, a state's code or name, any date in a
  month, an adjuster's or repair shop's ID or name.
- Numbers match within 0.5%. A ratio can be a fraction or a percentage (0.25 or 25), and
  ratios and days also allow small rounding (0.05 points).
- A row whose values are all zero counts the same as a missing row.
"""

import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from agent.key_numbers import RELATIVE_TOLERANCE
from evals.cases.loader import STATE_NAMES, WhatCase
from mcp_servers.warehouse import Limits, QueryError, connect, run_query

ABSOLUTE_TOLERANCE = {"ratio": 0.0005, "days": 0.05}
# Grading reads the whole result, not the capped version the model sees.
GRADING_LIMITS = Limits(timeout_seconds=30, max_rows=10_000, max_chars=10_000_000)

CATEGORIES = ("pass", "safety_violation", "wrong_result", "sql_error", "wrong_status",
              "missing_evidence", "missing_data_quality", "wrong_explanation", "no_answer",
              "unscored", "error")


@dataclass(frozen=True)
class Table:
    columns: tuple[str, ...]
    rows: tuple[tuple, ...]


@dataclass(frozen=True)
class Grade:
    passed: bool
    category: str  # CATEGORIES: "error" is a run failure (API, budget, cut-off), not a wrong answer
    reason: str


class WhatGrader:
    def __init__(self, db_path: str | Path):
        self.db_path = db_path
        self._references: dict[str, list[Table]] = {}
        con = connect(db_path)
        try:
            self.adjusters = dict(con.execute("SELECT adjuster_id, full_name FROM adjusters")
                                  .fetchall())
            self.shops = dict(con.execute("SELECT repair_shop_id, name FROM repair_shops")
                              .fetchall())
        finally:
            con.close()
        self.state_codes = {_text(name): code for code, name in STATE_NAMES.items()}

    def references(self, case: WhatCase) -> list[Table]:
        if case.id not in self._references:
            self._references[case.id] = [self._run(sql) for sql in case.reference_sql]
        return self._references[case.id]

    def grade(self, case: WhatCase, report: dict | None, error: str | None = None,
              **_context) -> Grade:
        if report is None:
            return Grade(False, "error", error or "No report.")
        if report.get("status") != "answered":
            return Grade(False, "no_answer", f"Status was {report.get('status')!r}.")
        sql = (report.get("answer_sql") or "").strip()
        if not sql:
            return Grade(False, "no_answer", "The report has no answer_sql.")
        try:
            answer = self._run(sql)
        except QueryError as failure:
            return Grade(False, "sql_error", f"answer_sql failed: {failure}")
        reasons = []
        for reference in self.references(case):
            reason = self.compare(case, reference, answer)
            if reason is None:
                return Grade(True, "pass", "Matches the reference.")
            reasons.append(reason)
        return Grade(False, "wrong_result", " | ".join(dict.fromkeys(reasons)))

    def compare(self, case: WhatCase, reference: Table, answer: Table) -> str | None:
        """None if the answer matches the reference, otherwise what's wrong."""
        keys, values = list(case.keys.items()), list(case.values.items())
        expected = {}
        for row in reference.rows:
            key = tuple(self._key(kind, v) for (_, kind), v in zip(keys, row, strict=False))
            numbers = row[len(keys):]
            if not all(_is_zero(n) for n in numbers):
                expected[key] = numbers

        used: set[int] = set()
        if not keys:
            if len(answer.rows) != 1:
                return f"Expected one row, got {len(answer.rows)}."
            got = {(): answer.rows[0]}
        else:
            key_columns = self._match_keys(keys, expected, answer)
            if key_columns is None:
                wanted = ", ".join(column for column, _ in keys)
                return f"No column in the answer matches the reference's {wanted}."
            got = {}
            for row in answer.rows:
                key = tuple(self._key(kind, row[i])
                            for (_, kind), i in zip(keys, key_columns, strict=True))
                if key in got:
                    return f"The answer has more than one row for {key}."
                got[key] = row
            used = set(key_columns)

        for position, (column, unit) in enumerate(values):
            candidates = [i for i in range(len(answer.columns)) if i not in used]
            match = next((i for i in candidates
                          if self._column_matches(expected, got, position, i, unit)), None)
            if match is None:
                return f"No column in the answer matches the reference's {column}."
        return None

    def _match_keys(self, keys, expected, answer: Table) -> list[int] | None:
        """For each reference key, the answer column holding the same set of values."""
        chosen: list[int] = []
        for position, (_, kind) in enumerate(keys):
            wanted = {key[position] for key in expected}
            for i in range(len(answer.columns)):
                if i in chosen:
                    continue
                found = {self._key(kind, row[i]) for row in answer.rows}
                if wanted <= found:
                    chosen.append(i)
                    break
            else:
                return None
        return chosen

    def _column_matches(self, expected, got, position: int, column: int, unit: str) -> bool:
        for key, numbers in expected.items():
            if key not in got or not _close(numbers[position], got[key][column], unit):
                return False
        # Rows the reference doesn't have must be zero (or empty) in this column.
        return all(_is_zero(row[column]) for key, row in got.items() if key not in expected)

    def _key(self, kind: str, value: object) -> object:
        if value is None:
            return None
        if kind == "state":
            text = str(value).strip()
            return text.upper() if text.upper() in STATE_NAMES else self.state_codes.get(
                _text(text), _text(text))
        if kind == "month":
            return _month(value)
        if kind in ("adjuster", "repair_shop"):
            names = self.adjusters if kind == "adjuster" else self.shops
            text = str(value).strip()
            if text.upper() in names:
                return text.upper()
            by_name = {_text(name): key for key, name in names.items()}
            return by_name.get(_text(text), _text(text))
        return _text(value)

    def _run(self, sql: str) -> Table:
        result = run_query(self.db_path, sql, GRADING_LIMITS)
        return Table(result.columns, result.rows)


def _text(value: object) -> str:
    return re.sub(r"[\s_\-]+", " ", str(value).strip().lower())


def _month(value: object) -> str | None:
    if isinstance(value, date | datetime):
        return f"{value.year:04d}-{value.month:02d}"
    text = str(value).strip()
    if match := re.match(r"(\d{4})-(\d{1,2})(?:\D|$)", text):
        return f"{match[1]}-{int(match[2]):02d}"
    for pattern in ("%B %Y", "%b %Y"):
        try:
            parsed = datetime.strptime(text, pattern)
            return f"{parsed.year:04d}-{parsed.month:02d}"
        except ValueError:
            pass
    return text


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return None if math.isnan(value) else float(value)


def _is_zero(value: object) -> bool:
    number = _number(value)
    return value is None or (number is not None and abs(number) < 1e-9)


def _close(expected: object, actual: object, unit: str) -> bool:
    want, got = _number(expected), _number(actual)
    if want is None or got is None:
        return want is None and got is None
    readings = [got, got / 100] if unit == "ratio" else [got]
    allowed = max(abs(want) * RELATIVE_TOLERANCE, ABSOLUTE_TOLERANCE.get(unit, 1e-9))
    return any(abs(reading - want) <= allowed for reading in readings)


class FollowUpGrader:
    """Grades a follow-up's answer exactly like the "what" case it names."""

    def __init__(self, what: WhatGrader):
        self.what = what

    def grade(self, case, report: dict | None, error: str | None = None, **context) -> Grade:
        return self.what.grade(case.grade_as, report, error, **context)
