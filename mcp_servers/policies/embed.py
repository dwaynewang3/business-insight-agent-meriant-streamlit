"""Text embeddings for policy search, in one place so changing the model touches one line.

The model is BAAI/bge-small-en-v1.5 through fastembed: 384 dimensions, runs locally with no
API key, and downloads about 70 MB on first use. Tests use HashEmbedder instead, which needs
no download. Changing the model means rebuilding the knowledge base, since the vector size is
part of the column type.
"""

import hashlib
import os
import re
from pathlib import Path
from typing import Protocol

import numpy as np

MODEL = "BAAI/bge-small-en-v1.5"
DIMENSIONS = 384
# A fixed cache, so every process reuses one download (fastembed defaults to a temp folder).
CACHE_DIR = Path(os.environ.get("FASTEMBED_CACHE_PATH", Path.home() / ".cache" / "fastembed"))


class Embedder(Protocol):
    name: str

    def passages(self, texts: list[str]) -> np.ndarray: ...

    def query(self, text: str) -> np.ndarray: ...


class FastEmbedder:
    """The real model. Loaded on first use (a few seconds)."""

    name = MODEL

    def __init__(self):
        from fastembed import TextEmbedding

        self._model = TextEmbedding(MODEL, cache_dir=str(CACHE_DIR))

    def passages(self, texts: list[str]) -> np.ndarray:
        return _unit(np.array(list(self._model.passage_embed(texts)), dtype=np.float32))

    def query(self, text: str) -> np.ndarray:
        return _unit(np.array(next(self._model.query_embed([text])), dtype=np.float32))


class HashEmbedder:
    """A deterministic stand-in for tests: each word hashed into the same 384 slots, so texts
    that share words are similar. Good enough to test the plumbing, not for retrieval quality."""

    name = "hash-test-embedder"

    def passages(self, texts: list[str]) -> np.ndarray:
        return np.stack([self.query(text) for text in texts])

    def query(self, text: str) -> np.ndarray:
        vector = np.zeros(DIMENSIONS, dtype=np.float32)
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIMENSIONS] += 1.0
        return _unit(vector)


def _unit(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.where(norms == 0, 1, norms)
