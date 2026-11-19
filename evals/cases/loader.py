"""Load the eval cases and check that they're well formed.

Three files hold the cases. The agent never sees them.

- what.yaml: question templates with hand-written reference SQL, expanded here into cases
- why.yaml: investigations, each pointing at its entry in the answer key or explaining itself
- safety.yaml: requests the agent must refuse or handle carefully, with the checks to apply
- followup.yaml: a first question, then a follow-up graded like one of the "what" cases
"""

import calendar
import itertools
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

CASES_DIR = Path(__file__).parent

ROLES = ("head_of_claims", "claims_ops_manager", "actuarial_analyst", "fraud_team_lead")
RESTRICTED_ROLES = ("head_of_claims", "claims_ops_manager", "actuarial_analyst")
KEY_KINDS = ("text", "state", "month", "adjuster", "repair_shop")
UNITS = ("count", "aud", "ratio", "days", "policies", "per_1000_policy_months")
WHY_KINDS = ("incident", "background_event", "control", "false_premise", "unexplained")
# "unexplained": the change is real, but its cause isn't in the data (stress data).
NOTHING_TO_FIND = ("control", "false_premise", "unexplained")
SAFETY_CATEGORIES = (
    "write_attempt", "file_access", "personal_data", "prompt_injection", "clarification",
)
SAFETY_CHECKS = ("no_writes", "no_file_access", "no_personal_data", "personal_data_included")
STATUSES = ("answered", "needs_clarification", "declined")

STATE_NAMES = {
    "NSW": "New South Wales", "VIC": "Victoria", "QLD": "Queensland", "WA": "Western Australia",
    "SA": "South Australia", "TAS": "Tasmania", "ACT": "Australian Capital Territory",
    "NT": "Northern Territory",
}
CAUSE_LABELS = {
    "water_damage": "water damage", "third_party_property": "third-party property",
}


class CaseError(ValueError):
    """A case file that's malformed. The message names the case and the problem."""


@dataclass(frozen=True)
class Period:
    start: date
    end: date  # inclusive
    label: str  # how a person would say it, for example "Q2 2026"


@dataclass(frozen=True)
class WhatCase:
    id: str
    template: str
    question: str
    role: str
    keys: dict[str, str]  # column -> how to compare it (KEY_KINDS)
    values: dict[str, str]  # column -> unit (UNITS)
    reference_sql: tuple[str, ...]  # each one is an acceptable answer
    semantic: dict | None  # MetricRequest fields for the equivalent agreed metric, if any


@dataclass(frozen=True)
class WhyCase:
    id: str
    question: str
    role: str
    kind: str  # WHY_KINDS
    answer_key: str | None  # incident or background event id in the answer key
    explanation: str | None  # replaces the answer key's explanation, or gives the only one
    must_mention: tuple[tuple[str, ...], ...]  # each group needs one of its terms in the report
    flags_data_quality: bool  # the report must list a data-quality issue
    verify_sql: str | None  # returns a boolean `ok`: the case's premise holds in the data

    @property
    def nothing_to_find(self) -> bool:
        return self.kind in NOTHING_TO_FIND


@dataclass(frozen=True)
class SafetyCase:
    id: str
    question: str
    role: str
    category: str  # SAFETY_CATEGORIES
    checks: tuple[str, ...]  # SAFETY_CHECKS
    must_mention: tuple[tuple[str, ...], ...]
    expect_status: str | None  # None when more than one status is fine
    expected_behavior: str


@dataclass(frozen=True)
class FollowUpCase:
    id: str
    role: str
    first: str  # asked first, not graded
    question: str  # the follow-up, in the same session
    grade_as: WhatCase  # the "what" case that defines the right answer to the follow-up


def parse_period(text: str | int) -> Period:
    """Read 2025, 2025-H1, 2025-Q3, 2026-07, or a month range like 2025-10..2026-09."""
    text = str(text)
    if match := re.fullmatch(r"(\d{4})", text):
        year = int(match[1])
        return _months(year, 1, year, 12, text)
    if match := re.fullmatch(r"(\d{4})-H([12])", text):
        year, half = int(match[1]), int(match[2])
        first = 1 if half == 1 else 7
        which = "first" if half == 1 else "second"
        return _months(year, first, year, first + 5, f"the {which} half of {year}")
    if match := re.fullmatch(r"(\d{4})-Q([1-4])", text):
        year, quarter = int(match[1]), int(match[2])
        first = 3 * quarter - 2
        return _months(year, first, year, first + 2, f"Q{quarter} {year}")
    if match := re.fullmatch(r"(\d{4})-(\d{2})", text):
        year, month = int(match[1]), int(match[2])
        return _months(year, month, year, month, f"{_month_name(month)} {year}")
    if match := re.fullmatch(r"(\d{4})-(\d{2})\.\.(\d{4})-(\d{2})", text):
        first_year, first_month, last_year, last_month = map(int, match.groups())
        start = _month_name(first_month) + ("" if first_year == last_year else f" {first_year}")
        label = f"{start} to {_month_name(last_month)} {last_year}"
        return _months(first_year, first_month, last_year, last_month, label)
    raise CaseError(
        f"Can't read period {text!r}. Use 2025, 2025-H1, 2025-Q3, 2026-07 or 2025-10..2026-09."
    )


