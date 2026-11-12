"""How a number written in a report relates to the query result it came from.

The agent checks each report's key numbers against their findings' own SQL before the answer
goes out, the eval runner counts how many it confirms, and the UI shows the exact value behind
a rounded number and marks a number its query doesn't confirm. Either way the value comes from
the query, not from the model.

Matching allows for how people write numbers:
- A value in the result, or the total or average of a result column (a 2025 total summed
  from monthly rows). Differences and ratios between cells aren't tried: with many cells,
  one would match by chance.
- Rounding to the precision written: 53.6 matches 53.62, and 1,200,000 matches 1,234,567.
- A fraction written as a percentage or the other way round (0.536 and 53.6), and a rate
  per 1,000 when the unit says so.
- A change written without its sign ("fell 12%" as 12).
- Otherwise a 0.5% tolerance, the same as the "what" grader's.
"""

import math
import numbers
from collections.abc import Callable

from mcp_servers.warehouse import QueryError

RELATIVE_TOLERANCE = 0.005


def as_number(value: object) -> float | None:
    """A finite number, or None for text, booleans, missing values and NaN."""
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def step(value: float) -> float:
    """The rounding step a written number implies: 53.6 -> 0.1, 159 -> 1, 1,200,000 -> 100,000.

    Trailing zeros count as rounding only down to two significant figures, so 1,000 allows
    950-1,050 rather than anything from 500 to 1,500.
    """
    text = repr(float(value))
    if "e" in text or "E" in text:
        return 0.0  # too large or small to read a precision from; use the tolerance alone
    whole, _, decimals = text.partition(".")
    decimals = decimals.rstrip("0")
    if decimals:
        return 10.0 ** -len(decimals)
    digits = whole.lstrip("-")
    zeros = len(digits) - len(digits.rstrip("0")) if digits.strip("0") else 0
    return 10.0 ** max(0, min(zeros, len(digits) - 2))


def scales(unit: str) -> tuple[float, ...]:
    text = unit.lower().replace(",", "")
    return (1, 100, 0.01, 1000) if "1000" in text else (1, 100, 0.01)


def scaled_match(value: float, cell: float, unit: str) -> float | None:
    """The cell in the written number's scale and sign (a fraction shown as a percentage is
    multiplied by 100) if the written value is a fair rounding of it, otherwise None."""
    allowed = max(step(value) / 2, abs(value) * RELATIVE_TOLERANCE) + 1e-9 * max(1, abs(value))
    for scale in scales(unit):
        if abs(abs(value) - abs(cell * scale)) <= allowed:
            return math.copysign(abs(cell * scale), value)
    return None


def matches(value: float, cell: float, unit: str) -> bool:
    return scaled_match(value, cell, unit) is not None


def result_numbers(rows: list[tuple] | list[list]) -> list[float]:
    """Every number in a result, plus each numeric column's total and average."""
    cells = [number for row in rows for cell in row if (number := as_number(cell)) is not None]
    if len(rows) > 1:
        for column in zip(*rows, strict=True):
            values = [n for cell in column if (n := as_number(cell)) is not None]
            if len(values) > 1:
                cells += [sum(values), sum(values) / len(values)]
    return cells


def source_value(value: object, unit: str, rows: list[tuple] | list[list]) -> float | None:
    """The exact value behind a written number, in its scale: the closest match in the
    result, or None if nothing in it matches."""
    written = as_number(value)
    if written is None:
        return None
    found = [match for cell in result_numbers(rows)
             if (match := scaled_match(written, cell, unit)) is not None]
    return min(found, key=lambda match: abs(match - written)) if found else None


def is_rounded(written: float, exact: float) -> bool:
    return abs(exact - written) > 1e-9 * max(1, abs(written))


def check_numbers(report: dict | None, rows_for: Callable[[str], list]) -> dict:
    """How many of the report's key numbers its findings' SQL confirms, and which not.
    rows_for runs one finding's SQL through the SQL guard and returns its rows; a QueryError
    it raises is the reason that finding's numbers aren't confirmed."""
    checked, unconfirmed = 0, []
    for position, finding in enumerate((report or {}).get("findings") or []):
        key_numbers = finding.get("key_numbers") or []
        if not key_numbers:
            continue
        cells, problem = _cells(finding.get("evidence_sql") or "", rows_for)
        for number in key_numbers:
            checked += 1
            value = as_number(number.get("value"))
            if problem:
                reason = problem
            elif value is None:
                reason = "Not a number."
            elif any(matches(value, cell, number.get("unit", "")) for cell in cells):
                continue
            else:
                reason = "Not in the result of its finding's SQL."
            unconfirmed.append({"finding": position, "label": number.get("label"),
                                "value": number.get("value"), "unit": number.get("unit"),
                                "reason": reason})
    return {"checked": checked, "confirmed": checked - len(unconfirmed),
            "unconfirmed": unconfirmed}


def _cells(sql: str, rows_for: Callable[[str], list]) -> tuple[list[float], str | None]:
    if not sql.strip():
        return [], "The finding has no SQL."
    try:
        return result_numbers(rows_for(sql)), None
    except QueryError as failure:
        return [], f"Its SQL failed: {failure}"
