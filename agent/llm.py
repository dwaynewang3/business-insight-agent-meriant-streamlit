"""One call to Claude, with the settings from DEV_PLAN.md section 11, its cost and the model
that served it.

- Adaptive thinking at an explicit effort (medium by default), with reasoning summaries kept
  for the transcripts.
- The final report as a structured output, in the same request as the tools.
- Prompt caching in two places: a fixed breakpoint after the system prompt, so every session
  and eval case reuses the tools and system prompt, and automatic caching for the growing
  conversation, so each step of a question reuses the steps before it.
- Server-side fallback ("default"): a declined turn may be served by another model, which is
  recorded so the eval runner can flag it.
"""

import time
from dataclasses import dataclass

import anthropic

from .costs import call_cost, check_spend, record_spend
from .report import OUTPUT_FORMAT

FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass(frozen=True)
class ModelSettings:
    model: str = "claude-sonnet-5-5"
    effort: str = "medium"
    max_tokens: int = 16_000
    thinking_display: str = "summarized"  # keeps reasoning summaries for the transcripts
    thinking_budget: int = 4_000  # Haiku 4.5 only: it has no effort setting


def request_params(
    settings: ModelSettings, system: str, tools: list[dict], messages: list[dict],
    output_format: dict = OUTPUT_FORMAT, cache_conversation: bool = True,
) -> dict:
    """The request for one call. The output format is the agent's report unless another is
    given (the compliance judge's verdict); a call with no tools leaves the field out.
    cache_conversation adds the automatic breakpoint at the end of the conversation, which a
    one-off call (a compliance check) doesn't want: its last part is never reused, so caching
    it only adds the cache-write premium."""
    params = {
        "model": settings.model,
        "max_tokens": settings.max_tokens,
        "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        "messages": messages,
    }
    if cache_conversation:
        params["cache_control"] = {"type": "ephemeral"}
    if tools:
        params["tools"] = tools
    if settings.model.startswith("claude-haiku-4-5"):
        # Haiku 4.5 (Experiment 2) has no effort setting and takes a fixed thinking budget, and
        # server-side fallback isn't offered for it.
        params["thinking"] = {"type": "enabled", "budget_tokens": settings.thinking_budget}
        params["output_config"] = {"format": output_format}
        return params
    params["thinking"] = {"type": "adaptive", "display": settings.thinking_display}
    params["output_config"] = {"effort": settings.effort, "format": output_format}
    params["fallbacks"] = "default"
    params["betas"] = [FALLBACK_BETA]
    return params


def call_claude(client: anthropic.Anthropic, params: dict, labels: dict) -> tuple[object, dict]:
    """Send one request. Returns the response and a record of its usage, cost and model.

    Raises SpendLimitReached before sending if the spend ledger is at its limit. API errors
    are raised for the caller to handle; the SDK has already retried the transient ones.
    """
    check_spend()
    started = time.perf_counter()
    message = client.beta.messages.create(**params)
    return message, usage_record(params, message, labels,
                                 round(time.perf_counter() - started, 2))


def usage_record(params: dict, message, labels: dict, seconds: float,
                 batch: bool = False) -> dict:
    """A response's usage, cost and model, also written to the spend ledger. Batch results
    cost half (the Batch API's discount)."""
    usage = message.usage.to_dict(mode="json")
    cost = call_cost(params["model"], usage) * (0.5 if batch else 1)
    fallback_models = [
        block.to.model for block in message.content if getattr(block, "type", "") == "fallback"
    ]
    record = {
        **labels,
        "model_requested": params["model"],
        "model_served": message.model,
        "fallback": bool(fallback_models) or not message.model.startswith(params["model"]),
        "stop_reason": message.stop_reason,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens") or 0,
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens") or 0,
        "cost_usd": round(cost, 6),
        "seconds": seconds,
        "request_id": getattr(message, "_request_id", None),
        "batch": batch,
    }
    record_spend({k: record[k] for k in (*labels, "model_served", "cost_usd")})
    return record


def run_batch(client: anthropic.Anthropic, requests: list[dict], poll_seconds: float = 15,
              timeout: float = 3 * 3600) -> tuple[str, dict]:
    """Send requests ({"custom_id", "params"}) through the Message Batches API and wait for
    them. Returns the batch ID and, by custom_id, each message or the reason it failed.
    Batch requests can't use beta features, so the params must not need any."""
    check_spend()
    batch = client.messages.batches.create(requests=requests)
    print(f"Submitted batch {batch.id} ({len(requests)} requests).", flush=True)
    waited = 0.0
    while client.messages.batches.retrieve(batch.id).processing_status != "ended":
        if waited >= timeout:
            raise TimeoutError(f"Batch {batch.id} didn't finish in {timeout:g} seconds.")
        time.sleep(poll_seconds)
        waited += poll_seconds
    results = {}
    for item in client.messages.batches.results(batch.id):
        results[item.custom_id] = (item.result.message if item.result.type == "succeeded"
                                   else f"batch request {item.result.type}")
    return batch.id, results
