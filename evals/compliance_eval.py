"""Run compliance reviews on the claim files and grade them (RAG_PLAN §9.3, design §3.9).

    uv run python -m evals.compliance_eval --variant v0 --split dev --max-cost 1.00
    uv run python -m evals.compliance_eval --variant v0 --claims GC-010 GC-009 --max-cost 0.20
    uv run python -m evals.compliance_eval --variant v1 --split all --batch --max-cost 2.00
    uv run python -m evals.compliance_eval --variant v1 --resume evals/results/<run> --batch \
        --max-cost 0.60

--batch sends the reviews through the Message Batches API at half price (results usually
within the hour); its cost is estimated before sending and checked against --max-cost and the
spend ledger's limit. --resume finishes a folder: only its missing or errored reviews run, and
the summary covers every review in it.

Splits: dev (18 claim files), held_out (9, for the final scoring only) or all. The grader is
checked before any paid call: every expected verdict must score 100% and an empty review must
fail. With --repeats N each claim is reviewed N times, every claim once before any repeats.
After the first 3 reviews the cost of the whole run is projected from them (the cost gate),
and the run stops there if it would pass --max-cost; it also stops once its cost passes it.
Results go to evals/results/<time>-<name>/: one JSON file per review, summary.json, summary.md, and
failures.jsonl with a diagnosis for every miss.
"""

import argparse
import json
import statistics
import time
from pathlib import Path

import anthropic
import duckdb
from dotenv import load_dotenv

from agent import costs
from agent.compliance import VARIANTS, ReviewConfig, review_claim, review_claims_batch
from agent.graph import DEFAULT_POLICY_KB, DEFAULT_WAREHOUSE
from agent.llm import ModelSettings
from agent.tools import _policy_library
from evals.graders.compliance import (
    ComplianceCase,
    grade,
    load_compliance_cases,
    reference_review,
    summarise,
)

RESULTS_DIR = Path(__file__).parent / "results"
# API errors that every later call would hit too, so the run stops instead of going on.
FATAL = ("credit balance is too low", "authentication_error", "permission_error")
# Measured live cost of one review (2026-10-18), for the estimate before a batch is sent.
LIVE_COST_PER_CLAIM = {"v0": 0.05, "v1": 0.14, "full": 0.08}  # full: estimated, not yet measured
GATE_AFTER = 3  # reviews, before the cost of the whole run is projected (design §4)
TARGETS = "overall >= 23/27; required findings >= 20/22; strict citations >= 0.90; " \
          "false breaches <= 3; traps and controls 7/7; 0 invented citations"


def known_clauses(kb: Path) -> set[str]:
    with duckdb.connect(str(kb), read_only=True) as con:
        rows = con.execute("SELECT DISTINCT clause_id FROM policy_chunks").fetchall()
    return {r[0] for r in rows}


def check_grader(cases: list[ComplianceCase]) -> None:
    """Stop before any paid call if the grader can't recognise right and wrong answers."""
    for case in cases:
        right = grade(case, reference_review(case))
        if not right["overall_correct"] or right["detected"] != right["required"] \
                or right["false_breaches"]:
            raise SystemExit(f"Grader check failed: the expected verdict for {case.claim_id} "
                             f"doesn't score 100%: {right}")
        empty = grade(case, {"overall": None, "findings": []})
        if empty["overall_correct"]:
            raise SystemExit(f"Grader check failed: an empty review passes {case.claim_id}.")


def _save(folder: Path, case: ComplianceCase, repeat: int, review: dict, known: set) -> dict:
    graded = grade(case, review, known)
    (folder / "reviews" / f"{case.claim_id}-r{repeat}.json").write_text(
        json.dumps({"review": review, "grade": graded}, indent=1, default=str))
    return graded


def _line(done: int, total: int, review: dict, graded: dict) -> str:
    mark = "ERROR" if review["error"] else ("RIGHT" if graded["overall_correct"] else "WRONG")
    seconds = f"{review['seconds']:.0f}s" if review["seconds"] is not None else "batch"
    return (f"[{done}/{total}] {mark:5} {review['claim_id']} {review['overall'] or '-':14} "
            f"found {graded['detected']}/{graded['required']}, "
            f"{graded['false_breaches']} false  ${review['cost_usd']:.3f} {seconds}"
            + (f"  {review['error']}" if review["error"] else ""))


