"""The policy knowledge base: chunking, cross-references, version filtering and search
(DEV_PLAN Phase 5, step B2). Built with the hash test embedder, so nothing is downloaded."""

from datetime import date

import duckdb
import pytest

from mcp_servers.policies.build import build
from mcp_servers.policies.embed import HashEmbedder
from mcp_servers.policies.ingest import load_library, normalise, unresolved_references
from mcp_servers.policies.search import PolicyLibrary, normalise_clause_id

EXPECTED_COUNTS = {"POL-CLM-001@4.2": 36, "POL-MTR-002@6.0": 42, "POL-MTR-002@5.3": 41,
                   "POL-AUT-003@3.1": 23, "POL-FRD-004@5.1": 25, "POL-DOC-005@2.4": 33,
                   "POL-SLA-006@1.3": 23, "POL-STL-007@3.0": 29}  # the kit's table, 252 in all


@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    path = tmp_path_factory.mktemp("kb") / "policies.duckdb"
    counts = build(path, HashEmbedder())
    return path, counts


@pytest.fixture(scope="module")
def library(kb):
    return PolicyLibrary(kb[0], HashEmbedder())


def test_chunk_counts_match_the_kit_and_every_reference_resolves(kb):
    assert kb[1]["by_document"] == EXPECTED_COUNTS
    assert unresolved_references(load_library()) == []
    assert kb[1]["xrefs"] > 0


def test_superseded_clauses_say_so_in_their_breadcrumb():
    chunk = next(c for c in load_library() if c.chunk_id == "POL-MTR-002@5.3:3.4")
    assert chunk.context_text.startswith(
        "POL-MTR-002 Motor Vehicle Coverage and Exclusions (v5.3, SUPERSEDED: applies to "
        "incidents before 2026-03-01) > 3. Exclusions > 3.4 Unlicensed driving — ABSOLUTE")
    assert chunk.exclusion_type == "ABSOLUTE"


def test_every_clause_is_embedded_and_the_build_can_be_repeated(kb):
    path, counts = kb
    build(path, HashEmbedder())  # rebuilding replaces the file
    with duckdb.connect(str(path), read_only=True) as con:
        assert con.execute("SELECT count(*) FROM policy_chunks").fetchone()[0] == 252
        assert con.execute(
            "SELECT count(*) FROM policy_chunks WHERE embedding IS NULL").fetchone()[0] == 0


def test_bm25_keeps_exact_codes(library):
    """The kit's sanity check: D-04 matches exactly three clauses."""
    scores = library.bm25("D-04")
    matched = {library.clauses[i].clause_id for i, s in enumerate(scores) if s > 0}
    assert matched == {"POL-FRD-004:2.4", "POL-FRD-004:5.1", "POL-DOC-005:8.2"}
    assert normalise("POL-FRD-004 code D-04, AUD 5,000") == "polfrd004 code d04, aud 5000"


@pytest.mark.parametrize("method", ["hybrid", "vector", "bm25"])
def test_only_the_version_in_force_is_returned(library, method):
    question = "driver with an expired licence"
    for day, version in ((date(2026, 2, 10), "5.3"), (date(2026, 6, 16), "6.0")):
        hits = library.search(question, day, day, method=method, k=10)
        motor = {h.clause.version for h in hits if h.clause.doc_id == "POL-MTR-002"}
        assert motor == {version}, (day, method)


def test_procedures_follow_the_decision_date_and_coverage_the_incident_date(library):
    # An incident under v5.3 decided after the change still gets v5.3 motor cover.
    hits = library.search("expired licence exclusion", date(2026, 2, 10), date(2026, 6, 1),
                          k=10, doc_scope=["POL-MTR-002"])
    assert {h.clause.version for h in hits} == {"5.3"}


def test_cross_references_add_at_most_four_clauses_in_force(library):
    day = date(2026, 6, 16)
    hits = library.search("young driver additional excess", day, day, k=6, expand=True)
    extra = [h for h in hits if h.via == "cross-reference"]
    assert len(extra) <= 4
    assert all(h.clause.in_force(day, day) for h in hits)
    assert len({h.clause.chunk_id for h in hits}) == len(hits)


def test_clause_ids_are_understood_in_every_common_form(library):
    for text in ("POL-AUT-003:4.7", "POL-AUT-003 4.7", "AUT-003 §4.7", "POL-AUT-003 clause 4.7"):
        assert normalise_clause_id(text) == "POL-AUT-003:4.7"
    versions = library.get_clause("POL-MTR-002 3.4", all_versions=True)
    assert [c.version for c in versions] == ["5.3", "6.0"]
    assert [c.version for c in library.get_clause("POL-MTR-002:3.4", date(2026, 2, 10))] == ["5.3"]
    assert library.get_clause("POL-DOC-005:A")[0].clause_title
    with pytest.raises(ValueError):
        normalise_clause_id("the excess rule")


def test_a_knowledge_base_built_with_another_model_is_refused(kb):
    class Other(HashEmbedder):
        name = "another-model"

    with pytest.raises(ValueError, match="Rebuild"):
        PolicyLibrary(kb[0], Other())


# The policies MCP server (B3) ---------------------------------------------------------------

def _server(library):
    from mcp_servers.policies.server import build_server

    return build_server(library, date(2026, 9, 30))


def test_the_server_lists_two_strict_read_only_tools(library):
    import asyncio
    import json

    from mcp import Client

    from agent.tools import claude_tool

    async def listing():
        async with Client(_server(library)) as client:
            return (await client.list_tools()).tools

    tools = asyncio.run(listing())
    assert {t.name for t in tools} == {"search_policies", "get_policy_clause"}
    for tool in tools:
        assert tool.annotations.read_only_hint is True
        schema = claude_tool(tool)["input_schema"]
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])
        assert "2026-09-30" in tool.description  # "today" is the extract date
        json.dumps(schema)


def test_search_and_lookup_return_cited_clauses_and_errors_to_the_model(library):
    import json

    from agent.tools import McpToolbox

    toolbox = McpToolbox(_server(library))
    try:
        found = json.loads(toolbox.call("search_policies", {
            "query": "expired licence", "as_of_date": "2026-02-10", "claim_type": "motor",
            "top_k": 3}).content)
        assert found["as_of_date"] == "2026-02-10" and len(found["clauses"]) == 3
        assert {c["version"] for c in found["clauses"] if c["clause_id"].startswith("POL-MTR")} \
            == {"5.3"}
        assert "document_review_date" in found["clauses"][0]
        history = json.loads(toolbox.call("get_policy_clause", {
            "clause_id": "MTR-002 §3.4", "as_of_date": None, "all_versions": True}).content)
        assert [c["version"] for c in history["clauses"]] == ["5.3", "6.0"]
        bad = toolbox.call("get_policy_clause", {"clause_id": "the excess rule",
                                                 "as_of_date": None, "all_versions": False})
        assert bad.is_error and "clause ID" in bad.content
        bad_date = toolbox.call("search_policies", {"query": "excess", "as_of_date": "June",
                                                    "claim_type": "motor", "top_k": 8})
        assert bad_date.is_error and "as_of_date" in bad_date.content
    finally:
        toolbox.close()
