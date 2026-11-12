"""Command line: uv run python -m evals.cases, to read through every eval question."""

from .loader import load_followup_cases, load_safety_cases, load_what_cases, load_why_cases


def main() -> None:
    sections = [
        ("What", load_what_cases()),
        ("Why", load_why_cases()),
        ("Safety", load_safety_cases()),
        ("Follow-up", load_followup_cases()),
    ]
    for title, cases in sections:
        print(f"\n{title} cases: {len(cases)}")
        for case in cases:
            print(f"  {case.id}  ({case.role})")
            if hasattr(case, "first"):
                print(f"      {case.first}\n      then: {case.question}")
            else:
                print(f"      {case.question}")


if __name__ == "__main__":
    main()
