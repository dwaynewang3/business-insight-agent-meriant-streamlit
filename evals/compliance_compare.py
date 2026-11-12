"""Compare compliance variants: one table across result folders, with the development and
held-out claim files shown separately (design §3.9, B7).

    uv run python -m evals.compliance_compare evals/results/<v0 run> <v1 run> <full run>

Reads each folder's repeat-1 reviews and grades, so it costs nothing. Writes the table to
stdout, ready for docs/results.md.
"""

import argparse
import json
from pathlib import Path

from evals.graders.compliance import summarise

METRICS = (
    ("Overall right", lambda s: f"{s['overall_correct']}/{s['claims']}"),
    ("Required findings", lambda s: f"{s['required_detected']}/{s['required_findings']}"),
    ("Strict citations", lambda s: f"{s['strict_citation_rate']}"),
    ("False breaches", lambda s: f"{s['false_breaches']}"),
    ("Traps and controls", lambda s: f"{s['traps_and_controls_right']}/{s['traps_and_controls']}"),
    ("Invented citations", lambda s: f"{s['invented_citations']}"),
    ("Errors", lambda s: f"{s['errors']}"),
)


def load(folder: Path) -> tuple[str, list[dict], list[dict]]:
    records = [json.loads(p.read_text()) for p in sorted(folder.glob("reviews/*-r1.json"))]
    return (records[0]["review"]["variant"], [r["grade"] for r in records],
            [r["review"] for r in records])


def table(folders: list[Path]) -> str:
    variants = [load(folder) for folder in folders]
    header = "| Metric | " + " | ".join(
        f"{name} ({part})" for name, _, _ in variants for part in ("dev", "held out")) + " |"
    lines = [header, "|" + " --- |" * (1 + 2 * len(variants))]
    parts = [(summarise([g for g in grades if not g["held_out"]]),
              summarise([g for g in grades if g["held_out"]])) for _, grades, _ in variants]
    for label, show in METRICS:
        lines.append(f"| {label} | " + " | ".join(show(s) for pair in parts for s in pair) + " |")
    lines += ["", "| Variant | All 27: overall | Required | Cost per claim (batch) | Judge calls "
                  "per claim |", "| --- | --- | --- | --- | --- |"]
    for name, grades, reviews in variants:
        total = summarise(grades)
        cost = sum(r["cost_usd"] for r in reviews) / len(reviews)
        calls = sum(len(r["model_calls"]) for r in reviews) / len(reviews)
        lines.append(f"| {name} | {total['overall_correct']}/{total['claims']} | "
                     f"{total['required_detected']}/{total['required_findings']} | "
                     f"${cost:.3f} | {calls:.1f} |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folders", nargs="+", type=Path)
    print(table(parser.parse_args().folders))


if __name__ == "__main__":
    main()
