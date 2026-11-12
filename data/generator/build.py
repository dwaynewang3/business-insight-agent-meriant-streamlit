"""Build one scenario's warehouse, plant its incidents, and write the answer key."""

import json
from pathlib import Path

import duckdb
import numpy as np
from faker import Faker

from data.compliance.build import add_claim_files
from mcp_servers.warehouse.access import restricted_path

from .checks import measure
from .claims import ClaimFactory, assign_ids, generate_claims
from .config import Scenario
from .entities import make_adjusters, make_policies, make_repair_shops
from .exposure import compute_exposure
from .incidents import (
    apply_staff_departures,
    channel_growth_evidence,
    duplicate_payments,
    early_claims,
    inject_notes,
    partner_business,
    reassign_departed_claims,
    shop_steering,
    weather_events,
)
from .restricted import write_restricted_copy
from .timeline import month_starts
from .writer import write_warehouse


def manifest_path(db_path: Path) -> Path:
    return db_path.with_name(f"{db_path.stem}_manifest.json")


def generate(scenario: Scenario, out_path: str | Path) -> dict:
    """Write the scenario's warehouse to a DuckDB file and return its manifest.

    A copy without personal data is written next to it (`<name>_restricted.duckdb`), for
    every role except the fraud team lead.

    The manifest, saved next to the database, is the answer key: each planted incident's
    question, explanation, evidence (IDs and dates) and measured size. The agent never
    sees it; the evals use it.
    """
    out_path = Path(out_path)
    rng = np.random.default_rng(scenario.seed)
    fake = Faker("en_AU")
    fake.seed_instance(scenario.seed)
    evidence: dict[str, dict] = {}

    # People, policies and exposure.
    adjusters = make_adjusters(scenario, rng, fake)
    evidence |= apply_staff_departures(scenario, adjusters)
    shops = make_repair_shops(scenario, rng, fake)
    holders, policies = make_policies(
        scenario, rng, fake, extra_business=partner_business(scenario, rng)
    )
    evidence |= channel_growth_evidence(scenario, policies)
    months = month_starts(scenario.start_date, scenario.end_date)
    exposure = compute_exposure(policies, months, scenario)

    # Claims and payments, including the incidents that change them.
    steering, steering_evidence = shop_steering(scenario, adjusters, shops, rng)
    evidence |= steering_evidence
    factory = ClaimFactory(scenario, adjusters, shops, rng, steering=steering)
    claims, payments = generate_claims(scenario, policies, exposure, factory, rng)
    weather_rows, storm_claims, storm_payments, weather_evidence = weather_events(
        scenario, policies, factory, rng
    )
    claims += storm_claims
    payments += storm_payments
    evidence |= weather_evidence
    fraud_claims, fraud_payments, fraud_evidence = early_claims(scenario, policies, factory, rng)
    claims += fraud_claims
    payments += fraud_payments
    evidence |= fraud_evidence
    reassign_departed_claims(claims, adjusters, rng)
    evidence |= duplicate_payments(scenario, payments)
    assign_ids(claims, payments)
    evidence |= inject_notes(scenario, claims, steering, rng)

    tables = {
        "warehouse_info": [{
            "extract_date": scenario.as_of,
            "data_start": scenario.start_date,
            "data_end": scenario.end_date,
        }],
        "policyholders": holders,
        "policies": policies,
        "exposure_monthly": exposure.rows,
        "claims": claims,
        "claim_payments": payments,
        "adjusters": adjusters,
        "repair_shops": shops,
        "weather_events": weather_rows,
    }
    write_warehouse(tables, out_path)
    write_restricted_copy(out_path, restricted_path(out_path))
    # The claim-file review sample for policy compliance holds no personal data, so both
    # copies get it (after the restricted copy, which carries tables but not views or macros).
    for path in (out_path, restricted_path(out_path)):
        add_claim_files(path)

    incidents, background = [], []
    with duckdb.connect(str(out_path), read_only=True) as con:
        for spec in scenario.incidents:
            entry = {
                "id": spec["id"],
                "number": spec.get("number"),
                "type": spec["type"],
                "question": spec.get("question"),
                "explanation": spec.get("explanation"),
                "evidence": evidence.get(spec["id"], {}),
                "measured": measure(con, scenario, spec, evidence.get(spec["id"], {})),
            }
            (background if spec.get("background") else incidents).append(entry)

    manifest = {
        "scenario": scenario.name,
        "seed": scenario.seed,
        "start_date": scenario.start_date,
        "end_date": scenario.end_date,
        "as_of": scenario.as_of,
        "row_counts": {name: len(rows) for name, rows in tables.items()},
        "incidents": incidents,
        "background_events": background,
    }
    manifest_path(out_path).write_text(json.dumps(manifest, indent=2, default=str) + "\n")
    return manifest
