"""Build the policy knowledge base: data/policies.duckdb, derived from the markdown policies.

    uv run python -m mcp_servers.policies.build        (run by `make data`)

The markdown in data/compliance/policies/ is the source of truth; this file is rebuilt from
it every time and never edited by hand. It's kept apart from the claims warehouse, so
run_sql can't read raw clauses and get around the citation rules.
"""

import argparse
from collections import Counter
from pathlib import Path

import duckdb

from .embed import DIMENSIONS, Embedder, FastEmbedder
from .ingest import POLICY_DIR, load_library, normalise, unresolved_references

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "policies.duckdb"

SCHEMA = f"""
CREATE TABLE policy_documents (
  doc_id VARCHAR, version VARCHAR, title VARCHAR, policy_family VARCHAR, status VARCHAR,
  version_basis VARCHAR, effective_from DATE, effective_to DATE, review_date DATE,
  applies_to_claim_types VARCHAR[], owner VARCHAR, source_path VARCHAR,
  PRIMARY KEY (doc_id, version));
CREATE TABLE policy_chunks (
  chunk_id VARCHAR PRIMARY KEY, clause_id VARCHAR, doc_id VARCHAR, version VARCHAR,
  doc_title VARCHAR, section_title VARCHAR, clause VARCHAR, clause_title VARCHAR,
  exclusion_type VARCHAR, policy_family VARCHAR, applies_to_claim_types VARCHAR[],
  status VARCHAR, version_basis VARCHAR, effective_from DATE, effective_to DATE,
  text VARCHAR, context_text VARCHAR, search_text VARCHAR, embedding FLOAT[{DIMENSIONS}]);
CREATE TABLE policy_xrefs (from_chunk_id VARCHAR, to_clause_id VARCHAR);
CREATE TABLE kb_info (embedding_model VARCHAR, chunks INTEGER, built_from VARCHAR);
"""


def build(out_path: Path = DEFAULT_PATH, embedder: Embedder | None = None,
          policy_dir: Path = POLICY_DIR) -> dict:
    """Write the knowledge base and return its counts. Rebuilding replaces the file."""
    chunks = load_library(policy_dir)
    if missing := unresolved_references(chunks):
        raise ValueError(f"Cross-references that don't resolve: {missing}")
    embedder = embedder or FastEmbedder()
    vectors = embedder.passages([c.context_text for c in chunks])

    out_path = Path(out_path)
    for stale in (out_path, out_path.with_name(out_path.name + ".wal")):
        stale.unlink(missing_ok=True)
    con = duckdb.connect(str(out_path))
    try:
        con.execute(SCHEMA)
        documents = {c.document for c in chunks}
        con.executemany(
            "INSERT INTO policy_documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(d.doc_id, d.version, d.title, d.policy_family, d.status, d.version_basis,
              d.effective_from, d.effective_to, d.review_date, list(d.applies_to_claim_types),
              d.owner, d.source_path) for d in sorted(documents, key=lambda d: d.source_path)])
        con.executemany(
            "INSERT INTO policy_chunks VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(c.chunk_id, c.clause_id, c.document.doc_id, c.document.version, c.document.title,
              c.section_title, c.clause, c.clause_title, c.exclusion_type,
              c.document.policy_family, list(c.document.applies_to_claim_types),
              c.document.status, c.document.version_basis, c.document.effective_from,
              c.document.effective_to, c.text, c.context_text, normalise(c.context_text),
              vector.tolist()) for c, vector in zip(chunks, vectors, strict=True)])
        con.executemany("INSERT INTO policy_xrefs VALUES (?, ?)",
                        [(c.chunk_id, ref) for c in chunks for ref in sorted(c.xrefs)])
        con.execute("INSERT INTO kb_info VALUES (?, ?, ?)",
                    [embedder.name, len(chunks), policy_dir.name])
    finally:
        con.close()
    return {
        "chunks": len(chunks),
        "by_document": dict(Counter(c.chunk_id.split(":")[0] for c in chunks)),
        "xrefs": sum(len(c.xrefs) for c in chunks),
        "embedding_model": embedder.name,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    counts = build(args.out)
    print(f"Policy knowledge base: {counts['chunks']} clauses, {counts['xrefs']} cross-references, "
          f"embedded with {counts['embedding_model']} -> {args.out}")
    for doc, n in sorted(counts["by_document"].items()):
        print(f"  {doc:22} {n:4}")


if __name__ == "__main__":
    main()
