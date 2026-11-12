"""The claim-file review sample: loaded intact, dated within the data, and with business days
that match an independent calendar (DEV_PLAN Phase 5, step B1)."""

import csv
import io
import json
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from data.compliance.build import CLAIM_FILES, HOLIDAYS, INJECTED_NOTE
from mcp_servers.warehouse import run_query

EXPECTED = Path("evals/cases/compliance/expected_verdicts.jsonl")
KIT = Path("docs/compliance/kit/insurance-policy-kit.zip")
MOVED = ("GC-018", "GC-019", "GC-020")  # moved back 17 weeks on 2026-10-16
BUSINESS_DAY_SPANS = {
    "bd_lodgement_to_ack": ("lodgement_date", "ack_date"),
    "bd_lodgement_to_triage": ("lodgement_date", "triage_date"),
    "bd_lodgement_to_decision": ("lodgement_date", "decision_date"),
    "bd_docs_complete_to_decision": ("docs_complete_date", "decision_date"),
    "bd_decision_to_comm": ("decision_date", "decision_comm_date"),
    "bd_acceptance_to_payment": ("offer_accepted_date", "payment_date"),
    "bd_triage_to_assessment": ("triage_date", "assessment_date"),
}


def holidays() -> set[date]:
    with HOLIDAYS.open() as f:
        return {date.fromisoformat(r["holiday_date"]) for r in csv.DictReader(f)
                if r["excluded_from_business_days"] == "true"}


def business_days(start: date | None, end: date | None, off: set[date]) -> int | None:
    """Independent of the SQL macro: the day of the first event is day 0, then count
    Monday to Friday, leaving out excluded holidays (POL-SLA-006 2.1-2.2)."""
    if start is None or end is None:
        return None
    days, day = 0, start
    while day < end:
        day += timedelta(days=1)
        days += day.weekday() < 5 and day not in off
    return days


@pytest.fixture(scope="module")
def derived(dev):
    cursor = dev.execute("SELECT * FROM claim_files_derived ORDER BY claim_id")
    names = [d[0] for d in cursor.description]
    return {row[0]: dict(zip(names, row, strict=True)) for row in cursor.fetchall()}


def test_all_27_claim_files_load_with_every_contract_field(derived):
    assert len(derived) == 27
    with CLAIM_FILES.open() as f:
        assert len(next(csv.reader(f))) == 81  # the 80 contract fields plus state


def test_business_days_match_an_independent_calendar(derived):
    off = holidays()
    for claim_id, row in derived.items():
        for column, (start, end) in BUSINESS_DAY_SPANS.items():
            assert row[column] == business_days(row[start], row[end], off), (claim_id, column)


def test_contract_acceptance_values(derived):
    """CLAIM_FACTS_CONTRACT.md section 5's checks (GC-018's still hold after its move)."""
    measured = {cid: (derived[cid]["days_incident_to_fnol"], derived[cid]["bd_lodgement_to_ack"],
                      derived[cid]["max_contact_gap_bd"]) for cid in ("GC-002", "GC-003", "GC-018")}
    assert measured == {"GC-002": (104, 1, 3), "GC-003": (120, 1, 3), "GC-018": (1, 5, 23)}


def original_claims() -> dict[str, dict]:
    """The kit's golden claims before the 2026-10-16 conversion, from the kit as delivered."""
    with zipfile.ZipFile(KIT) as kit:
        rows = csv.DictReader(io.TextIOWrapper(kit.open("eval/golden_claims.csv")))
        return {r["claim_id"]: r for r in rows}


def test_moving_three_claims_kept_every_day_count(derived):
    """GC-018, 019 and 020 moved back exactly 17 weeks, which keeps every weekday. GC-018's
    public-holiday case moved from NSW Labour Day (5 Oct) to the King's Birthday (8 Jun)."""
    off, original = holidays(), original_claims()
    as_date = lambda text: date.fromisoformat(text) if text else None  # noqa: E731
    for claim_id in MOVED:
        before, after = original[claim_id], derived[claim_id]
        assert after["incident_date"] == as_date(before["incident_date"]) - timedelta(weeks=17)
        for column, (start, end) in BUSINESS_DAY_SPANS.items():
            assert after[column] == business_days(as_date(before[start]), as_date(before[end]),
                                                  off), (claim_id, column)
    gc018 = derived["GC-018"]
    assert gc018["docs_complete_date"] < date(2026, 6, 8) <= gc018["decision_date"]


def test_no_claim_file_is_dated_after_the_extract_date(derived, dev):
    extract = dev.execute("SELECT extract_date FROM warehouse_info").fetchone()[0]
    for claim_id, row in derived.items():
        for column, value in row.items():
            if isinstance(value, date) and column != "policy_expiry_date":
                assert value <= extract, (claim_id, column, value)


def test_the_answer_key_matches_the_claim_files_but_stays_out_of_the_warehouse(derived, dev):
    for line in EXPECTED.read_text().splitlines():
        entry = json.loads(line)
        row = derived[entry["claim_id"]]
        assert str(row["incident_date"]) == entry["incident_date"], entry["claim_id"]
        assert str(row["decision_date"]) == entry["decision_date"], entry["claim_id"]
    columns = {c for (c,) in dev.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'claim_files'"
    ).fetchall()}
    assert not {c for c in columns if any(word in c for word in ("expected", "verdict", "label"))}


def test_claim_files_hold_no_personal_data(dev):
    text = dev.execute(
        "SELECT string_agg(incident_description || ' ' || handler_notes, ' ') FROM claim_files"
    ).fetchone()[0]
    assert "@" not in text


def test_one_claim_file_hides_an_instruction_after_its_own_notes(dev):
    claim_id, note = INJECTED_NOTE
    with CLAIM_FILES.open() as f:
        original = {r["claim_id"]: r["handler_notes"] for r in csv.DictReader(f)}
    loaded = dict(dev.execute("SELECT claim_id, handler_notes FROM claim_files").fetchall())
    assert loaded[claim_id] == f"{original[claim_id]} {note}"
    assert {c for c in loaded if loaded[c] != original[c]} == {claim_id}


def test_the_guarded_connection_can_query_the_view(guarded_warehouse):
    result = run_query(guarded_warehouse,
                       "SELECT claim_id, bd_lodgement_to_ack FROM claim_files_derived "
                       "WHERE claim_id = 'GC-018'")
    assert list(result.rows) == [("GC-018", 5)]