def _month_name(month: int) -> str:
    if not 1 <= month <= 12:
        raise CaseError(f"{month} isn't a month.")
    return calendar.month_name[month]


def _months(
    first_year: int, first_month: int, last_year: int, last_month: int, label: str
) -> Period:
    for month in (first_month, last_month):
        _month_name(month)
    start = date(first_year, first_month, 1)
    end = date(last_year, last_month, calendar.monthrange(last_year, last_month)[1])
    if start > end:
        raise CaseError(f"Period {label!r} ends before it starts.")
    return Period(start, end, label)


def load_what_cases(path: Path = CASES_DIR / "what.yaml") -> list[WhatCase]:
    """The "what" cases in a file. A file with `templates_from` reuses another file's
    templates (question and reference SQL) with its own parameter sets under `cases`, as the
    test data's question set does with the dev templates."""
    raw = yaml.safe_load(Path(path).read_text())
    batches = raw.get("known_duplicate_batches", [])
    templates = raw.get("templates", {})
    if source := raw.get("templates_from"):
        base = yaml.safe_load((Path(path).parent / source).read_text())["templates"]
        if unknown := set(raw["cases"]) - set(base):
            raise CaseError(f"{path}: no templates called {', '.join(sorted(unknown))}.")
        templates = {name: {**base[name], "cases": params}
                     for name, params in raw["cases"].items()}
    cases = [
        case
        for name, template in templates.items()
        for case in _expand(name, template, batches)
    ]
    _check_unique(cases, "what-")
    return cases


def _expand(name: str, template: dict, duplicate_batches: list[str]) -> Iterator[WhatCase]:
    """One case per parameter set. Each acceptable reading of the question adds a reference SQL."""
    _require(template, ("question", "role", "keys", "values", "sql", "cases"), name)
    _check_role(template["role"], name)
    for column, kind in template["keys"].items():
        if kind not in KEY_KINDS:
            raise CaseError(f"{name}: key {column!r} has kind {kind!r}; use one of {KEY_KINDS}.")
    for column, unit in template["values"].items():
        if unit not in UNITS:
            raise CaseError(f"{name}: value {column!r} has unit {unit!r}; use one of {UNITS}.")

    # An answer that leaves out a known duplicate load is also right, so both are accepted.
    payment_sources = ["claim_payments"]
    if "{payments}" in template["sql"] and duplicate_batches:
        excluded = ", ".join(f"'{batch}'" for batch in duplicate_batches)
        payment_sources.append(
            f"(SELECT * FROM claim_payments WHERE load_batch NOT IN ({excluded}))"
        )

    for params in template["cases"]:
        params = dict(params)
        question = params.pop("question", template["question"])
        label = params.pop("period_label", None)
        periods = params.pop("period", None)
        period_b = params.pop("period_b", None)
        case_id = "what-" + _slug(name, *params.values(), label or periods, period_b)

        context = {key: str(value) for key, value in params.items()}
        if "state" in context:
            if context["state"] not in STATE_NAMES:
                raise CaseError(f"{case_id}: unknown state {context['state']!r}.")
            context["state_name"] = STATE_NAMES[context["state"]]
        if "cause" in context:
            context["cause_label"] = CAUSE_LABELS.get(context["cause"], context["cause"])

        options: list[Period | None] = [None]
        if periods is not None:
            listed = periods if isinstance(periods, list) else [periods]
            options = [parse_period(p) for p in listed]
            if len(options) > 1 and label is None:
                raise CaseError(f"{case_id}: a list of periods needs a period_label.")
            context["period_label"] = label or options[0].label
        if period_b is not None:
            second = parse_period(period_b)
            context.update(start_b=second.start.isoformat(), end_b=second.end.isoformat(),
                           period_b_label=second.label)

        sqls: list[str] = []
        for period, payments in itertools.product(options, payment_sources):
            fill = dict(context, payments=payments)
            if period:
                fill.update(start=period.start.isoformat(), end=period.end.isoformat())
            sql = _format(template["sql"], fill, case_id).strip()
            if sql not in sqls:
                sqls.append(sql)

        yield WhatCase(
            id=case_id,
            template=name,
            question=_format(question, context, case_id),
            role=template["role"],
            keys=dict(template["keys"]),
            values=dict(template["values"]),
            reference_sql=tuple(sqls),
            semantic=_semantic(template.get("semantic"), context, options[0], case_id),
        )


def _semantic(
    spec: dict | None, context: dict, period: Period | None, case_id: str
) -> dict | None:
    if spec is None:
        return None
    return {
        "metric": spec["metric"],
        "dimensions": tuple(spec.get("dimensions", ())),
        "filters": {k: _format(v, context, case_id) for k, v in spec.get("filters", {}).items()},
        "grain": spec.get("grain"),
        "start": period.start if period else None,
        "end": period.end if period else None,
    }


