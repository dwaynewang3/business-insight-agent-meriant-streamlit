"""People and companies: policyholders, policies, adjusters and repair shops."""

import re
from datetime import date, timedelta

import numpy as np
from faker import Faker

from .config import Scenario
from .domain import (
    AGE_BAND_WEIGHTS,
    AGE_BANDS,
    BASE_PREMIUM,
    EXCESSES,
    METROS,
    SHOP_NAME_SUFFIXES,
    STATE_PREMIUM_FACTOR,
)
from .timeline import month_starts, next_month


def _pick(rng: np.random.Generator, weights: dict[str, float], size: int) -> list[str]:
    """Draw `size` keys from a weights dict."""
    keys = list(weights)
    p = np.array([weights[k] for k in keys], dtype=float)
    return [keys[i] for i in rng.choice(len(keys), size=size, p=p / p.sum())]


def make_adjusters(scenario: Scenario, rng: np.random.Generator, fake: Faker) -> list[dict]:
    """Claims adjusters. Each works claims in one region."""
    rows: list[dict] = []
    for region, count in scenario.adjusters_per_region.items():
        for _ in range(count):
            rows.append({
                "adjuster_id": f"ADJ-{len(rows) + 1:03d}",
                "full_name": fake.name(),
                "region": region,
                "team": f"{region} claims",
                "hire_date": scenario.start_date - timedelta(days=int(rng.integers(180, 3650))),
                "leave_date": None,
            })
    return rows


def make_repair_shops(scenario: Scenario, rng: np.random.Generator, fake: Faker) -> list[dict]:
    """Motor repair shops spread across each state's metros. The first three are preferred."""
    rows: list[dict] = []
    for state in scenario.policies.state_weights:
        metros = list(METROS[state])
        for i in range(scenario.repair_shops_per_state):
            suffix = SHOP_NAME_SUFFIXES[int(rng.integers(len(SHOP_NAME_SUFFIXES)))]
            rows.append({
                "repair_shop_id": f"RS-{len(rows) + 1:03d}",
                "name": f"{fake.last_name()} {suffix}",
                "state": state,
                "metro": metros[i % len(metros)],
                "network_status": "preferred" if i < 3 else "non-preferred",
            })
    return rows


def _start_dates(scenario: Scenario, rng: np.random.Generator) -> list[date]:
    """Start dates for the policies already in force, then for each month's new business."""
    settings = scenario.policies
    starts = [
        scenario.start_date - timedelta(days=int(d))
        for d in rng.integers(1, 4 * 365, size=settings.initial_count)
    ]
    for month in month_starts(scenario.start_date, scenario.end_date):
        days_in_month = (next_month(month) - month).days
        new_business = rng.poisson(settings.initial_count * settings.monthly_new_business_rate)
        starts += [
            month + timedelta(days=int(d))
            for d in rng.integers(0, days_in_month, size=new_business)
        ]
    return starts


def make_policies(
    scenario: Scenario,
    rng: np.random.Generator,
    fake: Faker,
    extra_business: list[tuple[date, str, str]] = (),
) -> tuple[list[dict], list[dict]]:
    """Policies and their holders. Each policy has its own holder.

    `extra_business` adds policies with a fixed product and channel, as
    (start date, product, channel), for example from a new sales partnership.
    Policy numbers follow start dates, as they would in a real policy system.
    """
    settings = scenario.policies
    entries = [(start, None, None) for start in _start_dates(scenario, rng)]
    entries = sorted(entries + list(extra_business), key=lambda entry: entry[0])
    starts = [start for start, _, _ in entries]
    n = len(entries)
    states = _pick(rng, settings.state_weights, n)
    products = [
        forced or drawn
        for (_, forced, _), drawn in zip(entries, _pick(rng, settings.product_mix, n), strict=True)
    ]
    channels = [
        forced or drawn
        for (_, _, forced), drawn in zip(entries, _pick(rng, settings.channels, n), strict=True)
    ]
    years_to_lapse = rng.exponential(1 / settings.annual_lapse_rate, size=n)
    premium_spread = rng.lognormal(0, 0.25, size=n)
    age_bands = rng.choice(len(AGE_BANDS), size=n, p=AGE_BAND_WEIGHTS)

    holders, policies = [], []
    for i in range(n):
        state, product = states[i], products[i]
        metro_names = list(METROS[state])
        if len(metro_names) == 1 or rng.random() < 0.5:
            metro = metro_names[0]
        else:
            metro = metro_names[int(rng.integers(1, len(metro_names)))]
        prefixes = METROS[state][metro]
        postcode = f"{prefixes[int(rng.integers(len(prefixes)))]}{int(rng.integers(0, 10))}"

        # Policies already in force can lapse from the start date on; new ones from their start.
        lapse_from = max(starts[i], scenario.start_date)
        end = lapse_from + timedelta(days=int(years_to_lapse[i] * 365))

        first, last = fake.first_name(), fake.last_name()
        handle = ".".join(re.sub(r"[^a-z]", "", part.lower()) for part in (first, last))
        holder_id = f"C-{i + 1:06d}"
        holders.append({
            "policyholder_id": holder_id,
            "full_name": f"{first} {last}",
            "email": f"{handle}{int(rng.integers(1, 1000))}@example.com",
            "state": state,
            "postcode": postcode,
            "age_band": AGE_BANDS[age_bands[i]],
            "customer_since": starts[i],
        })
        premium = BASE_PREMIUM[product] * STATE_PREMIUM_FACTOR.get(state, 1.0) * premium_spread[i]
        policies.append({
            "policy_id": f"P-{i + 1:06d}",
            "policyholder_id": holder_id,
            "product": product,
            "state": state,
            "region": scenario.region_of_state[state],
            "metro": metro,
            "postcode": postcode,
            "channel": channels[i],
            "start_date": starts[i],
            "end_date": end if end <= scenario.as_of else None,
            "annual_premium": round(float(premium), 2),
            "excess": int(rng.choice(EXCESSES[product])),
        })
    return holders, policies
