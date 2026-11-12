"""Policies in force and earned premium per month."""

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from .config import Scenario
from .timeline import next_month


@dataclass
class Exposure:
    months: list[date]
    in_force: np.ndarray  # share of each month (column) that each policy (row) was in force
    rows: list[dict]  # the exposure_monthly table


def coverage_end(policy: dict, as_of: date) -> date:
    """First day a policy no longer covers. Active policies are covered through the extract date."""
    return policy["end_date"] or as_of + timedelta(days=1)


def compute_exposure(policies: list[dict], months: list[date], scenario: Scenario) -> Exposure:
    start = np.array([p["start_date"].toordinal() for p in policies])
    end = np.array([coverage_end(p, scenario.as_of).toordinal() for p in policies])
    in_force = np.zeros((len(policies), len(months)))
    for m, month in enumerate(months):
        first, after_last = month.toordinal(), next_month(month).toordinal()
        overlap = np.clip(np.minimum(end, after_last) - np.maximum(start, first), 0, None)
        in_force[:, m] = overlap / (after_last - first)

    monthly_premium = np.array([p["annual_premium"] for p in policies]) / 12
    state = np.array([p["state"] for p in policies])
    product = np.array([p["product"] for p in policies])
    rows = []
    for group_state, group_product in sorted(set(zip(state, product, strict=True))):
        mask = (state == group_state) & (product == group_product)
        policies_in_force = in_force[mask].sum(axis=0)
        earned = (in_force[mask] * monthly_premium[mask, None]).sum(axis=0)
        for m, month in enumerate(months):
            rows.append({
                "month": month,
                "state": str(group_state),
                "region": scenario.region_of_state[str(group_state)],
                "product": str(group_product),
                "policies_in_force": round(float(policies_in_force[m]), 2),
                "earned_premium": round(float(earned[m]), 2),
            })
    return Exposure(months, in_force, rows)
