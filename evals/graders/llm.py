"""The LLM grader for "why" answers: is the explanation right, and free of invented causes?

Code checks can confirm that an answer names the right evidence, but not that its explanation
is right. This grader asks Claude Opus 5.5, a different model from the agent's, to compare
the answer with the answer key. It runs through the Batch API at half price, since grading
doesn't need to be fast.

Every batch also grades two check items for one case: the answer key's own explanation
(which must pass) and an empty answer (which must fail). If either check goes wrong, the
grades are marked untrusted.

    uv run python -m evals.graders.llm evals/results/<run> [<run> ...]
"""

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from agent.costs import call_cost, check_spend, record_spend
from evals.cases import load_why_cases
from evals.cases.loader import WhyCase

GRADER_MODEL = "claude-opus-5-5"
DEFAULT_MANIFEST = Path("data/dev_manifest.json")

RUBRIC = """\
You grade an analytics agent's answers to questions about why something happened in a \
fictional insurer's claims data. For each answer you get the question, the correct \
explanation from the answer key (written by the people who built the data), and the agent's \
report.

Decide two things.

1. explains_correctly. If the answer key gives a cause, does the agent's answer identify that \
cause as the main explanation? Judge the substance, not the wording or the amount of detail. \
If the answer key says there's nothing to find (a normal pattern, or a premise that's false), \
does the agent say so, rather than presenting something as the cause?

2. unsupported_causes. List each cause the agent presents as supported that is neither in the \
answer key nor backed by the evidence the agent shows. Don't count hypotheses the agent ruled \
out or marked inconclusive, side observations it clearly separates from the question, or \
effects of the true cause (for example, a storm changing the mix of claims).

The verdict is pass if explains_correctly is true and unsupported_causes is empty, and fail \
otherwise. Give the reason in one or two sentences.
"""

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "explains_correctly": {"type": "boolean"},
        "unsupported_causes": {"type": "array", "items": {"type": "string"}},
        "verdict": {"type": "string", "enum": ["pass", "fail"]},
        "reason": {"type": "string"},
    },
    "required": ["explains_correctly", "unsupported_causes", "verdict", "reason"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Item:
    """One answer to grade."""

    custom_id: str
    case: WhyCase
    expected: str
    report: dict


@dataclass(frozen=True)
class LlmGrade:
    custom_id: str
    passed: bool
    explains_correctly: bool | None
    unsupported_causes: list[str]
    reason: str
    cost_usd: float


def expected_explanation(case: WhyCase, manifest: dict) -> str:
    if case.explanation:
        return case.explanation
    entries = manifest["incidents"] + manifest.get("background_events", [])
    entry = next(e for e in entries if e["id"] == case.answer_key)
    return entry["explanation"].strip()


def _report_for_grading(report: dict) -> dict:
    """The parts of the report that carry the explanation, without the SQL."""
    return {
        "answer": report.get("answer", ""),
        "findings": [{"claim": f["claim"], "key_numbers": f["key_numbers"]}
                     for f in report.get("findings", [])],
        "hypotheses": report.get("hypotheses", []),
        "data_quality_issues": report.get("data_quality_issues", []),
    }


def request_params(item: Item) -> dict:
    kind = ("the change is real, but its cause isn't in the data"
            if item.case.kind == "unexplained"
            else "there's nothing to find" if item.case.nothing_to_find
            else "the answer key gives a cause")
    content = (
        f"Question: {item.case.question}\n\n"
        f"Answer key ({kind}): {item.expected}\n\n"
        f"Agent's report:\n{json.dumps(_report_for_grading(item.report), indent=1)}"
    )
    return {
        "model": GRADER_MODEL,
        "max_tokens": 8000,
        "system": RUBRIC,
        "messages": [{"role": "user", "content": content}],
        "output_config": {"effort": "medium",
                          "format": {"type": "json_schema", "schema": VERDICT_SCHEMA}},
    }


def check_items(case: WhyCase, expected: str) -> list[Item]:
    """The answer key itself (must pass) and an empty answer (must fail)."""
    right = {"answer": expected, "findings": [], "data_quality_issues": [],
             "hypotheses": [{"hypothesis": expected, "verdict": "supported",
                             "evidence": "As in the answer."}]}
    empty = {"answer": "I couldn't find anything.", "findings": [], "hypotheses": [],
             "data_quality_issues": []}
    return [Item("check-right", case, expected, right), Item("check-empty", case, expected, empty)]


def _to_grade(custom_id: str, message, batch: bool) -> LlmGrade:
    cost = call_cost(GRADER_MODEL, message.usage.to_dict(mode="json")) * (0.5 if batch else 1)
    record_spend({"purpose": "grader", "run_id": custom_id, "model_served": message.model,
                  "cost_usd": round(cost, 6)})
    if message.stop_reason != "end_turn":
        return LlmGrade(custom_id, False, None, [], f"Grader stopped: {message.stop_reason}", cost)
    text = next(b.text for b in message.content if b.type == "text")
    verdict = json.loads(text)
    return LlmGrade(custom_id, verdict["verdict"] == "pass", verdict["explains_correctly"],
                    verdict["unsupported_causes"], verdict["reason"], round(cost, 6))


def grade_items(client: anthropic.Anthropic, items: list[Item], batch: bool = True,
                poll_seconds: float = 20, timeout: float = 3600,
                batch_id: str | None = None) -> dict[str, LlmGrade]:
    """Grade the items. With batch_id, collect the results of a batch already submitted for
    the same items instead of submitting (and paying for) a new one."""
    if not batch:
        check_spend()
        return {item.custom_id: _to_grade(item.custom_id,
                                          client.messages.create(**request_params(item)), False)
                for item in items}
    if batch_id is None:
        check_spend()
        batch_id = client.messages.batches.create(requests=[
            {"custom_id": item.custom_id, "params": request_params(item)} for item in items]).id
        print(f"Submitted batch {batch_id} ({len(items)} requests).", flush=True)
    waited = 0.0
    while client.messages.batches.retrieve(batch_id).processing_status != "ended":
        if waited >= timeout:
            raise TimeoutError(f"Batch {batch_id} didn't finish in {timeout:g} seconds. "
                               f"Collect it later with --batch-id {batch_id}.")
        time.sleep(poll_seconds)
        waited += poll_seconds
    grades = {}
    for result in client.messages.batches.results(batch_id):
        if result.result.type == "succeeded":
            grades[result.custom_id] = _to_grade(result.custom_id, result.result.message, True)
        else:
            grades[result.custom_id] = LlmGrade(result.custom_id, False, None, [],
                                                f"Batch request {result.result.type}.", 0.0)
    return grades


def grade_folders(client: anthropic.Anthropic, folders: list[Path], manifest_path: Path,
                  batch: bool = True, poll_seconds: float = 20,
                  batch_id: str | None = None, timeout: float = 3600,
                  why_cases: Path | None = None) -> dict:
    """Grade the "why" answers in the folders, against the cases in why_cases (the dev cases
    by default; the test data's for the final scoring) and the manifest's answer key."""
    manifest = json.loads(manifest_path.read_text())
    cases = {case.id: case for case in (load_why_cases(why_cases) if why_cases
                                        else load_why_cases())}
    items, sources = [], {}
    for folder in folders:
        for path in sorted((folder / "cases").glob("why-*.json")):
            record = json.loads(path.read_text())
            if record["report"] is None:
                continue
            case = cases[record["case_id"]]
            # Batch ids allow only letters, digits, _ and -, so answers are numbered. Grades
            # are saved by file name: the case id, plus .r2, .r3 ... for repeat runs.
            custom_id = f"answer-{len(items) + 1}"
            sources[custom_id] = (folder, path.stem)
            items.append(Item(custom_id, case, expected_explanation(case, manifest),
                              record["report"]))
    if not items:
        raise SystemExit("No graded \"why\" answers in those folders.")
    first = next(i.case for i in items if not i.case.nothing_to_find)
    checks = check_items(first, expected_explanation(first, manifest))
    grades = grade_items(client, checks + items, batch, poll_seconds, timeout, batch_id)
    trusted = grades["check-right"].passed and not grades["check-empty"].passed
    for folder in folders:
        mine = {sources[k][1]: asdict(g) for k, g in grades.items()
                if k in sources and sources[k][0] == folder}
        (folder / "llm_grades.json").write_text(json.dumps(
            {"grader": GRADER_MODEL, "trusted": trusted, "grades": mine}, indent=2))
    named = {(f"{sources[k][0].name}/{sources[k][1]}" if k in sources else k): g
             for k, g in grades.items()}
    return {"trusted": trusted, "grades": named}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folders", nargs="+", type=Path)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--no-batch", action="store_true", help="grade now, at full price")
    parser.add_argument("--batch-id", help="collect a batch already submitted for these folders")
    parser.add_argument("--why-cases", type=Path,
                        help="the cases file (default: the dev cases; evals/cases/test/why.yaml "
                             "for the test data)")
    args = parser.parse_args()
    load_dotenv()
    outcome = grade_folders(anthropic.Anthropic(max_retries=3), args.folders, args.manifest,
                            batch=not args.no_batch, batch_id=args.batch_id,
                            why_cases=args.why_cases)
    print(f"Grader checks {'passed' if outcome['trusted'] else 'FAILED: grades untrusted'}.")
    total = 0.0
    for custom_id, grade in outcome["grades"].items():
        total += grade.cost_usd
        mark = "PASS" if grade.passed else "FAIL"
        print(f"{mark}  {custom_id}\n      {grade.reason}"
              + (f"\n      Unsupported: {'; '.join(grade.unsupported_causes)}"
                 if grade.unsupported_causes else ""))
    print(f"Grading cost: ${total:.4f}")
    from evals.run_evals import resummarize  # the runner imports this module

    for folder in args.folders:
        if (folder / "summary.json").exists():
            resummarize(folder)
            print(f"Updated {folder / 'summary.md'} with these grades.")


if __name__ == "__main__":
    main()
