"""Claims and their payments, drawn month by month from the policies in force."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from .config import Scenario
from .domain import (
    CAUSES,
    CLOSED_WITHOUT_PAYMENT_RATE,
    LONG_TAIL_CAUSES,
    NOTE_TEMPLATES,
    STATE_COST_FACTOR,
    seasonal_factor,
)
from .exposure import Exposure, coverage_end
from .timeline import next_month


def add_typo(text: str, rng: np.random.Generator) -> str:
    """Swap two neighboring letters in one word, the way hurried notes get typed."""
    words = text.split(" ")
    candidates = [i for i, word in enumerate(words) if len(word) > 4 and word.isalpha()]
    if not candidates:
        return text
    i = candidates[int(rng.integers(len(candidates)))]
    word = words[i]
    j = int(rng.integers(1, len(word) - 2))
    words[i] = word[:j] + word[j + 1] + word[j] + word[j + 2 :]
    return " ".join(words)


@dataclass
class ShopSteering:
    """A repair shop that, from `start_date`, is sent extra work and inflates its estimates.

    One adjuster handles most of its claims, which is the pattern a fraud team looks for.
    """

    shop: dict
    adjuster: dict
    start_date: date
    steering_share: float  # share of the metro's repair claims sent straight to this shop
    cost_factor: float
    adjuster_share: float  # share of the shop's claims given to the one adjuster


class ClaimFactory:
    """Builds one claim's life: report, adjuster, repair shop, cost, payments and closing.

    Everything after the extract date (`as_of`) is cut off, as in a real warehouse:
    claims reported later are missing, and claims still being handled are open.
    """

    def __init__(
        self,
        scenario: Scenario,
        adjusters: list[dict],
        shops: list[dict],
        rng: np.random.Generator,
        steering: ShopSteering | None = None,
    ):
        self.rng = rng
        self.as_of = scenario.as_of
        self.steering = steering
        self.adjusters_by_region: dict[str, list[dict]] = defaultdict(list)
        for adjuster in adjusters:
            self.adjusters_by_region[adjuster["region"]].append(adjuster)
        self.normal_staff = {
            region: len(self.active_adjusters(region, scenario.start_date))
            for region in self.adjusters_by_region
        }
        self.shops_by_area: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for shop in shops:
            self.shops_by_area[(shop["state"], shop["metro"])].append(shop)

    def active_adjusters(self, region: str, day: date) -> list[dict]:
        return [
            a
            for a in self.adjusters_by_region[region]
            if a["hire_date"] <= day and (a["leave_date"] is None or a["leave_date"] > day)
        ]

    def make(
        self,
        policy: dict,
        cause: str,
        loss_date: date,
        *,
        cost_factor: float = 1.0,
        adjuster: dict | None = None,
        shop: dict | None = None,
    ) -> tuple[dict | None, list[dict]]:
        """Return the claim and its payments, or (None, []) if it isn't reported by `as_of`."""
        spec = CAUSES[policy["product"]][cause]
        report_date = loss_date + timedelta(days=self._report_lag(cause))
        if report_date > self.as_of:
            return None, []

        active = self.active_adjusters(policy["region"], report_date)
        if spec["shop"] and shop is None:
            shop = self._pick_shop(policy, report_date)
        steering = self.steering
        if steering and shop is steering.shop and report_date >= steering.start_date:
            cost_factor *= steering.cost_factor
            if (
                adjuster is None
                and steering.adjuster in active
                and self.rng.random() < steering.adjuster_share
            ):
                adjuster = steering.adjuster
        adjuster = adjuster or active[int(self.rng.integers(len(active)))]

        cost = (
            spec["median"]
            * self.rng.lognormal(0, spec["sigma"])
            * STATE_COST_FACTOR.get(policy["state"], 1.0)
            * cost_factor
        )
        # Fewer adjusters on hand than normal means every claim waits longer.
        workload = self.normal_staff[policy["region"]] / max(len(active), 1)
        close_days = max(1, round(spec["close_days"] * self.rng.lognormal(0, 0.35) * workload))
        close_date = report_date + timedelta(days=close_days)

        is_paid = self.rng.random() >= CLOSED_WITHOUT_PAYMENT_RATE
        schedule = self._payment_schedule(cost, report_date, close_date) if is_paid else []
        made = [(day, amount) for day, amount in schedule if day <= self.as_of]
        is_closed = close_date <= self.as_of
        if is_closed:
            reserve = 0.0
        else:
            # Case reserves are estimates: right on average, off for any single claim.
            estimate = cost * self.rng.lognormal(-0.02, 0.2)
            reserve = max(round(float(estimate - sum(a for _, a in made)), 2), 0.0)

        claim = {
            "claim_id": None,  # numbered after all claims exist, in report order
            "policy_id": policy["policy_id"],
            "product": policy["product"],
            "cause": cause,
            "state": policy["state"],
            "region": policy["region"],
            "postcode": policy["postcode"],
            "loss_date": loss_date,
            "report_date": report_date,
            "status": "closed" if is_closed else "open",
            "adjuster_id": adjuster["adjuster_id"],
            "repair_shop_id": shop["repair_shop_id"] if shop else None,
            "reserve_amount": reserve,
            "close_date": close_date if is_closed else None,
            "notes": self._note(policy["product"], cause),
        }
        payee = self._payee(policy["product"], cause, spec)
        payments = []
        for day, amount in made:
            load_date = day + timedelta(days=1)  # payments load into the warehouse overnight
            payments.append({
                "payment_id": None,
                "claim": claim,
                "payment_date": day,
                "amount": amount,
                "payee_type": payee,
                "load_batch": f"nightly-{load_date}",
                "_load_date": load_date,
            })
        return claim, payments

    def _report_lag(self, cause: str) -> int:
        median_days, spread = (18, 0.8) if cause in LONG_TAIL_CAUSES else (4, 0.9)
        return int(round(median_days * self.rng.lognormal(0, spread)))

    def _pick_shop(self, policy: dict, report_date: date) -> dict:
        steering = self.steering
        if (
            steering
            and report_date >= steering.start_date
            and (policy["state"], policy["metro"])
            == (steering.shop["state"], steering.shop["metro"])
            and self.rng.random() < steering.steering_share
        ):
            return steering.shop
        shops = self.shops_by_area.get((policy["state"], policy["metro"])) or [
            shop
            for (state, _), group in self.shops_by_area.items()
            if state == policy["state"]
            for shop in group
        ]
        weights = np.array([2.0 if s["network_status"] == "preferred" else 1.0 for s in shops])
        return shops[int(self.rng.choice(len(shops), p=weights / weights.sum()))]

    def _payment_schedule(
        self, cost: float, report_date: date, close_date: date
    ) -> list[tuple[date, float]]:
        """One to three payments, the last one on the closing date."""
        span = (close_date - report_date).days
        count = min(int(self.rng.choice([1, 2, 3], p=[0.6, 0.3, 0.1])), span)
        interim = sorted(
            int(d) for d in self.rng.choice(np.arange(1, span), size=count - 1, replace=False)
        )
        shares = self.rng.dirichlet(np.ones(count))
        amounts = [round(float(cost * share), 2) for share in shares[:-1]]
        amounts.append(round(float(cost) - sum(amounts), 2))
        days = [report_date + timedelta(days=d) for d in interim] + [close_date]
        return list(zip(days, amounts, strict=True))

    def _payee(self, product: str, cause: str, spec: dict) -> str:
        if spec["shop"]:
            return "repair_shop"
        if cause in LONG_TAIL_CAUSES:
            return "claimant"
        if product == "home" and self.rng.random() < 0.3:
            return "contractor"
        return "policyholder"

    def _note(self, product: str, cause: str) -> str | None:
        if self.rng.random() < 0.03:
            return None
        templates = NOTE_TEMPLATES[(product, cause)]
        note = templates[int(self.rng.integers(len(templates)))]
        if self.rng.random() < 0.05:
            note = add_typo(note, self.rng)
        return note


