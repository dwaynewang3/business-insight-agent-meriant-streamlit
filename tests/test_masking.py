"""Masking personal data in free text: claim notes in the copy of the warehouse without
personal data, and the text tracing sends to Langfuse."""

import duckdb
import pytest

from mcp_servers.warehouse.access import restricted_path
from mcp_servers.warehouse.masking import Masker


@pytest.fixture(scope="module")
def masker():
    return Masker(["Mark Webb", "Alison Thompson", "Mary Anne Lee"])


@pytest.mark.parametrize("text, masked", [
    ("Spoke with Mark Webb on 0412 345 678.", "Spoke with [name] on [phone]."),
    ("Insured Mark Webb called back.", "Insured [name] called back."),
    ("Photos received from Alison Thompson (alison.thompson487@example.com).",
     "Photos received from [name] ([email])."),
    ("Landline (02) 9876 5432, or +61 412 345 678.", "Landline [phone], or [phone]."),
    ("MARY ANNE LEE and Mary Anne Lee", "[name] and [name]"),  # three words, any case
])
def test_names_emails_and_phone_numbers_are_masked(masker, text, masked):
    assert masker.mask(text) == masked


@pytest.mark.parametrize("text", [
    "Hail dents across bonnet, roof and boot. Photos attached.",
    "Claim CLM-004512 paid AUD 20,890 on 2026-07-14 to Melbourne Smash Repairs.",
    "Two-car collision at a roundabout. Postcode 3000, policy P-000123.",
    "New South Wales and Mark Twain aren't policyholders.",
])
def test_text_without_personal_data_is_unchanged(masker, text):
    assert masker.mask(text) == text


def test_json_like_values_are_masked_throughout(masker):
    data = {"answer": "Mark Webb has two claims.", "rows": 2,
            "findings": [{"claim": "Email mark@example.com", "value": 1.5}]}
    assert masker.mask_data(data) == {"answer": "[name] has two claims.", "rows": 2,
                                      "findings": [{"claim": "Email [email]", "value": 1.5}]}
    assert masker.mask(None) is None


def test_notes_carry_contact_details_and_only_the_full_warehouse_shows_them(built):
    con, _, path = built
    named = {claim_id: (notes, name) for claim_id, notes, name in con.execute("""
        SELECT c.claim_id, c.notes, h.full_name FROM claims c
        JOIN policies p USING (policy_id) JOIN policyholders h USING (policyholder_id)
        WHERE contains(c.notes, h.full_name)
    """).fetchall()}
    # About 4% of claims have the policyholder's name in their notes, with a phone or email.
    claims = con.execute("SELECT count(*) FROM claims").fetchone()[0]
    assert 0.02 < len(named) / claims < 0.06
    with duckdb.connect(str(restricted_path(path)), read_only=True) as restricted:
        masked = dict(restricted.execute(
            "SELECT claim_id, notes FROM claims WHERE claim_id IN "
            f"({', '.join(repr(i) for i in named)})").fetchall())
        for claim_id, (_, name) in named.items():
            assert name not in masked[claim_id] and "[name]" in masked[claim_id]
        assert "@example.com" not in " ".join(masked.values())
        # Notes without personal data are copied as they are.
        unchanged = restricted.execute(
            "SELECT count(*) FROM claims WHERE notes LIKE 'Stone chip%'").fetchone()[0]
        assert unchanged == con.execute(
            "SELECT count(*) FROM claims WHERE notes LIKE 'Stone chip%'").fetchone()[0] > 0
