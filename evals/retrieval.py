"""Retrieval eval for the policy knowledge base: does search find the right clauses, in the
right version? No model calls, so it's free (RAG_PLAN §9.2).

    uv run python -m evals.retrieval

For the 32 questions scored for recall it reports, per method (BM25 only, vector only,
hybrid, hybrid plus cross-references), overall and by question type:
- recall@5 and recall@8: the share of each question's expected clauses in the top 5 or 8,
  counting a clause only in the expected version where the question names one;
- version accuracy: on version questions, no clause from the wrong version in the top 8;
- MRR: 1 / the rank of the first expected clause.

Targets (DEV_PLAN Phase 5, B3): hybrid recall@8 >= 0.90, the 5 version questions 5/5,
exact-code recall@5 = 1.0. Misses go to failures.jsonl with a diagnosis: retrieval_miss
(the clause isn't in the results) or wrong_version (a clause from the other version came
back). Results go to evals/results/<time>-policy-retrieval/.
"""

import argparse
import json
import statistics
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

from mcp_servers.policies.search import Hit, PolicyLibrary

QUESTIONS = Path(__file__).parent / "cases" / "compliance" / "retrieval_questions.jsonl"
RESULTS_DIR = Path(__file__).parent / "results"
METHODS = {"bm25": ("bm25", False), "vector": ("vector", False), "hybrid": ("hybrid", False),
           "hybrid+xrefs": ("hybrid", True)}
TARGETS = {"recall@8": 0.90, "version_accuracy": 1.0, "exact_code_recall@5": 1.0}


def load_questions(path: Path = QUESTIONS) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _found(hit: Hit, clause_id: str, versions: dict) -> bool:
    wanted = versions.get(hit.clause.doc_id)
    return hit.clause.clause_id == clause_id and (wanted is None or hit.clause.version == wanted)


def score_question(question: dict, hits: list[Hit]) -> dict:
    expected, versions = question["expected_clause_ids"], question["expected_versions"]

    def recall(k: int) -> float:
        top = hits[:k] if k else hits
        return sum(any(_found(h, c, versions) for h in top) for c in expected) / len(expected)

    ranks = [rank for rank, h in enumerate(hits, 1)
             if any(_found(h, c, versions) for c in expected)]
    wrong_version = [h.clause.chunk_id for h in hits[:8] if h.clause.doc_id in versions
                     and h.clause.version != versions[h.clause.doc_id]]
    return {"recall@5": recall(5), "recall@8": recall(8), "recall@all": recall(0),
            "mrr": 1 / ranks[0] if ranks else 0.0, "wrong_version": wrong_version,
            "missing": [c for c in expected if not any(_found(h, c, versions) for h in hits[:8])]}


def run(library: PolicyLibrary, questions: list[dict]) -> dict:
    scored = [q for q in questions if q["scored_for_recall"]]
    report, failures = {}, []
    for name, (method, expand) in METHODS.items():
        rows = []
        for q in scored:
            day = date.fromisoformat(q["as_of_date"])
            hits = library.search(q["question"], day, day, claim_type=q["claim_type"], k=8,
                                  method=method, expand=expand)
            result = score_question(q, hits)
            rows.append((q, result))
            for clause_id in result["missing"]:
                failures.append({"method": name, "qid": q["qid"], "type": q["type"],
                                 "diagnosis": "retrieval_miss", "expected": clause_id,
                                 "got": [h.clause.chunk_id for h in hits[:8]]})
            if result["wrong_version"]:
                failures.append({"method": name, "qid": q["qid"], "type": q["type"],
                                 "diagnosis": "wrong_version", "got": result["wrong_version"]})
        version_rows = [r for q, r in rows if q["type"] == "version"]
        code_rows = [r for q, r in rows if q["type"] == "exact_code"]
        by_type = defaultdict(list)
        for q, r in rows:
            by_type[q["type"]].append(r["recall@8"])
        report[name] = {
            "recall@5": round(statistics.mean(r["recall@5"] for _, r in rows), 3),
            "recall@8": round(statistics.mean(r["recall@8"] for _, r in rows), 3),
            "mrr": round(statistics.mean(r["mrr"] for _, r in rows), 3),
            "version_questions_right": sum(r["recall@8"] == 1 and not r["wrong_version"]
                                           for r in version_rows),
            "version_questions": len(version_rows),
            "version_accuracy": round(sum(not r["wrong_version"] for r in version_rows)
                                      / len(version_rows), 3),
            "exact_code_recall@5": round(statistics.mean(r["recall@5"] for r in code_rows), 3),
            "recall@8_by_type": {t: round(statistics.mean(v), 3)
                                 for t, v in sorted(by_type.items())},
        }
    return {"questions_scored": len(scored), "methods": report, "failures": failures}


def write(result: dict, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "summary.json").write_text(json.dumps(
        {k: v for k, v in result.items() if k != "failures"}, indent=2))
    (folder / "failures.jsonl").write_text(
        "".join(json.dumps(f) + "\n" for f in result["failures"]))
    methods = result["methods"]
    lines = [f"# Policy retrieval eval ({result['questions_scored']} questions scored for recall)",
             "", "| Method | Recall@5 | Recall@8 | MRR | Version questions | Exact-code recall@5 |",
             "| --- | --- | --- | --- | --- | --- |"]
    for name, m in methods.items():
        lines.append(f"| {name} | {m['recall@5']:.2f} | {m['recall@8']:.2f} | {m['mrr']:.2f} | "
                     f"{m['version_questions_right']}/{m['version_questions']} | "
                     f"{m['exact_code_recall@5']:.2f} |")
    types = sorted(next(iter(methods.values()))["recall@8_by_type"])
    lines += ["", "Recall@8 by question type:", "",
              "| Type | " + " | ".join(methods) + " |", "| --- |" + " --- |" * len(methods)]
    for t in types:
        lines.append(f"| {t} | " + " | ".join(f"{m['recall@8_by_type'][t]:.2f}"
                                               for m in methods.values()) + " |")
    hybrid = methods["hybrid"]
    lines += ["", f"Targets (hybrid): recall@8 >= {TARGETS['recall@8']} "
                  f"({hybrid['recall@8']:.2f}); version questions all right "
                  f"({hybrid['version_questions_right']}/{hybrid['version_questions']}); "
                  f"exact-code recall@5 = 1.0 ({hybrid['exact_code_recall@5']:.2f})."]
    (folder / "summary.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", default="policy-retrieval")
    args = parser.parse_args()
    result = run(PolicyLibrary(), load_questions())
    folder = RESULTS_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}-{args.name}"
    write(result, folder)
    print((folder / "summary.md").read_text())
    print(f"{len(result['failures'])} misses written to {folder / 'failures.jsonl'}")


if __name__ == "__main__":
    main()
