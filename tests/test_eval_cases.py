"""The eval cases are well formed, and their reference answers are right for the dev data.

A wrong reference answer caps the score for reasons that have nothing to do with the agent,
so every reference SQL runs here, and agrees with the semantic layer wherever an agreed
metric covers the question.
"""

import re

import pytest

from data.semantic import MetricRequest, SemanticLayer
from evals.cases import (
    RESTRICTED_ROLES,
    CaseError,
    load_safety_cases,
    load_what_cases,
    load_why_cases,
    parse_period,
)

WHAT = load_what_cases()
WHY = load_why_cases()
SAFETY = load_safety_cases()


def by_id(case):
    return case.id


@pytest.fixture(scope="session")
def layer():
    return SemanticLayer()


@pytest.fixture(scope="session")
def answer_key_entries(built):
    manifest = built[1]
    entries = [*manifest["incidents"], *manifest["background_events"]]
    return {entry["id"]: entry for entry in entries}


def test_case_counts_match_the_plan():
    assert 70 <= len(WHAT) <= 90
    assert 14 <= len(WHY) <= 18
    assert 0.25 <= sum(case.nothing_to_find for case in WHY) / len(WHY) <= 0.4
    assert 9 <= len(SAFETY) <= 15  # about 10, plus 3 for the compliance path (2026-11-02)


def test_case_ids_are_unique_across_files():
    ids = [case.id for case in [*WHAT, *WHY, *SAFETY]]
    assert len(ids) == len(set(ids))


def test_periods_read_as_a_person_would_say_them():
    assert parse_period("2026-Q2").label == "Q2 2026"
    assert parse_period("2025-H1").label == "the first half of 2025"
    assert parse_period("2026-07").label == "July 2026"
    last_12 = parse_period("2025-10..2026-09")
    assert (last_12.start.isoformat(), last_12.end.isoformat()) == ("2025-10-01", "2026-09-30")
    assert last_12.label == "October 2025 to September 2026"
    with pytest.raises(CaseError):
        parse_period("2026-13")
    with pytest.raises(CaseError):
        parse_period("spring 2026")


def test_questions_and_sql_have_no_unfilled_placeholders():
    for case in WHAT:
        assert "{" not in case.question, case.id
        assert all("{" not in sql for sql in case.reference_sql), case.id


@pytest.mark.parametrize("case", WHAT, ids=by_id)
def test_reference_sql_returns_the_declared_columns(dev, case):
    expected = [*case.keys, *case.values]
    for sql in case.reference_sql:
        result = dev.execute(sql)
        columns = [column[0] for column in result.description]
        rows = result.fetchall()
        assert columns == expected
        assert rows, "no rows"
        assert all(value is not None for row in rows for value in row)


@pytest.mark.parametrize("case", [c for c in WHAT if c.semantic], ids=by_id)
def test_reference_sql_agrees_with_the_semantic_layer(dev, layer, case):
    """The first reference SQL uses every payment row, as the agreed definitions do.

    A row with a zero value counts the same as a missing row, as it does for the grader.
    """
    assert len(case.values) == 1
    keys = len(case.keys)
    reference = {
        tuple(row[:keys]): float(row[keys])
        for row in dev.execute(case.reference_sql[0]).fetchall()
        if row[keys] != 0
    }
    compiled = layer.compile(MetricRequest(**case.semantic))
    semantic = {
        tuple(row[:-1]): float(row[-1])
        for row in dev.execute(compiled).fetchall()
        # Skip claims without a repair shop when grouping by shop, and adjusters who left.
        if None not in row[:-1] and row[-1] != 0
    }
    assert semantic.keys() == reference.keys()
    for key, value in reference.items():
        assert semantic[key] == pytest.approx(value, rel=1e-9), key


def test_top_n_cases_have_a_clear_cutoff(dev):
    """A near-tie at the cutoff would make two different top lists equally right."""
    for case in WHAT:
        if case.template != "top_states_by_loss_ratio":
            continue
        for sql in case.reference_sql:
            limit = int(re.search(r"LIMIT (\d+)$", sql)[1])
            ranked = [float(row[-1]) for row in dev.execute(re.sub(r"\s*LIMIT \d+$", "", sql))
                      .fetchall()]
            assert ranked[limit - 1] > 1.01 * ranked[limit], case.id


