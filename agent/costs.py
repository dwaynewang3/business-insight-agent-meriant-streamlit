"""What each Claude call costs, and a spend ledger that stops calls past a set limit.

Cost is computed here from each response's token counts and the model's prices, rather than
taken from a tracing tool's price list, which may not know new models yet. Every call is
appended to logs/spend.jsonl, and `check_spend` refuses a call once the ledger passes the
limit in SPEND_LIMIT_USD (by default US$32, inside the project's A$50 budget).
"""

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

LEDGER = Path("logs/spend.jsonl")
# The whole project must cost less than A$50 (decided 2026-10-18), about US$34.60 at
# US$0.693 to the A$. The ledger stops at US$32, which leaves room for exchange-rate moves
# and anything the ledger misses. DEV_PLAN.md section 10.
DEFAULT_SPEND_LIMIT_USD = 32.0


@dataclass(frozen=True)
class Price:
    """USD per million tokens."""

    input: float
    output: float
    cache_read: float

    @property
    def cache_write(self) -> float:
        return 1.25 * self.input  # 5-minute cache, the default


PRICES = {
    "claude-sonnet-5-5": Price(input=2.0, output=10.0, cache_read=0.20),
    "claude-opus-5-5": Price(input=4.0, output=20.0, cache_read=0.20),
    "claude-haiku-4-5": Price(input=1.0, output=5.0, cache_read=0.10),
    # Server-side fallback targets: a declined Sonnet 5.5 or Opus 5.5 turn may be served by these.
    "claude-sonnet-5": Price(input=2.0, output=10.0, cache_read=0.20),
    "claude-opus-5": Price(input=5.0, output=25.0, cache_read=0.50),
    "claude-opus-4-8": Price(input=5.0, output=25.0, cache_read=0.50),
}
# A model missing from the table is priced like the most expensive one, so cost is never
# under-counted.
UNKNOWN_MODEL_PRICE = Price(input=5.0, output=25.0, cache_read=0.50)


class SpendLimitReached(RuntimeError):
    """The ledger has reached the spend limit, so no more paid calls are made."""


def price_of(model: str) -> Price:
    for name in sorted(PRICES, key=len, reverse=True):  # longest first: sonnet-5-5 before sonnet-5
        if model.startswith(name):
            return PRICES[name]
    return UNKNOWN_MODEL_PRICE


def _tokens_cost(price: Price, tokens: dict) -> float:
    return (
        tokens.get("input_tokens", 0) * price.input
        + tokens.get("output_tokens", 0) * price.output
        + (tokens.get("cache_read_input_tokens") or 0) * price.cache_read
        + (tokens.get("cache_creation_input_tokens") or 0) * price.cache_write
    ) / 1_000_000


def call_cost(model: str, usage: dict) -> float:
    """USD cost of one response, from its usage. A turn served partly by a fallback model is
    priced per iteration, at each model's own prices."""
    iterations = [i for i in usage.get("iterations") or [] if i.get("type") != "compaction"]
    if iterations:
        return sum(_tokens_cost(price_of(i.get("model") or model), i) for i in iterations)
    return _tokens_cost(price_of(model), usage)


def spend_limit() -> float:
    return float(os.environ.get("SPEND_LIMIT_USD", DEFAULT_SPEND_LIMIT_USD))


def spent(ledger: Path | None = None) -> float:
    """Total USD recorded in the ledger."""
    ledger = ledger or LEDGER
    if not ledger.exists():
        return 0.0
    with ledger.open() as lines:
        return sum(json.loads(line)["cost_usd"] for line in lines if line.strip())


def check_spend(ledger: Path | None = None) -> None:
    total, limit = spent(ledger), spend_limit()
    if total >= limit:
        raise SpendLimitReached(
            f"Spent ${total:.2f} of the ${limit:.2f} limit (SPEND_LIMIT_USD). No more paid calls."
        )


def record_spend(entry: dict, ledger: Path | None = None) -> None:
    ledger = ledger or LEDGER
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a") as out:
        out.write(json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%S"), **entry}) + "\n")
