"""Record the demo script's policy questions (docs/demo_script.md, step 5) for replay mode.

    uv run python -m evals.demo_runs --max-cost 0.50

The other demo questions are eval cases already, recorded by `run_evals`. These three have no
eval kind of their own (the compliance and routing evals don't save answers), so this asks each
in a fresh session and saves it in the same record format, under evals/results/<time>-demo-policy/,
where replay mode finds it. A light code check is recorded with each: the expected tool was
called, the answer names what it must, and every citation was returned by a tool.
"""

import argparse
import json
import time
from dataclasses import dataclass

from dotenv import load_dotenv

from agent.citations import check_citations
from agent.graph import AgentConfig, Session
from evals.graders import Grade
from evals.run_evals import RESULTS_DIR, case_record


@dataclass(frozen=True)
class DemoCase:
    id: str
    question: str
    role: str
    tool: str  # a tool the answer must call
    must_mention: tuple[str, ...]


CASES = (
    DemoCase("demo-expired-licence-february",
             "For an incident on 10 February 2026, could we cover a driver whose licence had "
             "expired 18 days earlier?", "head_of_claims", "search_policies", ("5.3",)),
    DemoCase("demo-review-gc-010", "Was claim GC-010 handled in line with policy?",
             "head_of_claims", "check_claim_compliance", ("GC-010",)),
    DemoCase("demo-settled-above-authority",
             "Which claim files were settled above the approving officer's authority limit?",
             "head_of_claims", "search_policies", ("GC-004", "GC-005")),
)


def grade(case: DemoCase, report: dict | None, error: str | None,
          tool_calls: list[dict]) -> Grade:
    if report is None:
        return Grade(False, "error", error or "no answer")
    citations = check_citations(report, tool_calls)
    problems = []
    if case.tool not in {call["tool"] for call in tool_calls}:
        problems.append(f"didn't call {case.tool}")
    if missing := [m for m in case.must_mention if m not in report["answer"]]:
        problems.append(f"doesn't mention {', '.join(missing)}")
    if citations["unconfirmed"]:
        problems.append(f"{len(citations['unconfirmed'])} citation(s) no tool returned")
    return Grade(not problems, "wrong_result" if problems else "pass",
                 "; ".join(problems) or "ok")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--max-cost", type=float, required=True)
    args = parser.parse_args()
    load_dotenv()
    config = AgentConfig()
    folder = RESULTS_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}-demo-policy"
    (folder / "cases").mkdir(parents=True)
    spent = 0.0
    for case in CASES:
        if spent >= args.max_cost:
            print(f"Stopping: ${spent:.4f} spent, past the ${args.max_cost:.2f} cap.")
            break
        with Session(case.role, config=config, purpose="demo",
                     trace_dir=folder / "traces") as session:
            answer = session.ask(case.question)
            record = case_record(case, answer,
                                 grade(case, answer.report, answer.error, answer.tool_calls),
                                 session, warehouse=config.warehouse)
        spent += answer.cost_usd
        (folder / "cases" / f"{case.id}.json").write_text(
            json.dumps(record, indent=2, default=str))
        print(f"{'PASS' if record['grade']['passed'] else 'CHECK':6} ${answer.cost_usd:.4f} "
              f"{answer.seconds:5.1f}s  {case.id}  {record['grade']['reason']}", flush=True)
    print(f"\n${spent:.4f} · {folder}")


if __name__ == "__main__":
    main()
