"""Traces: a local JSONL file per session, and the same run in Langfuse when it's set up.

Local traces hold every question, model call, tool call and answer, with the session ID and
each question's run ID, so an answer can be traced to the exact queries and calls behind it.
The eval runner and the UI's saved runs read them.

Langfuse (when LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set) gets one trace per
question, grouped by session, with a generation for each Claude call (tokens, and the cost
our code computed) and a span for each tool call (its input and how many rows came back).
Each approval decision is its own trace in the same session, linked to its question by the
run ID, with a span for each ticket or alert it created.
Query result rows are not sent: they stay in the local trace. The question, the answer's text
and its SQL are sent, with policyholders' names, email addresses and phone numbers masked
first (mcp_servers/warehouse/masking.py), so a fraud team lead's answer that names a
policyholder doesn't leave the machine with the name in it. The local trace keeps the full
text.

A user's rating of an answer (thumbs up or down, with an optional note) is an event in the
session's trace, a line in the feedback file beside the traces folder, and a score on the
question's Langfuse trace. The answers rated down are the ones to review, and where new eval
cases come from.
"""

import json
import os
import time
from collections.abc import Callable
from contextlib import contextmanager, nullcontext
from pathlib import Path

TRACE_DIR = Path("logs/traces")


# The fields of a Langfuse observation that can carry text from a question or an answer.
MASKED_FIELDS = ("input", "output", "metadata", "status_message")


class _NoSpan:
    """Stands in for a Langfuse observation when Langfuse isn't set up."""

    def update(self, **fields) -> None:
        pass


class _Masked:
    """A Langfuse observation whose text is masked before each update is sent."""

    def __init__(self, observation, mask: Callable[[dict], dict]):
        self._observation = observation
        self._mask = mask

    def update(self, **fields) -> None:
        self._observation.update(**self._mask(fields))


def langfuse_client():
    """A Langfuse client if the keys are set, otherwise None."""
    if not (os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")):
        return None
    if os.environ.get("LANGFUSE_TRACING_ENABLED", "true").lower() == "false":
        return None
    from langfuse import Langfuse

    return Langfuse(base_url=os.environ.get("LANGFUSE_BASE_URL") or None)


class Tracer:
    def __init__(self, session_id: str, purpose: str = "dev", directory: Path | None = None,
                 langfuse=None, masker=None):
        """masker: masks text before it goes to Langfuse (a masking.Masker); None sends it
        as it is."""
        self.session_id = session_id
        self.purpose = purpose  # dev, eval or demo: what the spend was for
        self.path = (directory or TRACE_DIR) / f"{session_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.feedback_file = self.path.parent.parent / "feedback.jsonl"
        self.langfuse = langfuse
        self.masker = masker
        self._root = None
        self._trace_ids: dict[str, str] = {}  # each question's Langfuse trace, for its score
        self.listeners: list[Callable[[dict], None]] = []  # such as the UI's live steps

    def event(self, kind: str, **fields) -> dict:
        entry = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": kind,
                 "session_id": self.session_id, **fields}
        with self.path.open("a") as out:
            out.write(json.dumps(entry, default=str) + "\n")
        for listener in self.listeners:
            listener(entry)
        return entry

    def feedback(self, run_id: str, helpful: bool, comment: str | None = None,
                 **fields) -> None:
        """A user's rating of one answer. Rating again adds a line; the last one counts."""
        entry = self.event("feedback", run_id=run_id, helpful=helpful, comment=comment,
                           **fields)
        with self.feedback_file.open("a") as out:
            out.write(json.dumps(entry, default=str) + "\n")
        if self.langfuse is not None and run_id in self._trace_ids:
            comment = self.masker.mask(comment) if self.masker else comment
            self.langfuse.create_score(trace_id=self._trace_ids[run_id], name="user_feedback",
                                       value=int(helpful), data_type="BOOLEAN", comment=comment)
            self.langfuse.flush()

    def masked(self, fields: dict) -> dict:
        """An observation's fields with the text that could carry personal data masked."""
        if self.masker is None:
            return fields
        return {key: self.masker.mask_data(value) if key in MASKED_FIELDS else value
                for key, value in fields.items()}

    def question(self, run_id: str, question: str, role: str, version: str):
        """One Langfuse trace for one question, grouped with the rest of its session."""
        return self.trace("question", run_id, question, role, version, as_type="agent")

    @contextmanager
    def trace(self, name: str, run_id: str, input: object, role: str, version: str,
              as_type: str = "span", metadata: dict | None = None):
        """One Langfuse trace in this session, such as a question or an approval decision.
        Spans opened inside it with span() become its children."""
        if self.langfuse is None:
            yield _NoSpan()
            return
        from langfuse import propagate_attributes

        with propagate_attributes(session_id=self.session_id, user_id=role, version=version,
                                  tags=[self.purpose], trace_name=name,
                                  metadata={"run_id": run_id}):
            with self.langfuse.start_as_current_observation(
                    name=name, as_type=as_type, **self.masked({
                        "input": input,
                        "metadata": {"run_id": run_id, "role": role, **(metadata or {})}})
                    ) as root:
                self._root = root
                if name == "question":
                    self._trace_ids[run_id] = root.trace_id
                try:
                    yield _Masked(root, self.masked)
                finally:
                    self._root = None
        self.langfuse.flush()

    def span(self, name: str, as_type: str = "span", **fields):
        """A child of the current trace, or a stand-in when there's no trace."""
        if self._root is None:
            return nullcontext(_NoSpan())
        return self._masked_span(self._root.start_as_current_observation(
            name=name, as_type=as_type, **self.masked(fields)))

    @contextmanager
    def _masked_span(self, observation):
        with observation as span:
            yield _Masked(span, self.masked)

    def close(self) -> None:
        if self.langfuse is not None:
            self.langfuse.flush()
