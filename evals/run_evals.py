"""Run the agent on eval cases, grade the answers, and record cost, latency and transcripts.

    uv run python -m evals.run_evals --subset smoke
    uv run python -m evals.run_evals --cases what-loss-ratio-by-product-2025 --max-cost 0.20

Each case gets a fresh session with the case's role. Results go to
evals/results/<time>-<name>/: one JSON file per case with the report, the grade, every model
call and query, and the full conversation; plus summary.json and summary.md.

"Why" runs then send their answers to the LLM grader (evals/graders/llm.py), and its verdicts
go into the summary. To rebuild a folder's summary without running anything, for example
after collecting a slow grading batch:

    uv run python -m evals.run_evals --summarize evals/results/<run>

The rules from DEV_PLAN.md section 9:
- The grader is checked before any paid call: each case's reference answers must pass and an
  empty answer must fail, or the run stops.
- API errors, budget stops and cut-off answers are counted apart from wrong answers.
- The model that served each call is recorded, and runs where a fallback model answered are
  flagged.
- The run stops once its cost passes --max-cost. The spend ledger's limit applies too.
- Results are counts with a 95% range, not bare percentages.
- With --repeats N, every case runs N times, each in a fresh session, to measure consistency
  (Sonnet 5.5 and Opus 5.5 reject a non-default temperature, so repeats are the only way).
  The headline is then the cases that passed in every run, since runs of one case aren't
  independent; the summary also gives each run's count and the cases with mixed results.
- Each finding's key numbers are checked against its own SQL and reported as their own count
  (the plan's trust criterion), apart from pass or fail.
"""

import argparse
import json
import math
import statistics
import time
from collections import Counter
from collections.abc import Collection
from dataclasses import asdict
from pathlib import Path

import anthropic
import yaml
from dotenv import load_dotenv

from agent.citations import check_citations
from agent.graph import AgentConfig, Answer, Session
from agent.llm import ModelSettings
from agent.tools import TOOLSETS
from data.generator.build import manifest_path
from evals.cases import (
    load_followup_cases,
    load_safety_cases,
    load_what_cases,
    load_why_cases,
)
from evals.cases.loader import FollowUpCase, SafetyCase, WhatCase, WhyCase
from evals.graders import (
    CATEGORIES,
    FollowUpGrader,
    Grade,
    NumberChecker,
    SafetyGrader,
    WhatGrader,
    WhyCodeGrader,
)
from evals.graders.llm import grade_folders

LOADERS = {"what": load_what_cases, "why": load_why_cases, "safety": load_safety_cases,
           "followup": load_followup_cases}
# The dev data, for development; the test data, scored once at the end (DEV_PLAN Phase 6),
# with its own warehouse and its own "what" and "why" cases.
CASES_ROOT = Path(__file__).parent / "cases"
SUITES = {"dev": (CASES_ROOT, Path("data/dev.duckdb")),
          "test": (CASES_ROOT / "test", Path("data/test.duckdb"))}

RESULTS_DIR = Path(__file__).parent / "results"
SUBSETS = Path(__file__).parent / "subsets.yaml"


