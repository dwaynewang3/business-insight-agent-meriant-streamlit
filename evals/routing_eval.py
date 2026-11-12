"""Routing eval: does the agent pick the right tools for data, policy and compliance questions?
(RAG_PLAN §9.4, design §3.9)

    uv run python -m evals.routing_eval --max-cost 1.50
    uv run python -m evals.routing_eval --repeats 3 --max-cost 4.00

Each of the 16 questions is asked in a fresh session. A question passes if every required tool
was called, at least one of its any-of tools was called (where listed), and no forbidden tool
was called. Target: at least 14 of 16.

One change from the kit: its agent had a single data tool, `run_sql`. This one also has
`query_metric`, which answers with an agreed metric definition, so either counts as the data
route, both where it's required and where it's forbidden. Results go to
evals/results/<time>-<name>/.
"""

import argparse
import json
import time
from pathlib import Path

from dotenv import load_dotenv

from agent.graph import Session

QUESTIONS = Path(__file__).parent / "cases" / "compliance" / "routing_questions.jsonl"
RESULTS_DIR = Path(__file__).parent / "results"
ROLE = "head_of_claims"
TARGET = 14
DATA_ROUTE = {"run_sql", "query_metric"}


def load_questions(path: Path = QUESTIONS) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _called(tool: str, used: set[str]) -> bool:
    return bool(used & DATA_ROUTE) if tool == "run_sql" else tool in used


def grade(question: dict, used: list[str]) -> dict:
    """Pass or fail, and why, from the tools the agent called."""
    called = set(used)
    missing = [t for t in question["required_tools"] if not _called(t, called)]
    forbidden = [t for t in question["forbidden_tools"] if _called(t, called)]
    any_of = question["any_of_tools"]
    any_missing = bool(any_of) and not any(_called(t, called) for t in any_of)
    reasons = ([f"didn't call {', '.join(missing)}"] if missing else []) + \
              ([f"called forbidden {', '.join(forbidden)}"] if forbidden else []) + \
              ([f"called none of {', '.join(any_of)}"] if any_missing else [])
    return {"passed": not reasons, "reason": "; ".join(reasons)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--max-cost", type=float, required=True)
    parser.add_argument("--qids", nargs="*")
    parser.add_argument("--name", default="routing")
    args = parser.parse_args()
    load_dotenv(".env")
    questions = [q for q in load_questions() if not args.qids or q["qid"] in args.qids]
    for q in questions:  # the grader recognises the kit's own right answer, and an empty one
        right = q["required_tools"] + q["any_of_tools"][:1]
        assert grade(q, right)["passed"], q["qid"]
        assert q["qid"] == "T-15" or not grade(q, [])["passed"], q["qid"]
    folder = RESULTS_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}-{args.name}"
    folder.mkdir(parents=True)
    spent, rows = 0.0, []
    for repeat in range(1, args.repeats + 1):
        for q in questions:
            if spent >= args.max_cost:
                print(f"Stopped: the run reached its ${args.max_cost:.2f} cap.")
                break
            with Session(ROLE, purpose="eval") as chat:
                answer = chat.ask(q["question"])
            used = [c["tool"] for c in answer.tool_calls]
            result = {"qid": q["qid"], "repeat": repeat, "question": q["question"], "tools": used,
                      **grade(q, used), "error": answer.error, "cost_usd": answer.cost_usd,
                      "seconds": answer.seconds, "run_id": answer.run_id,
                      "answer": (answer.report or {}).get("answer")}
            spent += answer.cost_usd
            rows.append(result)
            print(f"[r{repeat}] {'PASS' if result['passed'] else 'FAIL'} {q['qid']} "
                  f"${answer.cost_usd:.3f} {used} {result['reason']}", flush=True)
    (folder / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    lines = [f"# Routing eval ({len(questions)} questions, {args.repeats} run(s))", ""]
    for repeat in range(1, args.repeats + 1):
        run = [r for r in rows if r["repeat"] == repeat]
        lines.append(f"- Run {repeat}: **{sum(r['passed'] for r in run)}/{len(run)}** "
                     f"(target {TARGET}/16)")
    lines += ["", f"Cost ${spent:.2f}.", "", "| Question | Run | Result | Tools | Reason |",
              "| --- | --- | --- | --- | --- |"]
    lines += [f"| {r['qid']} | {r['repeat']} | {'pass' if r['passed'] else 'fail'} | "
              f"{', '.join(r['tools']) or '(none)'} | {r['reason']} |" for r in rows]
    (folder / "summary.md").write_text("\n".join(lines) + "\n")
    print((folder / "summary.md").read_text())


if __name__ == "__main__":
    main()
