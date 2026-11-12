"""The report every answer ends with (DEV_PLAN.md section 6).

It's a structured output, so the UI and the eval graders read the same fields. Structured
outputs need `additionalProperties: false` and fixed keys on every object, which is why
`key_numbers` is a list of label, value and unit rather than a free-form object.
"""

import json

STATUSES = ("answered", "needs_clarification", "declined")
QUESTION_TYPES = ("what", "why", "other")  # "why" questions also list the hypotheses tested


def _object(properties: dict) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _list(item: dict) -> dict:
    return {"type": "array", "items": item}


STRING = {"type": "string"}

REPORT_SCHEMA = _object({
    "status": {"type": "string", "enum": list(STATUSES)},
    "question_type": {"type": "string", "enum": list(QUESTION_TYPES)},
    "interpretation": STRING,
    "answer": STRING,
    "answer_sql": {"type": ["string", "null"]},
    "findings": _list(_object({
        "claim": STRING,
        "evidence_sql": STRING,
        "key_numbers": _list(_object({
            "label": STRING,
            "value": {"type": "number"},
            "unit": STRING,
        })),
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    })),
    "hypotheses": _list(_object({
        "hypothesis": STRING,
        "verdict": {"type": "string", "enum": ["supported", "ruled_out", "inconclusive"]},
        "evidence": STRING,
    })),
    "data_quality_issues": _list(_object({"issue": STRING, "impact": STRING})),
    "charts": _list(_object({
        "title": STRING,
        "sql": STRING,
        "type": {"type": "string", "enum": ["line", "bar"]},
        "x": STRING,
        "y": STRING,
    })),
    "proposed_actions": _list(_object({
        "type": {"type": "string", "enum": ["ticket", "alert"]},
        "title": STRING,
        "reason": STRING,
    })),
    "open_questions": _list(STRING),
})

OUTPUT_FORMAT = {"type": "json_schema", "schema": REPORT_SCHEMA}


class ReportError(ValueError):
    """The model's final message isn't a valid report."""


def parse_report(text: str) -> dict:
    """The report in the model's final text. Structured outputs guarantee the shape, so this
    only guards against a cut-off or missing message."""
    try:
        report = json.loads(text)
    except json.JSONDecodeError as error:
        raise ReportError(f"The final message isn't valid JSON: {error}") from error
    if not isinstance(report, dict) or report.get("status") not in STATUSES:
        raise ReportError("The final message isn't a report with a valid status.")
    if missing := [key for key in REPORT_SCHEMA["required"] if key not in report]:
        raise ReportError(f"The report is missing {', '.join(missing)}.")
    return report
