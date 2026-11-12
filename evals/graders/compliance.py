"""Grade compliance reviews against the expected verdicts (RAG_PLAN §9.3), in code.

Matching is by clause, not by check name: an expected finding is detected if some predicted
BREACH cites at least one clause in its `must_cite_any` or `also_acceptable`. Where the
expected finding gives a version, a cited clause of the coverage document (POL-MTR-002) counts
only in that version. One predicted finding can detect several expected ones. Agreement on the
check name is reported separately, since single-call variants choose their own labels.

Per claim, misses get a diagnosis (RAG_PLAN §9.6):
- retrieval_miss: no acceptable clause for the finding was retrieved;
- wrong_version: an acceptable clause was retrieved, but only in the wrong version;
- validator_reject: the review cited a clause it wasn't given;
- judge_error: the clauses were there and the judgement was still wrong.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

CASES = Path(__file__).resolve().parent.parent / "cases" / "compliance"


@dataclass(frozen=True)
class ComplianceCase:
    claim_id: str
    expected: dict
    held_out: bool


def load_compliance_cases(split: str = "dev") -> list[ComplianceCase]:
    """The claim files in a split: dev (18), held_out (9) or all (27)."""
    held_out = set(yaml.safe_load((CASES / "split.yaml").read_text())["held_out"])
    cases = [ComplianceCase(e["claim_id"], e, e["claim_id"] in held_out)
             for e in map(json.loads, (CASES / "expected_verdicts.jsonl").read_text().splitlines())]
    if split == "all":
        return cases
    if split not in ("dev", "held_out"):
        raise ValueError(f"split must be dev, held_out or all, not {split!r}.")
    return [c for c in cases if c.held_out == (split == "held_out")]


def _coverage_doc(expected: dict) -> str:
    return expected.get("coverage_version", "POL-MTR-002@").split("@")[0]


def _cites(finding: dict, wanted: set[str], version: str | None, coverage_doc: str) -> bool:
    for clause in finding.get("clauses") or [{"clause_id": c, "version": None}
                                             for c in finding.get("clause_ids", [])]:
        if clause["clause_id"] not in wanted:
            continue
        if version and clause["clause_id"].startswith(coverage_doc + ":") \
                and clause["version"] != version:
            continue
        return True
    return False


def detected_by(expected_finding: dict, predicted: list[dict], coverage_doc: str,
                strict: bool = False) -> list[int]:
    """Indexes of the predicted BREACH findings that detect this expected finding (with
    strict, only those citing a must_cite_any clause)."""
    wanted = set(expected_finding["must_cite_any"])
    if not strict:
        wanted |= set(expected_finding.get("also_acceptable", []))
    return [i for i, f in enumerate(predicted) if f["status"] == "BREACH"
            and _cites(f, wanted, expected_finding.get("version"), coverage_doc)]


def _diagnose(expected_finding: dict, review: dict, coverage_doc: str) -> str:
    wanted = set(expected_finding["must_cite_any"]) | set(expected_finding["also_acceptable"])
    retrieved = [_chunk(chunk) for chunks in review.get("retrieved", {}).values()
                 for chunk in chunks]
    found = [(clause_id, version) for clause_id, version in retrieved if clause_id in wanted]
    if not found:
        return "retrieval_miss"
    wanted_version = expected_finding.get("version")
    if wanted_version and all(clause_id.startswith(coverage_doc + ":") and version != wanted_version
                              for clause_id, version in found):
        return "wrong_version"
    if review.get("validation") and any("wasn't given" in p for v in review["validation"]
                                        for p in v["problems"]):
        return "validator_reject"
    return "judge_error"


def _chunk(chunk_id: str) -> tuple[str, str]:
    """POL-MTR-002@6.0:3.4 -> (POL-MTR-002:3.4, 6.0)."""
    doc_version, clause = chunk_id.split(":", 1)
    doc, version = doc_version.split("@")
    return f"{doc}:{clause}", version


def grade(case: ComplianceCase, review: dict, known_clauses: set[str] | None = None) -> dict:
    """One claim's grade: verdict, findings detected, false breaches, and a diagnosis for
    each miss. A review with no verdict (an error) is graded as all wrong, counted apart.
    Citations of clauses not in the knowledge base (known_clauses) count as invented; ones
    that exist but weren't supplied to the judge count as unsupplied."""
    expected = case.expected
    predicted = review.get("findings") or []
    coverage_doc = _coverage_doc(expected)
    required, optional = expected["required_findings"], expected["optional_findings"]
    grade = {"claim_id": case.claim_id, "held_out": case.held_out,
             "expected_overall": expected["expected_overall"], "overall": review.get("overall"),
             "overall_correct": review.get("overall") == expected["expected_overall"],
             "trap_or_control": expected["expected_overall"] == "COMPLIANT",
             "error": review.get("error"), "required": len(required), "detected": 0,
             "strict_citations": 0, "check_name_agrees": 0, "false_breaches": 0,
             "invented_citations": 0, "unsupplied_citations": 0, "pass_grounding": [],
             "misses": []}
    if review.get("error"):  # no verdict: counted as an error, not diagnosed as misses
        return grade
    used: set[int] = set()
    for exp in required:
        hits = detected_by(exp, predicted, coverage_doc)
        if hits:
            grade["detected"] += 1
            grade["strict_citations"] += bool(detected_by(exp, predicted, coverage_doc, True))
            grade["check_name_agrees"] += any(predicted[i]["check"] == exp["check"] for i in hits)
        else:
            grade["misses"].append({"check": exp["check"], "expected": exp["must_cite_any"],
                                    "diagnosis": _diagnose(exp, review, coverage_doc)})
        used.update(hits)
    for exp in optional:
        used.update(detected_by(exp, predicted, coverage_doc))
    grade["false_breaches"] = sum(1 for i, f in enumerate(predicted)
                                  if f["status"] == "BREACH" and i not in used)
    cited = [c for f in predicted for c in f.get("clauses", [])]
    grade["unsupplied_citations"] = sum(1 for c in cited if c["version"] is None)
    if known_clauses is not None:
        grade["invented_citations"] = sum(1 for c in cited if c["clause_id"] not in known_clauses)
    passes = expected.get("expected_passes", [])
    grade["pass_grounding"] = [
        any(f["status"] == "PASS" and _cites(f, set(p["must_cite_any"]) | set(p["also_acceptable"]),
                                             None, coverage_doc) for f in predicted)
        for p in passes]
    if not grade["overall_correct"] and not grade["misses"] and grade["false_breaches"]:
        grade["misses"].append({"check": None, "expected": "COMPLIANT",
                                "diagnosis": "judge_error"})
    return grade