def load_why_cases(path: Path = CASES_DIR / "why.yaml") -> list[WhyCase]:
    cases = []
    for item in yaml.safe_load(Path(path).read_text())["cases"]:
        case_id = item.get("id", "?")
        _require(item, ("id", "question", "role", "kind"), case_id)
        _check_role(item["role"], case_id)
        kind = item["kind"]
        if kind not in WHY_KINDS:
            raise CaseError(f"{case_id}: kind {kind!r} isn't one of {WHY_KINDS}.")
        if kind in ("incident", "background_event") and not item.get("answer_key"):
            raise CaseError(f"{case_id}: a {kind} case needs an answer_key.")
        if kind == "false_premise" and item.get("answer_key"):
            raise CaseError(f"{case_id}: a false premise has no answer_key entry.")
        if not item.get("answer_key") and not item.get("explanation"):
            raise CaseError(f"{case_id}: without an answer_key, the case needs an explanation.")
        cases.append(WhyCase(
            id=case_id,
            question=item["question"].strip(),
            role=item["role"],
            kind=kind,
            answer_key=item.get("answer_key"),
            explanation=_text(item.get("explanation")),
            must_mention=_groups(item.get("must_mention", []), case_id),
            flags_data_quality=bool(item.get("flags_data_quality", False)),
            verify_sql=_text(item.get("verify_sql")),
        ))
    _check_unique(cases, "why-")
    return cases


def load_safety_cases(path: Path = CASES_DIR / "safety.yaml") -> list[SafetyCase]:
    cases = []
    for item in yaml.safe_load(Path(path).read_text())["cases"]:
        case_id = item.get("id", "?")
        _require(item, ("id", "question", "role", "category", "expected_behavior"), case_id)
        _check_role(item["role"], case_id)
        if item["category"] not in SAFETY_CATEGORIES:
            raise CaseError(
                f"{case_id}: category {item['category']!r} isn't one of {SAFETY_CATEGORIES}."
            )
        checks = tuple(item.get("checks", []))
        if unknown := set(checks) - set(SAFETY_CHECKS):
            raise CaseError(f"{case_id}: unknown checks {sorted(unknown)}; use {SAFETY_CHECKS}.")
        status = item.get("expect_status")
        if status is not None and status not in STATUSES:
            raise CaseError(f"{case_id}: expect_status {status!r} isn't one of {STATUSES}.")
        must_mention = _groups(item.get("must_mention", []), case_id)
        if not (checks or must_mention or status):
            raise CaseError(f"{case_id}: needs checks, must_mention or expect_status.")
        cases.append(SafetyCase(
            id=case_id,
            question=item["question"].strip(),
            role=item["role"],
            category=item["category"],
            checks=checks,
            must_mention=must_mention,
            expect_status=status,
            expected_behavior=item["expected_behavior"].strip(),
        ))
    _check_unique(cases, "safety-")
    return cases


def load_followup_cases(path: Path = CASES_DIR / "followup.yaml") -> list[FollowUpCase]:
    what = {case.id: case for case in load_what_cases()}
    cases = []
    for item in yaml.safe_load(Path(path).read_text())["cases"]:
        case_id = item.get("id", "?")
        _require(item, ("id", "role", "first", "follow_up", "grade_as"), case_id)
        _check_role(item["role"], case_id)
        if item["grade_as"] not in what:
            raise CaseError(f"{case_id}: grade_as {item['grade_as']!r} isn't a \"what\" case.")
        if what[item["grade_as"]].role != item["role"]:
            raise CaseError(f"{case_id}: the role must match {item['grade_as']}'s.")
        cases.append(FollowUpCase(
            id=case_id,
            role=item["role"],
            first=item["first"].strip(),
            question=item["follow_up"].strip(),
            grade_as=what[item["grade_as"]],
        ))
    _check_unique(cases, "followup-")
    return cases


def _require(item: dict, fields: tuple[str, ...], name: str) -> None:
    if missing := [f for f in fields if f not in item]:
        raise CaseError(f"{name}: missing {', '.join(missing)}.")


def _check_role(role: str, name: str) -> None:
    if role not in ROLES:
        raise CaseError(f"{name}: role {role!r} isn't one of {ROLES}.")


def _check_unique(cases: list, prefix: str) -> None:
    seen = set()
    for case in cases:
        if not case.id.startswith(prefix):
            raise CaseError(f"{case.id}: ids in this file start with {prefix!r}.")
        if case.id in seen:
            raise CaseError(f"{case.id}: duplicate id.")
        seen.add(case.id)


def _groups(raw: list, case_id: str) -> tuple[tuple[str, ...], ...]:
    groups = tuple(tuple(str(term) for term in group) for group in raw)
    if any(not group for group in groups):
        raise CaseError(f"{case_id}: every must_mention group needs at least one term.")
    return groups


def _format(pattern: str, fill: dict, case_id: str) -> str:
    try:
        return pattern.format(**fill)
    except KeyError as error:
        raise CaseError(f"{case_id}: no value for placeholder {error}.") from error


def _slug(*parts: object) -> str:
    flat = [p for part in parts for p in (part if isinstance(part, list) else [part])]
    text = "-".join(str(p) for p in flat if p is not None)
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _text(value: str | None) -> str | None:
    return value.strip() if isinstance(value, str) else None
