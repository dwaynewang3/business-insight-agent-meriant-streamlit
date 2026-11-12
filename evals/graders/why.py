"""Code checks for a "why" answer: does it name the evidence in the answer key?

These are the code half of the "why" grading in DEV_PLAN.md section 9. Each `must_mention`
group needs one of its terms somewhere in the report (an ID such as RS-041, a batch name or
a place), and cases that hinge on a data problem need a data-quality issue in the report.

Whether an explanation is right and free of unsupported causes needs judgment, so that's the
LLM grader's job (evals/graders/llm.py). Cases with nothing to find (controls and false
premises) can't be scored by these checks alone, so they're marked "unscored" here, and the
LLM grader's verdict scores them in the run summary.
"""

import json

from evals.cases.loader import WhyCase

from .what import Grade


class WhyCodeGrader:
    def grade(self, case: WhyCase, report: dict | None, error: str | None = None,
              **_context) -> Grade:
        if report is None:
            return Grade(False, "error", error or "No report.")
        if report.get("status") != "answered":
            return Grade(False, "no_answer", f"Status was {report.get('status')!r}.")
        if case.nothing_to_find:
            return Grade(False, "unscored", "Nothing to find: scored by the LLM grader.")
        text = json.dumps(report).lower()
        missing = [group for group in case.must_mention
                   if not any(term.lower() in text for term in group)]
        if missing:
            wanted = "; ".join(" or ".join(group) for group in missing)
            return Grade(False, "missing_evidence", f"The report doesn't mention {wanted}.")
        if case.flags_data_quality and not report.get("data_quality_issues"):
            return Grade(False, "missing_data_quality", "The report lists no data-quality issue.")
        return Grade(True, "pass", "Names the key evidence.")
