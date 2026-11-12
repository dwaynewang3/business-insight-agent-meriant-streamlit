"""Find the policy citations in a report's text, and check them against what the policy tools
actually returned.

The agent cites clauses inline, as (POL-AUT-003 §2.1, v3.1). Code reads them from the text the
user sees (the answer, findings and hypotheses), so the check covers exactly what's shown, and
the structured report doesn't need a citations field (one pushed the request past the API's
size limit for strict schemas, 2026-10-17). A citation counts only if a tool returned that
clause, in that version, while the question was being answered: a policy tool, a compliance
review, or a query of the recorded findings (compliance_findings), which name clauses as
POL-AUT-003:2.1 v3.1.
"""

import re

_DOC = re.compile(r"POL-[A-Z]{3}-\d{3}")
# After a document ID: clause references, separators, and versions. A version applies to the
# references before it, or, written straight after the document ID, to those after it.
# Anything else ends the citation.
_TOKEN = re.compile(
    r"\s*(?:(?P<sep>,|and\b|\((?=\s*§))"
    r"|(?P<ref>(?:§\s*|:|clause\s+)?(?:\d+\.\d+|Appendix\s+[A-Z]\b))(?:\([a-z]\))?"
    r"|(?:§\s*|:)(?P<letter>[A-Z])\b"
    r"|\(?\s*v(?P<ver>\d+\.\d+)\)?)")


def citations_in(text: str) -> list[tuple[str, str | None]]:
    """The (clause_id, version) pairs cited in text. Reads single citations, such as
    (POL-AUT-003 §2.1, v3.1) or POL-STL-007:3.4, and lists, such as POL-MTR-002 §3.1 and
    §3.2 (v6.0) and §3.4 (v5.3), where a version covers the references before it, or
    POL-AUT-003 v3.1 (§1.2, §2.1), where it covers those after it."""
    found = []
    for doc in _DOC.finditer(text):
        position, pending, leading, closed = doc.end(), [], None, False
        while (token := _TOKEN.match(text, position)) and token.end() > position:
            position = token.end()
            if token["ref"] or token["letter"]:
                clause = token["letter"] or re.sub(r"^(?:§|:|clause|Appendix)\s*", "",
                                                   token["ref"].strip())
                pending.append(f"{doc.group()}:{clause.replace('Appendix', '').strip()}")
            elif token["ver"] and pending:
                found += [(clause_id, token["ver"]) for clause_id in pending]
                pending, closed = [], True
            elif token["ver"] and not closed:
                leading = token["ver"]
        found += [(clause_id, leading) for clause_id in pending]
    return found


def extract_citations(report: dict | None) -> list[dict]:
    """Every distinct clause cited in the report's text, with its version if one is given."""
    found: dict[tuple[str, str | None], dict] = {}
    for text in _texts(report or {}):
        for key in citations_in(text):
            found.setdefault(key, {"clause_id": key[0], "version": key[1]})
    return list(found.values())


def _texts(report: dict) -> list[str]:
    texts = [report.get("answer") or "", report.get("interpretation") or ""]
    texts += [f.get("claim", "") for f in report.get("findings") or []]
    texts += [f"{h.get('hypothesis', '')} {h.get('evidence', '')}"
              for h in report.get("hypotheses") or []]
    return texts


def returned_clauses(tool_calls: list[dict]) -> set[tuple[str, str]]:
    """Every (clause_id, version) a tool returned in this answer: the policy tools' clauses,
    a compliance review's, and the clauses named in query results from the recorded
    compliance findings."""
    return {(clause_id, version) for call in tool_calls
            for clause_id, version in call.get("clauses", [])}


def is_returned(citation: dict, returned: set[tuple[str, str]]) -> bool:
    """A versioned citation must match exactly; one without a version matches any version."""
    if citation["version"]:
        return (citation["clause_id"], citation["version"]) in returned
    return any(clause_id == citation["clause_id"] for clause_id, _ in returned)


def check_citations(report: dict | None, tool_calls: list[dict]) -> dict:
    """How many of the report's citations a tool returned, and which ones it didn't."""
    citations = extract_citations(report)
    returned = returned_clauses(tool_calls)
    unchecked = [c for c in citations if not is_returned(c, returned)]
    return {"cited": len(citations), "confirmed": len(citations) - len(unchecked),
            "without_version": sum(1 for c in citations if not c["version"]),
            "unconfirmed": unchecked}
