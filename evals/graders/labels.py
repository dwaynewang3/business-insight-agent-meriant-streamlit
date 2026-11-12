"""Check the LLM grader against your own labels (DEV_PLAN.md section 9).

1. Write a sheet of "why" answers to label:
       uv run python -m evals.graders.labels sheet evals/results/<run> [<run> ...]
   It writes evals/labels/why_labels.csv, with the question, the answer key, the agent's
   answer and the explanations it tested, plus the LLM grader's verdict if there is one.
   Repeat runs of a case are separate rows: their case_id ends in .r2, .r3 and so on.
2. Fill in `your_verdict` (pass or fail) for each row, in a spreadsheet or a text editor,
   without looking at `llm_verdict` first if you can.
3. Measure agreement:
       uv run python -m evals.graders.labels agreement
"""

import argparse
import csv
import json
from pathlib import Path

from evals.cases import load_why_cases

from .llm import DEFAULT_MANIFEST, expected_explanation

SHEET = Path("evals/labels/why_labels.csv")
COLUMNS = ["run", "case_id", "kind", "question", "answer_key", "agent_answer",
           "explanations_tested", "llm_verdict", "llm_reason", "your_verdict", "your_notes"]


def write_sheet(folders: list[Path], out: Path = SHEET,
                manifest_path: Path = DEFAULT_MANIFEST) -> int:
    manifest = json.loads(manifest_path.read_text())
    cases = {case.id: case for case in load_why_cases()}
    existing = {(r["run"], r["case_id"]): r for r in read_sheet(out)} if out.exists() else {}
    rows = []
    for folder in folders:
        llm = folder / "llm_grades.json"
        grades = json.loads(llm.read_text())["grades"] if llm.exists() else {}
        for path in sorted((folder / "cases").glob("why-*.json")):
            record = json.loads(path.read_text())
            report = record["report"]
            if report is None:
                continue
            case = cases[record["case_id"]]
            grade = grades.get(path.stem, {})
            previous = existing.get((folder.name, path.stem), {})
            rows.append({
                "run": folder.name,
                "case_id": path.stem,
                "kind": case.kind,
                "question": case.question,
                "answer_key": expected_explanation(case, manifest),
                "agent_answer": report["answer"],
                "explanations_tested": " | ".join(
                    f"{h['verdict']}: {h['hypothesis']}" for h in report.get("hypotheses", [])),
                "llm_verdict": ("pass" if grade.get("passed") else "fail") if grade else "",
                "llm_reason": grade.get("reason", ""),
                # Labels already filled in are kept when the sheet is rewritten.
                "your_verdict": previous.get("your_verdict", ""),
                "your_notes": previous.get("your_notes", ""),
            })
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as sheet:
        writer = csv.DictWriter(sheet, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def read_sheet(path: Path = SHEET) -> list[dict]:
    with path.open(newline="") as sheet:
        return list(csv.DictReader(sheet))


def agreement(rows: list[dict]) -> dict:
    """How often the LLM grader agrees with your labels, on the rows that have both."""
    labeled = [r for r in rows if r["your_verdict"].strip().lower() in ("pass", "fail")
               and r["llm_verdict"] in ("pass", "fail")]
    agree = [r for r in labeled if r["your_verdict"].strip().lower() == r["llm_verdict"]]
    return {
        "labeled": len(labeled),
        "agree": len(agree),
        "disagreements": [(r["case_id"], r["your_verdict"], r["llm_verdict"])
                          for r in labeled if r not in agree],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    sheet = commands.add_parser("sheet", help="write the sheet of answers to label")
    sheet.add_argument("folders", nargs="+", type=Path)
    commands.add_parser("agreement", help="compare your labels with the LLM grader's")
    args = parser.parse_args()
    if args.command == "sheet":
        count = write_sheet(args.folders)
        print(f"Wrote {count} answers to {SHEET}. Fill in your_verdict (pass or fail).")
    else:
        result = agreement(read_sheet())
        print(f"The LLM grader agrees with you on {result['agree']} of {result['labeled']} "
              "labeled answers.")
        for case_id, yours, llm in result["disagreements"]:
            print(f"  {case_id}: you said {yours}, the grader said {llm}")


if __name__ == "__main__":
    main()
