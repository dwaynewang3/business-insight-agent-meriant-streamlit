"""A scripted stand-in for Claude, so agent and eval-runner tests make no API calls."""

import copy
import json

from anthropic.types.beta import BetaMessage

USAGE = {"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 3000,
         "cache_creation_input_tokens": 0}


def reply(*content: dict, stop_reason: str = "end_turn", model: str = "claude-sonnet-5-5",
          usage: dict | None = None) -> BetaMessage:
    return BetaMessage.model_validate({
        "id": "msg_test", "type": "message", "role": "assistant", "model": model,
        "content": list(content), "stop_reason": stop_reason, "stop_sequence": None,
        "usage": usage or USAGE,
    })


def thinking() -> dict:
    return {"type": "thinking", "thinking": "Checking the data.", "signature": "sig"}


def sql_call(sql: str, call_id: str = "tu_1") -> dict:
    return {"type": "tool_use", "id": call_id, "name": "run_sql",
            "input": {"sql": sql, "purpose": "test query"}}


def report(answer_sql: str | None = "SELECT 1 AS x", status: str = "answered",
           actions: list[dict] | None = None) -> dict:
    body = {
        "status": status, "question_type": "what", "interpretation": "How I read it.",
        "answer": "The answer.", "answer_sql": answer_sql, "findings": [], "hypotheses": [],
        "data_quality_issues": [], "charts": [], "proposed_actions": actions or [],
        "open_questions": [],
    }
    return {"type": "text", "text": json.dumps(body)}


class FakeClaude:
    """Plays back scripted responses and keeps a copy of every request."""

    def __init__(self, *script):
        self.script = list(script)
        self.requests: list[dict] = []
        self.beta = self
        self.messages = self

    def create(self, **params):
        self.requests.append(copy.deepcopy(params))
        if not self.script:
            raise AssertionError("The agent made more calls than the script has.")
        return self.script.pop(0)