def run(todo: list[tuple[int, ComplianceCase]], variant: str, max_cost: float, folder: Path,
        client, config: ReviewConfig, kb: Path) -> None:
    """Review each (repeat, claim) now, one at a time, with the cost gate."""
    library, known = _policy_library(str(kb)), known_clauses(kb)
    spent, total = 0.0, len(todo)
    for done, (repeat, case) in enumerate(todo, 1):
        if spent >= max_cost:
            print(f"Stopped: the run reached its ${max_cost:.2f} cap.")
            return
        run_id = f"c-{case.claim_id.lower()}-{variant}-r{repeat}-{int(time.time())}"
        review = review_claim(case.claim_id, library, client, config, variant, run_id,
                              purpose="eval")
        graded = _save(folder, case, repeat, review, known)
        spent += review["cost_usd"]
        if review["error"] and any(s in review["error"] for s in FATAL):
            print(f"Stopped: {review['error']}")
            return
        print(_line(done, total, review, graded), flush=True)
        if done == GATE_AFTER and total > GATE_AFTER:
            projected = spent / done * total
            print(f"Cost gate: {done} reviews cost ${spent:.2f}, so all {total} would cost "
                  f"about ${projected:.2f} (cap ${max_cost:.2f}).", flush=True)
            if projected > max_cost:
                print("Stopped at the cost gate: raise --max-cost, or run fewer claims or "
                      "repeats.")
                return


def run_batched(todo: list[tuple[int, ComplianceCase]], variant: str, max_cost: float,
                folder: Path, client, config: ReviewConfig, kb: Path) -> None:
    """Review the claims through the Batch API, one batch per repeat (plus one for v1's
    retries). A batch can't be stopped part-way, so its cost is estimated before it's sent,
    from measured live costs at half price, and checked against --max-cost and the ledger."""
    library, known = _policy_library(str(kb)), known_clauses(kb)
    spent = 0.0
    for repeat in sorted({r for r, _ in todo}):
        cases = [case for r, case in todo if r == repeat]
        estimate = len(cases) * LIVE_COST_PER_CLAIM[variant] / 2
        if spent + estimate > max_cost or costs.spent() + estimate > costs.spend_limit():
            print(f"Stopped before sending: {len(cases)} reviews would cost about "
                  f"${estimate:.2f}, past --max-cost (${max_cost:.2f}, ${spent:.2f} spent) or "
                  f"the ledger's limit (${costs.spend_limit():.2f}, "
                  f"${costs.spent():.2f} spent).")
            return
        print(f"Repeat {repeat}: {len(cases)} reviews, about ${estimate:.2f}.", flush=True)
        run_ids = {c.claim_id: f"c-{c.claim_id.lower()}-{variant}-r{repeat}-{int(time.time())}"
                   for c in cases}
        reviews = review_claims_batch([c.claim_id for c in cases], library, client, config,
                                      variant, run_ids)
        for done, (case, review) in enumerate(zip(cases, reviews, strict=True), 1):
            graded = _save(folder, case, repeat, review, known)
            spent += review["cost_usd"]
            print(_line(done, len(cases), review, graded), flush=True)


def to_do(cases: list[ComplianceCase], repeats: int, folder: Path,
          variant: str) -> list[tuple[int, ComplianceCase]]:
    """The (repeat, claim) reviews a folder doesn't have yet, or has only with an error.
    Every claim comes once before any repeats."""
    todo = []
    for repeat in range(1, repeats + 1):
        for case in cases:
            path = folder / "reviews" / f"{case.claim_id}-r{repeat}.json"
            if path.exists():
                review = json.loads(path.read_text())["review"]
                if review["variant"] != variant:
                    raise SystemExit(f"{folder} holds {review['variant']} reviews, not {variant}.")
                if not review["error"]:
                    continue
            todo.append((repeat, case))
    return todo