def summarise(grades: list[dict]) -> dict:
    """Totals for a set of grades (one run), as the kit's metrics."""
    detected = sum(g["detected"] for g in grades)
    return {
        "claims": len(grades),
        "overall_correct": sum(g["overall_correct"] for g in grades),
        "errors": sum(1 for g in grades if g["error"]),
        "required_findings": sum(g["required"] for g in grades),
        "required_detected": detected,
        "strict_citation_rate": round(sum(g["strict_citations"] for g in grades) / detected, 3)
        if detected else None,
        "check_name_agreement": round(sum(g["check_name_agrees"] for g in grades) / detected, 3)
        if detected else None,
        "false_breaches": sum(g["false_breaches"] for g in grades),
        "traps_and_controls_right": sum(g["overall_correct"] for g in grades
                                        if g["trap_or_control"]),
        "traps_and_controls": sum(g["trap_or_control"] for g in grades),
        "invented_citations": sum(g["invented_citations"] for g in grades),
        "unsupplied_citations": sum(g["unsupplied_citations"] for g in grades),
        "pass_grounding": f"{sum(sum(g['pass_grounding']) for g in grades)}/"
                          f"{sum(len(g['pass_grounding']) for g in grades)}",
    }


def reference_review(case: ComplianceCase) -> dict:
    """The expected verdict as a review, for checking the grader before any paid run: it
    must score 100%, and an empty review must not."""
    exp = case.expected
    findings = [{"check": f["check"], "status": "BREACH", "severity": f["severity"],
                 "clause_ids": f["must_cite_any"][:1],
                 "clauses": [{"clause_id": f["must_cite_any"][0],
                              "version": f.get("version") or "as supplied"}]}
                for f in exp["required_findings"]]
    return {"overall": exp["expected_overall"], "findings": findings, "retrieved": {}}
