"""Attack the key-number check: how often does it confirm a number that's been made wrong?

Takes every key number in the held-out runs, re-runs its finding's SQL on the test warehouse,
and names the cell the number came from (as a report written since 2026-11-17 does). Then it
makes each number wrong in two ways and checks it the old way, anywhere in the result, and
the new way, against its own cell:

- shifted: the value moved 10% or 25% up or down, after rounding to the precision written
- swapped: the value of another key number in the same finding, with the label kept, as when
  one state's figure is reported as another's

Needs `make test-data`; makes no API calls.

    uv run python -m evals.number_check_attack
"""

import argparse
import glob
import json
from pathlib import Path

from agent.key_numbers import as_number, cell_values, matches
from mcp_servers.warehouse import Limits, QueryError, run_query

LIMITS = Limits(max_rows=10_000, max_chars=10_000_000)
RUNS = "evals/results/20261019-20*-test-final-*/cases/*.json"


def confirmed(number: dict, result) -> bool:
    cells, problem = cell_values(number, result)
    return not problem and any(matches(number["value"], cell, number.get("unit", ""))
                               for cell in cells)


def name_cell(number: dict, result) -> dict | None:
    """The number with the cell it came from: the closest matching cell (its row named by
    the row's text and date columns, or by every other column when those don't pick out one
    row), or a column whose total or average matches. None if nothing matches."""
    columns, rows = result
    value, unit = float(number["value"]), number.get("unit", "")
    best = None
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            n = as_number(cell)
            if n is not None and matches(value, n, unit):
                gap = abs(abs(value) - abs(n))
                if best is None or gap < best[0]:
                    best = (gap, r, c)
    if best is None:
        totals = (dict(number, column=name, row="") for name in columns)
        return next((n for n in totals if confirmed(n, result)), None)
    _, r, c = best
    if len(rows) == 1:
        return dict(number, column=columns[c], row="")
    keys = [k for k in range(len(columns)) if k != c and as_number(rows[r][k]) is None]
    if sum(all(row[k] == rows[r][k] for k in keys) for row in rows) != 1:
        keys = [k for k in range(len(columns)) if k != c]
    return dict(number, column=columns[c],
                row="; ".join(f"{columns[k]} = {rows[r][k]}" for k in keys))


def _decimals(value: float) -> int:
    text = repr(float(value))
    return len(text.split(".")[1].rstrip("0")) if "." in text else 0


def attack(runs: str, warehouse: Path) -> dict:
    findings = []
    for path in sorted(glob.glob(runs)):
        report = json.loads(Path(path).read_text()).get("report") or {}
        for finding in report.get("findings") or []:
            numbers = [n for n in finding.get("key_numbers") or []
                       if as_number(n.get("value")) is not None]
            if not finding.get("evidence_sql") or not numbers:
                continue
            try:
                query = run_query(warehouse, finding["evidence_sql"], LIMITS)
            except QueryError:
                continue
            result = (query.columns, query.rows)
            findings.append((result, [(n, name_cell(n, result)) for n in numbers]))
    named = [(n, cell, result) for result, numbers in findings for n, cell in numbers if cell]
    summary = {"key_numbers": sum(len(numbers) for _, numbers in findings),
               "with_a_cell": len(named),
               "originals_confirmed": sum(confirmed(cell, r) for _, cell, r in named)}
    for shift in (0.10, 0.25):
        old = new = cases = 0
        for number, cell, result in named:
            for sign in (-1, 1):
                wrong = round(float(number["value"]) * (1 + sign * shift),
                              _decimals(number["value"]))
                if wrong == float(number["value"]):
                    continue
                cases += 1
                old += confirmed(dict(number, value=wrong), result)
                new += confirmed(dict(cell, value=wrong), result)
        summary[f"shifted_{shift:.0%}"] = {"cases": cases, "old": old, "new": new}
    old = new = cases = 0
    for result, numbers in findings:
        pairs = [(n, cell) for n, cell in numbers if cell]
        for number, cell in pairs:
            for other, _ in pairs:
                if matches(float(other["value"]), float(number["value"]), number.get("unit", "")):
                    continue  # the same number as written
                cases += 1
                old += confirmed(dict(number, value=other["value"]), result)
                new += confirmed(dict(cell, value=other["value"]), result)
    summary["swapped"] = {"cases": cases, "old": old, "new": new}
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--runs", default=RUNS, help="saved cases to take key numbers from")
    parser.add_argument("--warehouse", type=Path, default=Path("data/test.duckdb"))
    args = parser.parse_args()
    summary = attack(args.runs, args.warehouse)
    print(f"{summary['key_numbers']} key numbers; {summary['with_a_cell']} matched a cell, "
          f"and {summary['originals_confirmed']} of those are confirmed against it.")
    for name in ("shifted_10%", "shifted_25%", "swapped"):
        row = summary[name]
        print(f"{name.replace('_', ' ')}: the old check confirms {row['old']}/{row['cases']}, "
              f"the new one {row['new']}/{row['cases']}")


if __name__ == "__main__":
    main()