def write_summary(folder: Path, variant: str, split: str) -> dict:
    """The summary of every review in the folder, by repeat, read from the review files."""
    by_repeat: dict[int, list[dict]] = {}
    reviews = []
    for path in sorted(folder.glob("reviews/*.json")):
        record = json.loads(path.read_text())
        repeat = int(path.stem.rsplit("-r", 1)[1])
        by_repeat.setdefault(repeat, []).append(record["grade"])
        reviews.append(record["review"])
    complete = [by_repeat[r] for r in sorted(by_repeat)]
    per_run = [summarise(r) for r in complete]
    timed = [r["seconds"] for r in reviews if r.get("seconds") is not None]
    summary = {"variant": variant, "split": split, "runs": per_run,
               "cost_usd": round(sum(r["cost_usd"] for r in reviews), 4),
               "seconds_per_claim": round(statistics.mean(timed), 1) if timed else None,
               "cost_per_claim": round(statistics.mean(r["cost_usd"] for r in reviews), 4)
               if reviews else None,
               "batch": any(r.get("batch_ids") for r in reviews)}
    (folder / "summary.json").write_text(json.dumps(summary, indent=2))
    failures = [{"run": i + 1, "claim_id": g["claim_id"], "expected": g["expected_overall"],
                 "got": g["overall"], **miss} for i, run in enumerate(complete) for g in run
                for miss in g["misses"]]
    failures += [{"run": i + 1, "claim_id": g["claim_id"], "diagnosis": "error",
                  "error": g["error"]} for i, run in enumerate(complete) for g in run if g["error"]]
    (folder / "failures.jsonl").write_text("".join(json.dumps(f) + "\n" for f in failures))
    rows = ["| Run | Overall right | Required found | Strict citations | False breaches | "
            "Traps and controls | Invented / unsupplied citations | Errors |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for i, s in enumerate(per_run, 1):
        rows.append(f"| {i} | {s['overall_correct']}/{s['claims']} | "
                    f"{s['required_detected']}/{s['required_findings']} | "
                    f"{s['strict_citation_rate']} | {s['false_breaches']} | "
                    f"{s['traps_and_controls_right']}/{s['traps_and_controls']} | "
                    f"{s['invented_citations']} / {s['unsupplied_citations']} | {s['errors']} |")
    diagnoses: dict[str, int] = {}
    for f in failures:
        diagnoses[f["diagnosis"]] = diagnoses.get(f["diagnosis"], 0) + 1
    lines = [f"# Compliance review: {variant} on the {split} claim files", "", *rows, "",
             f"Cost ${summary['cost_usd']:.2f} in all; per claim ${summary['cost_per_claim']}"
             + (" (Batch API, half price)." if summary["batch"] else
                f" and {summary['seconds_per_claim']}s."),
             "Misses by diagnosis: " + (", ".join(f"{k} {v}" for k, v in sorted(diagnoses.items()))
                                        or "none") + ".",
             f"Targets (on all 27): {TARGETS}."]
    (folder / "summary.md").write_text("\n".join(lines) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--variant", choices=VARIANTS, default="v0")
    parser.add_argument("--split", choices=("dev", "held_out", "all"), default="dev")
    parser.add_argument("--claims", nargs="*", help="only these claim files (from the split)")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--max-cost", type=float, required=True)
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--name", default=None)
    parser.add_argument("--batch", action="store_true",
                        help="through the Batch API: half price, results within the hour")
    parser.add_argument("--resume", type=Path,
                        help="a results folder to finish: runs only its missing or errored "
                             "reviews")
    args = parser.parse_args()
    load_dotenv(".env")
    cases = load_compliance_cases(args.split)
    if args.claims:
        wanted = {c.upper() for c in args.claims}
        cases = [c for c in cases if c.claim_id in wanted]
        if missing := wanted - {c.claim_id for c in cases}:
            raise SystemExit(f"Not in the {args.split} split: {', '.join(sorted(missing))}.")
    check_grader(load_compliance_cases("all"))
    folder = args.resume or RESULTS_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}-" \
        f"{args.name or f'compliance-{args.variant}-{args.split}'}"
    (folder / "reviews").mkdir(parents=True, exist_ok=True)
    todo = to_do(cases, args.repeats, folder, args.variant)
    print(f"{len(todo)} reviews to run in {folder}.", flush=True)
    config = ReviewConfig(DEFAULT_WAREHOUSE, ModelSettings(effort=args.effort))
    runner = run_batched if args.batch else run
    runner(todo, args.variant, args.max_cost, folder, anthropic.Anthropic(max_retries=3), config,
           DEFAULT_POLICY_KB)
    write_summary(folder, args.variant, args.split)
    print((folder / "summary.md").read_text())


if __name__ == "__main__":
    main()