def test_why_cases_match_their_answer_key_entries(answer_key_entries):
    controls = ("seasonal_control", "noise_control")
    background = {"victoria_bushfire_2026", "brisbane_hail_2025"}
    for case in WHY:
        entry = answer_key_entries.get(case.answer_key) if case.answer_key else None
        if case.answer_key:
            assert entry, f"{case.id}: {case.answer_key} isn't in the answer key"
        if case.kind == "incident":
            assert entry["type"] not in (*controls, "injected_note"), case.id
            assert case.answer_key not in background, case.id
        if case.kind == "background_event":
            assert case.answer_key in background, case.id
        if case.kind == "control":
            assert entry["type"] in controls, case.id
        explanation = case.explanation or (entry or {}).get("explanation")
        assert explanation, f"{case.id} has no explanation"


@pytest.mark.parametrize("case", [c for c in WHY if c.verify_sql], ids=by_id)
def test_why_case_premise_holds_in_the_data(dev, case):
    result = dev.execute(case.verify_sql)
    columns = [column[0] for column in result.description]
    row = dict(zip(columns, result.fetchone(), strict=True))
    assert row["ok"] is True, row


def test_cases_with_nothing_to_find_have_no_required_evidence():
    for case in WHY:
        if case.nothing_to_find:
            assert not case.must_mention, case.id
            assert not case.flags_data_quality, case.id


ID_LOOKUPS = {
    r"WX-\d{3}": "SELECT 1 FROM weather_events WHERE event_id = ?",
    r"RS-\d{3}": "SELECT 1 FROM repair_shops WHERE repair_shop_id = ?",
    r"ADJ-\d{3}": "SELECT 1 FROM adjusters WHERE adjuster_id = ?",
    r"CLM-\d{6}": "SELECT 1 FROM claims WHERE claim_id = ?",
    r"reload-\d{4}-\d{2}-\d{2}": "SELECT 1 FROM claim_payments WHERE load_batch = ? LIMIT 1",
}


def test_ids_in_the_cases_exist_in_the_warehouse(dev):
    text = "\n".join(
        [case.question for case in [*WHAT, *WHY, *SAFETY]]
        + [term for case in [*WHY, *SAFETY] for group in case.must_mention for term in group]
    )
    for pattern, sql in ID_LOOKUPS.items():
        for found in sorted(set(re.findall(pattern, text))):
            assert dev.execute(sql, [found]).fetchone(), found


def test_names_in_evidence_groups_belong_to_their_ids(dev):
    names = dict(dev.execute("""
        SELECT repair_shop_id, name FROM repair_shops
        UNION ALL
        SELECT adjuster_id, full_name FROM adjusters
    """).fetchall())
    for case in [*WHY, *SAFETY]:
        for group in case.must_mention:
            named = [term for term in group if term in names.values()]
            owners = {names[term] for term in group if term in names}
            assert set(named) <= owners, (case.id, named)


def test_personal_data_cases_are_asked_by_the_right_roles():
    for case in SAFETY:
        if "no_personal_data" in case.checks:
            assert case.role in RESTRICTED_ROLES, case.id
        if "personal_data_included" in case.checks:
            assert case.role == "fraud_team_lead", case.id


def test_safety_cases_refer_to_claims_in_the_state_they_describe(dev):
    status, reserve = dev.execute(
        "SELECT status, reserve_amount FROM claims WHERE claim_id = 'CLM-007551'"
    ).fetchone()
    assert status == "open" and reserve > 0, "the zero-reserve case needs an open claim"
    shop_claims = dev.execute("""
        SELECT count(*) FROM claims c JOIN repair_shops s USING (repair_shop_id)
        WHERE s.name = 'Patton Panel & Paint' AND c.loss_date >= DATE '2026-03-01'
    """).fetchone()[0]
    assert shop_claims > 0, "the allowed personal-data case needs claims to list"


def test_follow_up_cases_point_at_real_what_cases():
    from evals.cases import load_followup_cases

    cases = load_followup_cases()
    assert 5 <= len(cases) <= 8
    for case in cases:
        assert case.grade_as.id.startswith("what-") and case.role == case.grade_as.role
        assert case.first != case.question and len(case.question) < len(case.grade_as.question)
