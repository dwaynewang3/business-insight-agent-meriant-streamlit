"""Command line: ask the agent a question, then follow-ups in the same session.

    uv run python -m agent --role head_of_claims "What was the loss ratio for each product in 2025?"

After the first answer, type a follow-up and press Enter, or press Enter on an empty line to
stop. A session holds 10 questions. Each question costs a few cents of API usage; the total is
printed after each answer.

Proposed tickets and alerts can be approved right away or left for later. Anything still
waiting gets one last chance when the session ends; whatever isn't approved then is dropped.
"""

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from .context import ROLES
from .graph import AgentConfig, Answer, Session
from .tools import TOOLSETS


def show(answer: Answer, verbose: bool) -> None:
    print()
    for call in answer.tool_calls:
        if "error" in call:
            status = f"error: {call['error'][:120]}"
        elif "rows" in call:
            status = f"{call['rows']} rows"
        else:
            status = "ok"
        arguments = {k: v for k, v in call.get("input", {}).items() if k != "sql"}
        print(f"  · {call['tool']}{' ' + json.dumps(arguments) if arguments else ''} ({status})")
        if verbose and call.get("sql"):
            print("    " + call["sql"].replace("\n", "\n    "))
    report = answer.report
    if report is None:
        print(f"\nNo answer: {answer.error}")
    else:
        print(f"\n[{report['status']}] {report['interpretation']}\n")
        print(report["answer"])
        if report.get("answer_sql"):
            print("\nSQL behind the answer:\n  " + report["answer_sql"].replace("\n", "\n  "))
        for item in report["hypotheses"]:
            print(f"\n  [{item['verdict']}] {item['hypothesis']}: {item['evidence']}")
        for issue in report["data_quality_issues"]:
            print(f"\nData quality: {issue['issue']} ({issue['impact']})")
        for number in (answer.numbers or {}).get("unconfirmed", []):
            print(f"\nNot confirmed by its query: {number['label']}, {number['value']} "
                  f"{number['unit'] or ''}".rstrip())
        if verbose:
            print("\n" + json.dumps(report, indent=2))
    served = ", ".join(answer.models_served) or "none"
    print(f"\nUS${answer.cost_usd:.4f} · {answer.seconds:.1f}s · {len(answer.tool_calls)} queries "
          f"· {served}{' (fallback)' if answer.fell_back else ''} · run {answer.run_id}")


def list_actions(actions: list[dict]) -> None:
    for number, action in enumerate(actions, 1):
        print(f"  {number}. {action['type'].title()}: {action['title']}\n     {action['reason']}")


def choose(actions: list[dict], mode: str, prompt: str) -> list[int] | None:
    """The positions to approve, or None to decide later. Nothing is sent unless approved."""
    if mode == "all":
        return list(range(len(actions)))
    if mode == "none":
        return None
    try:
        reply = input(prompt).strip().lower()
    except EOFError:
        return None
    if not reply:
        return None
    if reply in ("n", "none"):
        return []
    return [int(part) - 1 for part in reply.replace(",", " ").split()
            if part.isdigit() and 1 <= int(part) <= len(actions)]


def show_decisions(decisions: list[dict]) -> None:
    for decision in decisions:
        status = "not sent" if decision["status"] == "dropped" else decision["status"]
        details = " ".join(part for part in (decision.get("id"), decision.get("url")
                                             or decision.get("error")) if part)
        print(f"  {decision['title']}: {status} {details}".rstrip())


def decide_now(session: Session, answer: Answer, mode: str) -> None:
    print("\nProposed actions:")
    list_actions(answer.pending_actions)
    approved = choose(answer.pending_actions, mode,
                      "Approve which? Numbers such as 1,2; n for none; Enter to decide later: ")
    if approved is None:
        print("  Waiting. You'll be asked again before the session ends.")
    else:
        show_decisions(session.decide(answer.run_id, approved))


def last_chance(session: Session, mode: str) -> None:
    """Before the session ends: approve anything still waiting, or it's dropped."""
    if not session.pending:
        return
    print("\nBefore the session ends, these actions are still waiting. Anything not approved "
          "now is dropped.")
    approved = {}
    for group in session.pending:
        print(f"\nFrom \"{group['question']}\":")
        list_actions(group["proposed_actions"])
        approved[group["run_id"]] = choose(group["proposed_actions"], mode,
                                           "Approve which? Numbers such as 1,2; Enter for none: "
                                           ) or []
    for decisions in session.end(approved).values():
        show_decisions(decisions)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("question")
    parser.add_argument("--role", choices=sorted(ROLES), default="head_of_claims")
    parser.add_argument("--verbose", "-v", action="store_true", help="show SQL and the report")
    parser.add_argument("--once", action="store_true", help="don't ask for follow-ups")
    parser.add_argument("--toolset", choices=sorted(TOOLSETS), default="full")
    parser.add_argument("--approve", choices=["ask", "none", "all"], default="ask",
                        help="what to do with proposed tickets and alerts (none: never send)")
    args = parser.parse_args()

    load_dotenv()
    config = AgentConfig(toolset=args.toolset, checkpoints=Path("logs/checkpoints.sqlite"))
    with Session(args.role, config) as session:
        question = args.question
        while question:
            answer = session.ask(question)
            show(answer, args.verbose)
            if answer.pending_actions:
                decide_now(session, answer, args.approve)
            if args.once:
                break
            if not session.questions_left:
                print(f"\nThis session has used its {config.max_questions} questions. Run the "
                      "command again to start a new one.")
                break
            try:
                question = input("\nFollow-up (Enter to stop): ").strip()
            except EOFError:
                break
        last_chance(session, args.approve)


if __name__ == "__main__":
    main()
