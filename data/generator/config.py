"""Scenario settings: everything that differs between the dev and test data."""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml


@dataclass(frozen=True)
class PolicySettings:
    initial_count: int  # policies in force on the start date
    monthly_new_business_rate: float  # new policies per month, as a share of initial_count
    annual_lapse_rate: float  # share of policies that end each year
    product_mix: dict[str, float]
    state_weights: dict[str, float]
    channels: dict[str, float]


@dataclass(frozen=True)
class Scenario:
    name: str
    seed: int
    start_date: date
    end_date: date
    as_of: date  # extract date: anything reported or paid later isn't in the data yet
    regions: dict[str, list[str]]
    policies: PolicySettings
    adjusters_per_region: dict[str, int]
    repair_shops_per_state: int
    incidents: list[dict] = field(default_factory=list)

    @property
    def region_of_state(self) -> dict[str, str]:
        return {state: region for region, states in self.regions.items() for state in states}


def load_scenario(path: str | Path) -> Scenario:
    raw = yaml.safe_load(Path(path).read_text())
    return Scenario(
        name=raw["name"],
        seed=raw["seed"],
        start_date=raw["start_date"],
        end_date=raw["end_date"],
        as_of=raw["as_of"],
        regions=raw["regions"],
        policies=PolicySettings(**raw["policies"]),
        adjusters_per_region=raw["adjusters_per_region"],
        repair_shops_per_state=raw["repair_shops_per_state"],
        incidents=raw.get("incidents") or [],
    )