def wilson_range(passed: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """95% range for a pass rate (Wilson score interval)."""
    if total == 0:
        return (0.0, 0.0)
    p = passed / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return (max(0.0, centre - spread), min(1.0, centre + spread))


def select_cases(subset: str | None, ids: list[str] | None, kind: str = "what",
                 suite: str = "dev") -> list:
    path = SUITES[suite][0] / f"{kind}.yaml"
    if not path.exists():
        raise SystemExit(f"The {suite} suite has no {kind} cases ({path}).")
    cases = {case.id: case for case in LOADERS[kind](path)}
    if ids:
        wanted = ids
    elif subset:
        wanted = yaml.safe_load(SUBSETS.read_text())[subset]
    else:
        wanted = list(cases)
    if unknown := [case_id for case_id in wanted if case_id not in cases]:
        raise SystemExit(f"Unknown case ids: {', '.join(unknown)}")
    return [cases[case_id] for case_id in wanted]


def check_grader(grader: WhatGrader, cases: list[WhatCase]) -> None:
    """Stop before spending anything if the grader would score these cases wrongly."""
    for case in cases:
        for sql in case.reference_sql:
            grade = grader.grade(case, {"status": "answered", "answer_sql": sql})
            if not grade.passed:
                raise SystemExit(f"Grader check failed: {case.id}'s reference fails: "
                                 f"{grade.reason}")
        if grader.grade(case, {"status": "answered", "answer_sql": None}).passed:
            raise SystemExit(f"Grader check failed: an empty answer passes {case.id}.")


def record_key(case_id: str, repeat: int = 1) -> str:
    """A saved run's name, and its file's: the case id, plus .r2, .r3 ... for repeat runs."""
    return case_id if repeat == 1 else f"{case_id}.r{repeat}"


def key_of(record: dict) -> str:
    return record_key(record["case_id"], record.get("repeat", 1))


def case_record(case: WhatCase | WhyCase | SafetyCase | FollowUpCase, answer: Answer,
                grade: Grade, session: Session, first: Answer | None = None,
                numbers: dict | None = None, repeat: int = 1,
                warehouse: Path = AgentConfig.warehouse) -> dict:
    record = {
        "case_id": case.id,
        "repeat": repeat,
        "warehouse": str(warehouse),  # replay re-runs the SQL here
        "question": case.question,
        "role": case.role,
        "grade": asdict(grade),
        "report": answer.report,
        "error": answer.error,
        "cost_usd": answer.cost_usd,
        "seconds": answer.seconds,
        "tool_calls": answer.tool_calls,
        "model_calls": answer.model_calls,
        "models_served": answer.models_served,
        "fell_back": answer.fell_back,
        "proposed_actions": answer.pending_actions,  # never approved in eval runs
        "session_id": answer.session_id,
        "run_id": answer.run_id,
        "numbers": numbers,
        "citations": check_citations(answer.report, answer.tool_calls),
        "agent_version": session.version,
        "transcript": session.messages,
    }
    if first is not None:  # a follow-up case: the first answer isn't graded, but it's paid for
        record["first"] = {"question": first.question, "report": first.report,
                           "error": first.error, "cost_usd": first.cost_usd}
        record["cost_usd"] = round(first.cost_usd + answer.cost_usd, 6)
        record["seconds"] = round(first.seconds + answer.seconds, 2)
    return record


def load_llm_grades(folder: Path) -> dict | None:
    """The LLM grader's file for a results folder, if it has been graded."""
    path = folder / "llm_grades.json"
    return json.loads(path.read_text()) if path.exists() else None


def final_grade(record: dict, llm: dict | None) -> dict:
    """The case's grade with the LLM grader's verdict folded in.

    The code checks come first: an answer that misses the key evidence fails whatever the LLM
    grader says. A code pass, or a case the code can't judge (nothing to find), takes the LLM
    grader's verdict, but only when the grader's own checks passed in that batch.
    """
    grade = record["grade"]
    if not llm or not llm.get("trusted") or grade["category"] not in ("pass", "unscored"):
        return grade
    verdict = llm["grades"].get(key_of(record))
    if verdict is None:
        return grade
    if verdict["passed"]:
        return {"passed": True, "category": "pass", "reason": verdict["reason"]}
    return {"passed": False, "category": "wrong_explanation", "reason": verdict["reason"]}


def summarize(name: str, records: list[dict], skipped: list[str], settings: ModelSettings,
              version: str | None, toolset: str = "full", llm: dict | None = None) -> dict:
    grades = {key_of(r): final_grade(r, llm) for r in records}
    graded = [r for r in records if grades[key_of(r)]["category"] != "error"]
    # Cases nobody could judge yet (nothing to find, before the LLM grader) don't count as
    # passes or failures.
    scored = [r for r in records if grades[key_of(r)]["category"] != "unscored"]
    runs_passed = sum(grades[key_of(r)]["passed"] for r in scored)
    repeats = max((r.get("repeat", 1) for r in records), default=1)
    consistency = None
    if repeats == 1:
        passed, total = runs_passed, len(scored)
    else:
        # Runs of one case aren't independent, so the headline counts cases: a case passes
        # only if it passed in every run that could be scored.
        by_case: dict[str, list[bool]] = {}
        for r in scored:
            by_case.setdefault(r["case_id"], []).append(grades[key_of(r)]["passed"])
        passed = sum(all(results) for results in by_case.values())
        total = len(by_case)
        consistency = {
            "runs_passed": runs_passed,
            "runs_scored": len(scored),
            "per_repeat": [[sum(grades[key_of(r)]["passed"] for r in scored
                                if r.get("repeat", 1) == n),
                            sum(1 for r in scored if r.get("repeat", 1) == n)]
                           for n in range(1, repeats + 1)],
            "mixed_cases": sorted(case for case, results in by_case.items()
                                  if len(set(results)) > 1),
        }
    low, high = wilson_range(passed, total)
    numbers = [r["numbers"] for r in records if r.get("numbers")]
    seconds = sorted(r["seconds"] for r in records)
    calls = [c for r in records for c in r["model_calls"]]
    input_side = sum(c["input_tokens"] + c["cache_read_input_tokens"]
                     + c["cache_creation_input_tokens"] for c in calls)
    return {
        "name": name,
        "model": settings.model,
        "effort": settings.effort,
        "toolset": toolset,
        "agent_version": version,
        "cases": len({r["case_id"] for r in records}),
        "runs": len(records),
        "repeats": repeats,
        "skipped_for_cost": skipped,
        "scored": total,
        "unscored": len(records) - len(scored),
        "passed": passed,
        "pass_range_95": [round(low, 3), round(high, 3)],
        "consistency": consistency,
        "categories": {c: n for c in CATEGORIES
                       if (n := Counter(g["category"] for g in grades.values())[c])},
        "grades": grades,
        "llm_grader": None if llm is None else {
            "model": llm.get("grader"), "trusted": llm.get("trusted"),
            "graded": len(llm.get("grades", {})),
            "cost_usd": round(sum(g.get("cost_usd", 0) for g in llm.get("grades", {}).values()),
                              4)},
        "key_numbers_checked": sum(n["checked"] for n in numbers),
        "key_numbers_confirmed": sum(n["confirmed"] for n in numbers),
        "citations_made": sum((r.get("citations") or {}).get("cited", 0) for r in records),
        "citations_confirmed": sum((r.get("citations") or {}).get("confirmed", 0)
                                   for r in records),
        "graded_without_errors": len(graded),
        "cost_usd": round(sum(r["cost_usd"] for r in records), 4),
        "cost_per_case_usd": round(sum(r["cost_usd"] for r in records) / len(records), 4)
        if records else 0,
        "median_seconds": statistics.median(seconds) if seconds else None,
        "p95_seconds": seconds[min(len(seconds) - 1, math.ceil(0.95 * len(seconds)) - 1)]
        if seconds else None,
        "mean_tool_calls": round(statistics.mean(len(r["tool_calls"]) for r in records), 2)
        if records else None,
        "cache_read_share": round(sum(c["cache_read_input_tokens"] for c in calls)
                                  / input_side, 3) if input_side else None,
        "fallback_cases": [key_of(r) for r in records if r["fell_back"]],
        "models_served": sorted({m for r in records for m in r["models_served"]}),
    }


def write_markdown(path: Path, summary: dict, records: list[dict]) -> None:
    low, high = summary["pass_range_95"]
    lines = [
        f"# Eval run: {summary['name']}",
        "",
        f"- Model: {summary['model']} at {summary['effort']} effort, tools: "
        f"{summary['toolset']} (agent {summary['agent_version']})",
        f"- Passed: **{summary['passed']}/{summary['scored']}** "
        f"(95% range {low:.0%}–{high:.0%})"
        if not summary.get("consistency") else
        f"- Passed in every run: **{summary['passed']}/{summary['scored']} cases** "
        f"(95% range {low:.0%}–{high:.0%}), {summary['repeats']} runs each",
    ]
    if consistency := summary.get("consistency"):
        lines += [
            f"- Runs passed: {consistency['runs_passed']}/{consistency['runs_scored']}; "
            f"per run: {', '.join(f'{p}/{n}' for p, n in consistency['per_repeat'])}",
            f"- Mixed results across runs: {', '.join(consistency['mixed_cases']) or 'none'}",
        ]
    if summary["unscored"]:
        lines.append(f"- {summary['unscored']} answers unscored until the LLM grader")
    lines += [
        f"- Categories: {', '.join(f'{k} {v}' for k, v in summary['categories'].items())}",
    ]
    if llm := summary.get("llm_grader"):
        lines.append(f"- LLM grader: {llm['model']}, {llm['graded']} answers, "
                     f"${llm['cost_usd']:.4f}" + ("" if llm["trusted"] else
                     "; its checks FAILED, so its verdicts aren't used"))
    if checked := summary.get("key_numbers_checked"):
        lines.append(f"- Key numbers confirmed by their finding's SQL: "
                     f"{summary['key_numbers_confirmed']}/{checked} "
                     f"({summary['key_numbers_confirmed'] / checked:.0%})")
    if cited := summary.get("citations_made"):
        lines.append(f"- Policy citations returned by a policy tool: "
                     f"{summary['citations_confirmed']}/{cited}")
    lines += [
        f"- Cost: ${summary['cost_usd']:.4f} (${summary['cost_per_case_usd']:.4f} per question)",
        f"- Latency: median {summary['median_seconds']}s, 95th percentile "
        f"{summary['p95_seconds']}s",
        f"- Queries per case: {summary['mean_tool_calls']}; cache read share of input: "
        f"{summary['cache_read_share']}",
        f"- Fallback answers: {', '.join(summary['fallback_cases']) or 'none'}",
    ]
    if summary["skipped_for_cost"]:
        lines.append(f"- Skipped (cost cap): {', '.join(summary['skipped_for_cost'])}")
    lines += ["", "| Case | Result | Cost | Seconds | Queries | Numbers | Reason |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in records:
        grade = summary["grades"].get(key_of(r), r["grade"])
        reason = "" if grade["passed"] else grade["reason"].replace("|", "/")[:160]
        numbers = r.get("numbers") or {}
        count = f"{numbers['confirmed']}/{numbers['checked']}" if numbers.get("checked") else ""
        lines.append(f"| {key_of(r)} | {grade['category']} | ${r['cost_usd']:.4f} | "
                     f"{r['seconds']} | {len(r['tool_calls'])} | {count} | {reason} |")
    path.write_text("\n".join(lines) + "\n")


def saved_records(folder: Path) -> dict[str, dict]:
    """Runs already saved in a results folder, by record key (case id, plus .r2 ...)."""
    files = sorted((folder / "cases").glob("*.json")) if folder.exists() else []
    return {key_of(record): record for record in map(json.loads, map(Path.read_text, files))}


def run_cases(cases: list, config: AgentConfig, grader, folder: Path,
              max_cost: float, client=None, checker: NumberChecker | None = None,
              repeats: int = 1, done: Collection[str] = ()
              ) -> tuple[list[dict], list[str], str | None]:
    """Run and grade each case in a fresh session, writing one file per run. With repeats,
    every case runs once before any case runs again, so a run stopped by the cost cap still
    covers every case it reached. Runs named in `done` (already saved) are skipped."""
    checker = checker or NumberChecker(config.warehouse)
    (folder / "cases").mkdir(parents=True, exist_ok=True)
    planned = [(case, repeat) for repeat in range(1, repeats + 1) for case in cases
               if record_key(case.id, repeat) not in done]
    records, skipped, version = [], [], None
    for number, (case, repeat) in enumerate(planned, 1):
        spent = sum(r["cost_usd"] for r in records)
        if spent >= max_cost:
            skipped = [record_key(c.id, n) for c, n in planned[number - 1:]]
            print(f"Stopping: ${spent:.4f} spent, past the ${max_cost:.2f} cap.")
            break
        with Session(case.role, config=config, client=client, purpose="eval",
                     trace_dir=folder / "traces") as session:
            version = session.version
            first = session.ask(case.first) if isinstance(case, FollowUpCase) else None
            answer = session.ask(case.question)
            grade = grader.grade(case, answer.report, answer.error,
                                 transcript=session.messages, tool_calls=answer.tool_calls)
            record = case_record(case, answer, grade, session, first,
                                 checker.check(answer.report), repeat, config.warehouse)
        records.append(record)
        key = record_key(case.id, repeat)
        (folder / "cases" / f"{key}.json").write_text(json.dumps(record, indent=2, default=str))
        mark = "PASS" if grade.passed else grade.category.upper()
        print(f"[{number}/{len(planned)}] {mark:12} ${record['cost_usd']:.4f} "
              f"{record['seconds']:5.1f}s "
              f"{len(answer.tool_calls):2} queries  {key}"
              + ("" if grade.passed else f"\n      {grade.reason[:200]}"), flush=True)
    return records, skipped, version


def write_summary(folder: Path, records: list[dict], skipped: list[str], settings: ModelSettings,
                  version: str | None, toolset: str) -> dict:
    summary = summarize(folder.name, records, skipped, settings, version, toolset,
                        load_llm_grades(folder))
    (folder / "summary.json").write_text(json.dumps(summary, indent=2))
    write_markdown(folder / "summary.md", summary, records)
    return summary


def resummarize(folder: Path, warehouse: Path = AgentConfig.warehouse) -> dict:
    """Rebuild a results folder's summary from its saved cases, with no API calls. Older
    runs get their key numbers checked here; LLM grades are read from llm_grades.json."""
    old = json.loads((folder / "summary.json").read_text()) \
        if (folder / "summary.json").exists() else {}
    records = list(saved_records(folder).values())
    checker = NumberChecker(warehouse)
    for record in records:
        if "numbers" not in record:
            record["numbers"] = checker.check(record["report"])
    settings = ModelSettings(model=old.get("model", ModelSettings.model),
                             effort=old.get("effort", ModelSettings.effort))
    version = old.get("agent_version") or next((r["agent_version"] for r in records), None)
    return write_summary(folder, records, old.get("skipped_for_cost", []), settings, version,
                         old.get("toolset", "full"))


def llm_grade(folder: Path, manifest: Path, timeout: float,
              why_cases: Path | None = None) -> None:
    """Send a "why" run's answers to the LLM grader, waiting up to `timeout` seconds."""
    print("Sending the answers to the LLM grader (Batch API)…", flush=True)
    try:
        outcome = grade_folders(anthropic.Anthropic(max_retries=3), [folder], manifest,
                                timeout=timeout, why_cases=why_cases)
    except TimeoutError as slow:
        print(f"{slow}\nThe summary counts these cases as unscored until then; collecting the "
              f"batch with evals.graders.llm updates it.")
        return
    print(f"LLM grader checks {'passed' if outcome['trusted'] else 'FAILED'}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run and grade eval cases.")
    parser.add_argument("--kind", choices=sorted(LOADERS), default="what")
    parser.add_argument("--subset", help="a name from evals/subsets.yaml")
    parser.add_argument("--cases", help="comma-separated case ids (overrides --subset)")
    parser.add_argument("--max-cost", type=float, default=1.00, help="stop the run past this (USD)")
    parser.add_argument("--model", default=ModelSettings.model)
    parser.add_argument("--effort", default=ModelSettings.effort)
    parser.add_argument("--suite", choices=sorted(SUITES), default="dev",
                        help="dev data, or the test data (scored once, at the end)")
    parser.add_argument("--warehouse", type=Path,
                        help="the warehouse to use (default: the suite's)")
    parser.add_argument("--toolset", choices=sorted(TOOLSETS), default="full")
    parser.add_argument("--name", help="a label for the results folder")
    parser.add_argument("--repeats", type=int, default=1,
                        help="run every case this many times, to measure consistency")
    parser.add_argument("--resume", type=Path,
                        help="a results folder to finish: runs only the cases it doesn't have")
    parser.add_argument("--summarize", type=Path,
                        help="rebuild a results folder's summary without running anything")
    parser.add_argument("--no-llm-grade", action="store_true",
                        help="don't send \"why\" answers to the LLM grader")
    parser.add_argument("--llm-timeout", type=float, default=1200,
                        help="seconds to wait for the LLM grader's batch")
    args = parser.parse_args()
    args.warehouse = args.warehouse or SUITES[args.suite][1]

    if args.summarize:
        summary = resummarize(args.summarize, args.warehouse)
        print(f"Rebuilt {args.summarize / 'summary.md'}: passed {summary['passed']}/"
              f"{summary['scored']}.")
        return

    load_dotenv()
    cases = select_cases(args.subset, args.cases.split(",") if args.cases else None, args.kind,
                         args.suite)
    if args.kind == "what":
        grader = WhatGrader(args.warehouse)
        check_grader(grader, cases)
        print(f"Grader check passed for {len(cases)} cases.")
    elif args.kind == "followup":
        grader = FollowUpGrader(WhatGrader(args.warehouse))
        check_grader(grader.what, [case.grade_as for case in cases])
        print(f"Grader check passed for {len(cases)} follow-ups.")
    elif args.kind == "why":
        grader = WhyCodeGrader()
    else:
        grader = SafetyGrader(args.warehouse, manifest_path(args.warehouse))

    name = args.name or args.subset or "custom"
    folder = args.resume or RESULTS_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}-{name}"
    saved = saved_records(folder)
    keys = [record_key(case.id, n) for n in range(1, args.repeats + 1) for case in cases]
    if saved:
        print(f"Resuming {folder.name}: {len(saved)} runs saved, "
              f"{sum(key not in saved for key in keys)} to run.")
    settings = ModelSettings(model=args.model, effort=args.effort)
    config = AgentConfig(warehouse=args.warehouse, settings=settings, toolset=args.toolset)
    checker = NumberChecker(args.warehouse)
    new, skipped, version = run_cases(cases, config, grader, folder,
                                      args.max_cost - sum(r["cost_usd"] for r in saved.values()),
                                      checker=checker, repeats=args.repeats, done=set(saved))
    by_key = saved | {key_of(record): record for record in new}
    records = [by_key[key] for key in keys if key in by_key]
    for record in records:  # cases saved before the number check existed
        record.setdefault("numbers", checker.check(record["report"]))
    version = version or next((r["agent_version"] for r in records), None)

    if args.kind == "why" and not args.no_llm_grade and any(r["report"] for r in records):
        llm_grade(folder, manifest_path(args.warehouse), args.llm_timeout,
                  SUITES[args.suite][0] / "why.yaml")
    summary = write_summary(folder, records, skipped, settings, version, args.toolset)
    low, high = summary["pass_range_95"]
    every = " cases in every run" if summary["consistency"] else ""
    print(f"\nPassed {summary['passed']}/{summary['scored']}{every} (95% range "
          f"{low:.0%}–{high:.0%}) · ${summary['cost_usd']:.4f} · "
          f"median {summary['median_seconds']}s · {folder}")


if __name__ == "__main__":
    main()
