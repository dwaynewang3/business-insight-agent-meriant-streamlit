"""Record compliance verdicts from an eval run in the warehouse, for portfolio questions such
as "what are the most common breach types?" (design §3.6, replanned 2026-10-18).

    uv run python -m data.compliance.results evals/results/<compliance run>

Takes each claim file's first successful review in the run (repeat 1), writes them to
data/compliance/review_results.jsonl, and loads that into compliance_results and
compliance_findings in both warehouse copies. `make data` loads the same file, so rebuilding
keeps them. It's run by a person, never by the model, and only while no session has the
warehouse open (DuckDB allows one writer). No model is called: the verdicts were paid for
when the eval ran.
"""

import argparse
import json
import time
from pathlib import Path

import duckdb

from mcp_servers.warehouse.access import restricted_path

from .build import REVIEW_RESULTS, load_review_results

DEFAULT_WAREHOUSE = Path("data/dev.duckdb")


def rows_from_run(folder: Path) -> list[dict]:
    """One row per claim file: the verdict and its findings, from the run's repeat-1 reviews."""
    rows = []
    for path in sorted(folder.glob("reviews/*-r1.json")):
        review = json.loads(path.read_text())["review"]
        if review["error"] or review["overall"] is None:
            continue
        findings = [{"check": f["check"], "status": f["status"], "severity": f["severity"],
                     "rule": f["rule"],
                     "clauses": "; ".join(f"{c['clause_id']} v{c['version']}"
                                          for c in f.get("clauses", []) if c["version"]),
                     "validation_failed": bool(f.get("validation_failed"))}
                    for f in review["findings"]]
        models = sorted({c["model_served"] for c in review["model_calls"]})
        rows.append({
            "claim_id": review["claim_id"], "overall": review["overall"],
            "breaches": sum(f["status"] == "BREACH" for f in findings),
            "needs_review": sum(f["status"] == "NEEDS_REVIEW" for f in findings),
            # "POL-AUT-003 v3.1", not the review's "POL-AUT-003@3.1", which the personal-data
            # scan reads as an email address.
            "policy_versions": "; ".join(v.replace("@", " v")
                                         for v in review.get("policy_versions", [])),
            "variant": review["variant"], "model": ", ".join(models),
            "reviewed_on": time.strftime("%Y-%m-%d", time.localtime(path.stat().st_mtime)),
            "run_id": review["run_id"], "findings": findings})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path, help="a compliance eval run's results folder")
    parser.add_argument("--warehouse", type=Path, default=DEFAULT_WAREHOUSE)
    args = parser.parse_args()
    rows = rows_from_run(args.folder)
    if not rows:
        raise SystemExit(f"No successful repeat-1 reviews in {args.folder}.")
    REVIEW_RESULTS.write_text("".join(json.dumps(row) + "\n" for row in rows))
    for path in (args.warehouse, restricted_path(args.warehouse)):
        with duckdb.connect(str(path)) as con:
            load_review_results(con)
    print(f"Recorded {len(rows)} verdicts from {args.folder} in {REVIEW_RESULTS} and both "
          "warehouse copies.")


if __name__ == "__main__":
    main()
