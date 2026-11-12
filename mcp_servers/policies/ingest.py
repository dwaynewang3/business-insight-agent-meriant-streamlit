"""Turn Meridian's policy library (data/compliance/policies/*.md) into clause-sized chunks.

One clause (a `### N.M` heading) is one chunk, so the unit retrieved is the unit cited. Each
chunk carries a breadcrumb (document, version, section, clause) in front of its text, which
is what gets embedded and shown to the model. Cross-references between clauses are stored so
search can follow them one hop. The rules are the kit's (docs/compliance/kit/RAG_PLAN.md §4).
"""

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

POLICY_DIR = Path(__file__).resolve().parents[2] / "data" / "compliance" / "policies"

_DOC_ID = r"POL-[A-Z]{3}-\d{3}"
_CLAUSE = r"\d+\.\d+"


@dataclass(frozen=True)
class Document:
    doc_id: str
    version: str
    title: str
    policy_family: str
    status: str
    version_basis: str  # incident_date or action_date
    effective_from: date
    effective_to: date | None  # exclusive; None while current
    review_date: date | None
    applies_to_claim_types: tuple[str, ...]
    owner: str
    source_path: str


@dataclass
class Chunk:
    document: Document
    section_title: str
    clause: str  # "3.4", or "A" for an appendix
    clause_title: str
    text: str
    xrefs: set[str] = field(default_factory=set)  # clause ids it refers to

    @property
    def clause_id(self) -> str:  # shared across versions: POL-MTR-002:3.4
        return f"{self.document.doc_id}:{self.clause}"

    @property
    def chunk_id(self) -> str:  # unique: POL-MTR-002@5.3:3.4
        return f"{self.document.doc_id}@{self.document.version}:{self.clause}"

    @property
    def exclusion_type(self) -> str | None:
        match = re.search(r"—\s*(ABSOLUTE|REBUTTABLE)\s*$", self.clause_title)
        return match[1] if match else None

    @property
    def breadcrumb(self) -> str:
        doc = self.document
        version = f"v{doc.version}"
        if doc.status == "superseded":
            version += (f", SUPERSEDED: applies to {_basis_noun(doc)} before "
                        f"{doc.effective_to.isoformat()}")
        head = f"{doc.doc_id} {doc.title} ({version}) > {self.section_title}"
        if self.section_title.startswith("Appendix"):
            return head  # an appendix is one chunk; its section title names it
        return f"{head} > {self.clause} {self.clause_title}"

    @property
    def context_text(self) -> str:
        return f"{self.breadcrumb}\n{self.text}"


def _basis_noun(doc: Document) -> str:
    return "incidents" if doc.version_basis == "incident_date" else "decisions"


def normalise(text: str) -> str:
    """Make exact codes searchable: POL-MTR-002 -> polmtr002, D-04 -> d04, 5,000 -> 5000.
    Applied to both the indexed text and the query (RAG_PLAN §4.3)."""
    text = re.sub(r"POL-([A-Z]{3})-(\d{3})", lambda m: f"pol{m[1]}{m[2]}", text)
    text = re.sub(r"\b([A-Z]{1,3})-(\d{2})\b", r"\1\2", text)
    text = re.sub(r"(\d),(\d{3})\b", r"\1\2", text)
    return text.lower()


def _references(text: str, own_doc: str) -> set[str]:
    """Clause-level references in a clause's text, as clause ids. Section references
    ("section 3") aren't kept: they'd expand to up to 18 clauses."""
    refs: set[str] = set()
    # "POL-XXX-NNN clause(s) N.M ...", "clause(s) N.M ..." (same document), and table cells
    # written "POL-XXX-NNN N.M".
    pattern = re.compile(
        rf"(?:(?P<doc>{_DOC_ID})\s+)?(?:(?P<word>clauses?)\s+)?"
        rf"(?P<first>{_CLAUSE})(?:\([a-z]\))?"
        rf"(?:\s+(?P<joiner>and|or|to)\s+(?P<second>{_CLAUSE}))?")
    for match in pattern.finditer(text):
        if not (match["doc"] or match["word"]):
            continue  # a bare number, such as an amount or a version
        doc = match["doc"] or own_doc
        clauses = [match["first"]]
        if match["second"]:
            if match["joiner"] == "to":
                clauses += _between(match["first"], match["second"])
            clauses.append(match["second"])
        refs |= {f"{doc}:{clause}" for clause in clauses}
    return refs


def _between(first: str, last: str) -> list[str]:
    """Clause numbers strictly between two in the same section: 3.1 to 3.4 -> 3.2, 3.3."""
    (s1, c1), (s2, c2) = (map(int, first.split(".")), map(int, last.split(".")))
    return [f"{s1}.{n}" for n in range(c1 + 1, c2)] if s1 == s2 else []


def parse(path: Path) -> list[Chunk]:
    raw = path.read_text()
    front, body = raw.split("\n---\n", 1) if raw.startswith("---") else ("", raw)
    meta = yaml.safe_load(front.removeprefix("---"))
    doc = Document(
        doc_id=meta["doc_id"],
        version=str(meta["version"]),
        title=meta["title"],
        policy_family=meta.get("policy_family", ""),
        status=meta["status"],
        version_basis=meta["version_basis"],
        effective_from=meta["effective_from"],
        effective_to=meta.get("effective_to"),
        review_date=meta.get("review_date"),
        applies_to_claim_types=tuple(meta.get("applies_to_claim_types") or ()),
        owner=meta.get("owner", ""),
        source_path=path.name,
    )
    chunks: list[Chunk] = []
    section, current, lines = "", None, []

    def close() -> None:
        if current is not None:
            text = "\n".join(lines).strip()
            text = re.sub(r"(\n\s*---\s*)+$", "", text).strip()
            current.text = text
            current.xrefs = {r for r in _references(text, doc.doc_id) if r != current.clause_id}
            chunks.append(current)

    appendix_has_children = False
    for line in body.splitlines():
        if line.startswith("### "):
            close()
            heading = line[4:].strip()
            number, _, title = heading.partition(" ")
            current, lines = Chunk(doc, section, number, title.strip(), ""), []
            appendix_has_children = appendix_has_children or section.startswith("Appendix")
        elif line.startswith("## "):
            close()
            section, current, lines = line[3:].strip(), None, []
            appendix = re.match(r"Appendix ([A-Z])\b\s*[—-]?\s*(.*)", section)
            if appendix:  # an appendix without ### children is one chunk (clause "A")
                current = Chunk(doc, section, appendix[1], appendix[2].strip() or section, "")
        elif line.startswith("# ") or line.startswith(">"):
            continue  # the title and the superseded notice live in the breadcrumb
        elif current is not None:
            lines.append(line)
    close()
    return chunks


def load_library(directory: Path = POLICY_DIR) -> list[Chunk]:
    chunks = [c for path in sorted(directory.glob("*.md")) for c in parse(path)]
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), "clause numbers must be unique within a document version"
    return chunks


def unresolved_references(chunks: list[Chunk]) -> list[tuple[str, str]]:
    known = {c.clause_id for c in chunks}
    return sorted((c.chunk_id, ref) for c in chunks for ref in c.xrefs if ref not in known)
