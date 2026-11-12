"""Search Meridian's policy knowledge base: hybrid retrieval of clauses in force on a date.

Hybrid means two rankings fused: meaning (cosine similarity of embeddings) and exact words
(BM25 over normalised text, so codes like D-04 and amounts like 5,000 match exactly). Each
keeps its top 30, and reciprocal rank fusion (k = 60) combines them without calibrating
scores. Before ranking, only clauses in force on the relevant date are kept: coverage and
settlement documents go by the incident date, procedures by the decision date
(RAG_PLAN §6). The knowledge base is 252 clauses, so everything runs in memory, exactly.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb
import numpy as np
from py_rust_stemmers import SnowballStemmer

from .build import DEFAULT_PATH
from .embed import Embedder, FastEmbedder
from .ingest import normalise

CANDIDATES = 30  # per ranking, before fusion
RRF_K = 60
XREF_CAP = 4  # extra clauses added by following cross-references

_STEMMER = SnowballStemmer("english")
_STOPWORDS = set("""a an and are as at be but by for from has have if in into is it its of on or
such that the their then there these they this to was were what when where which while who will
with""".split())


def tokens(text: str) -> list[str]:
    """BM25 tokens: normalised, split on anything but letters and digits (digits are kept,
    unlike DuckDB's default full-text rule), stop words dropped, stemmed."""
    return [_STEMMER.stem_word(t) for t in re.split(r"[^a-z0-9]+", normalise(text))
            if t and t not in _STOPWORDS]


@dataclass(frozen=True)
class Clause:
    chunk_id: str
    clause_id: str
    doc_id: str
    version: str
    status: str
    version_basis: str
    effective_from: date
    effective_to: date | None
    claim_types: tuple[str, ...]
    clause_title: str
    exclusion_type: str | None
    text: str
    context_text: str
    review_date: date | None  # the document's next review date

    def in_force(self, coverage_as_of: date, procedure_as_of: date) -> bool:
        as_of = coverage_as_of if self.version_basis == "incident_date" else procedure_as_of
        return self.effective_from <= as_of and (self.effective_to is None
                                                 or as_of < self.effective_to)

    def as_dict(self) -> dict:
        return {"clause_id": self.clause_id, "version": self.version, "status": self.status,
                "effective_from": self.effective_from.isoformat(),
                "effective_to": self.effective_to.isoformat() if self.effective_to else None,
                "document_review_date": self.review_date.isoformat() if self.review_date else None,
                "text": self.context_text}


@dataclass(frozen=True)
class Hit:
    clause: Clause
    score: float
    via: str  # "search" or "cross-reference"


class PolicyLibrary:
    def __init__(self, path: str | Path = DEFAULT_PATH, embedder: Embedder | None = None):
        con = duckdb.connect(str(path), read_only=True)
        try:
            rows = con.execute("""
                SELECT c.chunk_id, c.clause_id, c.doc_id, c.version, c.status, c.version_basis,
                       c.effective_from, c.effective_to, c.applies_to_claim_types,
                       c.clause_title, c.exclusion_type, c.text, c.context_text, c.search_text,
                       c.embedding, d.review_date
                FROM policy_chunks c JOIN policy_documents d USING (doc_id, version)
                ORDER BY c.chunk_id""").fetchall()
            self.xrefs: dict[str, list[str]] = {}
            for source, target in con.execute(
                    "SELECT from_chunk_id, to_clause_id FROM policy_xrefs ORDER BY ALL"
            ).fetchall():
                self.xrefs.setdefault(source, []).append(target)
            model = con.execute("SELECT embedding_model FROM kb_info").fetchone()[0]
        finally:
            con.close()
        self.embedder = embedder or FastEmbedder()
        if self.embedder.name != model:
            raise ValueError(f"The knowledge base was embedded with {model}, not "
                             f"{self.embedder.name}. Rebuild it or use the same model.")
        self.clauses = [Clause(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], tuple(r[8]),
                               r[9], r[10], r[11], r[12], r[15]) for r in rows]
        self.by_clause_id: dict[str, list[Clause]] = {}
        for clause in self.clauses:
            self.by_clause_id.setdefault(clause.clause_id, []).append(clause)
        self.vectors = np.array([r[14] for r in rows], dtype=np.float32)
        self._index_bm25([r[13] for r in rows])

    def _index_bm25(self, search_texts: list[str]) -> None:
        self.term_counts = [Counter(tokens(text)) for text in search_texts]
        self.lengths = np.array([sum(c.values()) for c in self.term_counts], dtype=float)
        n = len(self.term_counts)
        df = Counter(term for counts in self.term_counts for term in counts)
        self.idf = {t: math.log((n - d + 0.5) / (d + 0.5) + 1) for t, d in df.items()}

    def bm25(self, query: str, k1: float = 1.2, b: float = 0.75) -> np.ndarray:
        """BM25 score of every clause for the query; 0 where no query term appears."""
        scores = np.zeros(len(self.clauses))
        average = self.lengths.mean()
        for term in set(tokens(query)):
            if term not in self.idf:
                continue
            tf = np.array([counts.get(term, 0) for counts in self.term_counts], dtype=float)
            scores += self.idf[term] * tf * (k1 + 1) / (tf + k1 * (1 - b + b * self.lengths
                                                                   / average))
        return scores

    def search(self, query: str, coverage_as_of: date, procedure_as_of: date | None = None,
               claim_type: str = "motor", doc_scope: list[str] | None = None, k: int = 8,
               method: str = "hybrid", expand: bool = False) -> list[Hit]:
        """The k best clauses in force on the dates, plus (with expand) up to XREF_CAP more
        that they cross-reference. method is hybrid, vector or bm25 (for the ablation)."""
        procedure_as_of = procedure_as_of or coverage_as_of
        eligible = [i for i, c in enumerate(self.clauses)
                    if claim_type in c.claim_types
                    and (not doc_scope or c.doc_id in doc_scope)
                    and c.in_force(coverage_as_of, procedure_as_of)]
        rankings = []
        if method in ("hybrid", "vector"):
            similarity = self.vectors[eligible] @ self.embedder.query(query)
            rankings.append([eligible[i] for i in np.argsort(-similarity)[:CANDIDATES]])
        if method in ("hybrid", "bm25"):
            scores = self.bm25(query)[eligible]
            order = [i for i in np.argsort(-scores, kind="stable") if scores[i] > 0]
            rankings.append([eligible[i] for i in order[:CANDIDATES]])
        fused: Counter = Counter()
        for ranking in rankings:
            for rank, index in enumerate(ranking, 1):
                fused[index] += 1 / (RRF_K + rank)
        hits = [Hit(self.clauses[i], score, "search") for i, score in fused.most_common(k)]
        if expand:
            hits += self.cross_references(hits, coverage_as_of, procedure_as_of, claim_type)
        return hits

    def cross_references(self, hits: list[Hit], coverage_as_of: date, procedure_as_of: date,
                         claim_type: str = "motor", cap: int = XREF_CAP) -> list[Hit]:
        """One hop: clauses the hits refer to, in force on the same dates, at most cap."""
        have = {h.clause.chunk_id for h in hits}
        extra: list[Hit] = []
        for hit in hits:
            for target in self.xrefs.get(hit.clause.chunk_id, []):
                for clause in self.by_clause_id.get(target, []):
                    if (len(extra) < cap and clause.chunk_id not in have
                            and claim_type in clause.claim_types
                            and clause.in_force(coverage_as_of, procedure_as_of)):
                        extra.append(Hit(clause, 0.0, "cross-reference"))
                        have.add(clause.chunk_id)
        return extra

    def get_clause(self, clause_ref: str, as_of: date | None = None,
                   all_versions: bool = False) -> list[Clause]:
        """A clause by ID, in the version in force on as_of, or every version. Accepts
        POL-AUT-003:4.7, POL-AUT-003 4.7, AUT-003 §4.7, POL-AUT-003 clause 4.7 and DOC-005:A."""
        clause_id = normalise_clause_id(clause_ref)
        versions = sorted(self.by_clause_id.get(clause_id, []), key=lambda c: c.effective_from)
        if all_versions or as_of is None:
            return versions
        return [c for c in versions if c.in_force(as_of, as_of)]


def normalise_clause_id(text: str) -> str:
    match = re.search(r"(?:POL-)?([A-Z]{3})-(\d{3})\s*(?::|§|clause|\s)\s*"
                      r"(\d+\.\d+|[A-Z])\b", text.strip(), re.IGNORECASE)
    if not match:
        raise ValueError(f"{text!r} isn't a clause ID. Use a form like POL-AUT-003:4.7.")
    return f"POL-{match[1].upper()}-{match[2]}:{match[3].upper()}"
