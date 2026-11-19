"""How a number written in a report relates to the query result it came from.

The agent checks each report's key numbers against their findings' own SQL before the answer
goes out, the eval runner counts how many it confirms, and the UI shows the exact value behind
a rounded number and marks a number its query doesn't confirm. Either way the value comes from
the query, not from the model.

Each key number names the cell it comes from: the result column (`column`) and the values
that pick out its row (`row`), such as "state = NSW; month = 2026-07". (The row is one string
rather than a list of pairs because a list of objects made the request's strict schemas too
large for the API to compile.) The number is
checked against that cell only, so a real number put on the wrong row, such as one state's
count reported as another's, isn't confirmed. With no row given, the number is the result's
only value in that column, or the column's total or average (a 2025 total summed from monthly
rows); when the row given matches several rows, it's their total or average.

Reports written before key numbers named their cell are checked the old way: the number may
match any value in the result, or any column's total or average.

Matching a cell allows for how people write numbers:
- Rounding to the precision written: 53.6 matches 53.62, and 1,200,000 matches 1,234,567.
- A fraction written as a percentage or the other way round (0.536 and 53.6), and a rate
  per 1,000 when the unit says so.
- A change written without its sign ("fell 12%" as 12).
- Otherwise a 0.5% tolerance, the same as the "what" grader's.
"""

import math
import numbers
from collections.abc import Callable, Sequence

from mcp_servers.warehouse import QueryError, reads_no_table

RELATIVE_TOLERANCE = 0.005

# A query result as the check needs it: its column names and its rows.
Result = tuple[Sequence[str], Sequence[Sequence]]


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


def result_numbers(rows: Sequence[Sequence]) -> list[float]:
    """Every number in a result, plus each numeric column's total and average."""
    cells = [number for row in rows for cell in row if (number := as_number(cell)) is not None]
    if len(rows) > 1:
        for column in zip(*rows, strict=True):
            cells += _total_and_average(column)
    return cells


def _total_and_average(cells: Sequence) -> list[float]:
    values = [n for cell in cells if (n := as_number(cell)) is not None]
    return [sum(values), sum(values) / len(values)] if len(values) > 1 else []


def same_value(cell: object, written: str) -> bool:
    """Whether a result cell is the value a key number gives to pick out its row: equal as
    numbers, as text ignoring case, or a date given to the month or year ("2026-07" for
    2026-07-01)."""
    text = written.strip()
    number, given = as_number(cell), _parse_number(text)
    if number is not None and given is not None:
        return math.isclose(number, given, rel_tol=1e-9, abs_tol=1e-9)
    shown = str(cell).strip()
    if shown.lower() == text.lower():
        return True
    return len(text) >= 4 and _looks_like_date(shown) and shown.startswith(text) \
        and shown[len(text):len(text) + 1] in ("-", "T", " ")


def _parse_number(text: str) -> float | None:
    try:
        return as_number(float(text.replace(",", "")))
    except ValueError:
        return None


def _looks_like_date(text: str) -> bool:
    return len(text) >= 7 and text[:4].isdigit() and text[4] == "-"


def row_pairs(row: str) -> list[tuple[str, str]] | None:
    """The column and value pairs in a key number's row ("state = NSW; month = 2026-07"), or
    None if a part isn't written as column = value."""
    pairs = []
    for part in filter(str.strip, row.split(";")):
        column, equals, value = part.partition("=")
        if not equals or not column.strip():
            return None
        pairs.append((column.strip(), value.strip().strip("'\"")))
    return pairs


def cell_values(number: dict, result: Result) -> tuple[list[float], str | None]:
    """The values a key number may be a rounding of, and why there are none. A number that
    names its cell is checked against that cell (or the total or average of the rows its row
    values pick out); one from an older report, which names no cell, against the whole
    result."""
    columns, rows = result
    if "column" not in number:
        return result_numbers(rows), None
    names = [str(name).lower() for name in columns]
    wanted = str(number.get("column") or "").strip().lower()
    if wanted not in names:
        return [], (f"Its column, {number.get('column')!r}, isn't in the result of its "
                    f"finding's SQL (columns: {', '.join(map(str, columns))}).")
    index = names.index(wanted)
    pairs = row_pairs(str(number.get("row") or ""))
    if pairs is None:
        return [], (f"Its row, {number.get('row')!r}, isn't written as column = value pairs "
                    "separated by semicolons.")
    picked = list(rows)
    for key, value in pairs:
        if key.lower() not in names:
            return [], f"Its row names a column, {key!r}, the result doesn't have."
        position = names.index(key.lower())
        picked = [row for row in picked if same_value(row[position], value)]
    if not picked:
        return [], f"No row in the result has {'; '.join(f'{k} = {v}' for k, v in pairs)}."
    cells = [row[index] for row in picked]
    values = [n for cell in cells if (n := as_number(cell)) is not None]
    if not values:
        return [], f"Its cell in {number['column']!r} isn't a number."
    if len(picked) == 1:
        return values, None
    return _total_and_average(cells) or values, None


def source_value(number: dict, result: Result) -> float | None:
    """The exact value behind a written number, in its scale: the closest of the values its
    cell allows, or None if none of them matches."""
    written = as_number(number.get("value"))
    if written is None:
        return None
    cells, _ = cell_values(number, result)
    found = [match for cell in cells
             if (match := scaled_match(written, cell, number.get("unit", ""))) is not None]
    return min(found, key=lambda match: abs(match - written)) if found else None


def is_rounded(written: float, exact: float) -> bool:
    return abs(exact - written) > 1e-9 * max(1, abs(written))


def check_numbers(report: dict | None, result_for: Callable[[str], Result]) -> dict:
    """How many of the report's key numbers its findings' SQL confirms, and which not.
    result_for runs one finding's SQL through the SQL guard and returns its columns and
    rows; a QueryError it raises is the reason that finding's numbers aren't confirmed."""
    checked, unconfirmed = 0, []
    for position, finding in enumerate((report or {}).get("findings") or []):
        key_numbers = finding.get("key_numbers") or []
        if not key_numbers:
            continue
        result, problem = _result(finding.get("evidence_sql") or "", result_for)
        for number in key_numbers:
            checked += 1
            value = as_number(number.get("value"))
            cells, missing = cell_values(number, result) if result else ([], None)
            if problem or missing:
                reason = problem or missing
            elif value is None:
                reason = "Not a number."
            elif any(matches(value, cell, number.get("unit", "")) for cell in cells):
                continue
            elif "column" in number:
                reason = "Not the value in its cell of its finding's SQL result."
            else:
                reason = "Not in the result of its finding's SQL."
            unconfirmed.append({"finding": position, "label": number.get("label"),
                                "value": number.get("value"), "unit": number.get("unit"),
                                "reason": reason})
    return {"checked": checked, "confirmed": checked - len(unconfirmed),
            "unconfirmed": unconfirmed}


def _result(sql: str, result_for: Callable[[str], Result]) -> tuple[Result | None, str | None]:
    if not sql.strip():
        return None, "The finding has no SQL."
    if reads_no_table(sql):
        # SELECT 638 AS claims would "confirm" any number it repeats.
        return None, ("Its SQL reads no warehouse table, so it can't show where the number "
                      "comes from.")
    try:
        return result_for(sql), None
    except QueryError as failure:
        return None, f"Its SQL failed: {failure}"