def generate_claims(
    scenario: Scenario,
    policies: list[dict],
    exposure: Exposure,
    factory: ClaimFactory,
    rng: np.random.Generator,
) -> tuple[list[dict], list[dict]]:
    """Draw each month's claims for every state, product and cause from the policies in force."""
    members: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, policy in enumerate(policies):
        members[(policy["state"], policy["product"])].append(i)
    groups = {key: np.array(idx) for key, idx in members.items()}
    # Month-to-month swings shared by every claim type in a state (weather, traffic, economy).
    shocks = {
        state: rng.lognormal(0, 0.06, size=len(exposure.months))
        for state in scenario.policies.state_weights
    }

    claims: list[dict] = []
    payments: list[dict] = []
    for m, month in enumerate(exposure.months):
        month_last_day = min(next_month(month) - timedelta(days=1), scenario.as_of)
        for (state, product), idx in groups.items():
            weights = exposure.in_force[idx, m]
            total = weights.sum()
            if total == 0:
                continue
            region = scenario.region_of_state[state]
            for cause, spec in CAUSES[product].items():
                expected = (
                    total
                    * spec["rate"]
                    * seasonal_factor(cause, region, month.month)
                    * shocks[state][m]
                )
                for i in rng.choice(idx, size=rng.poisson(expected), p=weights / total):
                    policy = policies[i]
                    first = max(month, policy["start_date"])
                    last = min(
                        month_last_day,
                        coverage_end(policy, scenario.as_of) - timedelta(days=1),
                    )
                    span = max((last - first).days, 0)
                    loss_date = first + timedelta(days=int(rng.integers(0, span + 1)))
                    claim, claim_payments = factory.make(policy, cause, loss_date)
                    if claim:
                        claims.append(claim)
                        payments.extend(claim_payments)
    return claims, payments


def assign_ids(claims: list[dict], payments: list[dict]) -> None:
    """Number claims in report order and payments in load order, as a real system would."""
    claims.sort(key=lambda c: (c["report_date"], c["loss_date"], c["policy_id"]))
    for n, claim in enumerate(claims, 1):
        claim["claim_id"] = f"CLM-{n:06d}"
    payments.sort(key=lambda p: (p["_load_date"], p["payment_date"], p["claim"]["claim_id"]))
    for n, payment in enumerate(payments, 1):
        payment["payment_id"] = f"PAY-{n:07d}"
        payment["claim_id"] = payment.pop("claim")["claim_id"]
        del payment["_load_date"]
