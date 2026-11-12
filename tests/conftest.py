"""Shared fixtures: build the dev warehouse once per test run."""

import shutil
from pathlib import Path

import duckdb
import pytest

from data.generator import generate
from data.generator.config import load_scenario
from mcp_servers.warehouse.access import restricted_path

DEV_SCENARIO = Path("data/scenarios/dev.yaml")


@pytest.fixture(scope="session")
def scenario():
    return load_scenario(DEV_SCENARIO)


@pytest.fixture(scope="session")
def built(scenario, tmp_path_factory):
    """A read-only connection to the generated warehouse, its manifest, and its file."""
    path = tmp_path_factory.mktemp("warehouse") / "dev.duckdb"
    manifest = generate(scenario, path)
    con = duckdb.connect(str(path), read_only=True)
    yield con, manifest, path
    con.close()


@pytest.fixture(scope="session")
def test_built(tmp_path_factory):
    """The held-out test data's warehouse (data/scenarios/test.yaml): its manifest's incidents
    by id, and the file. A copy without personal data is written next to it."""
    path = tmp_path_factory.mktemp("test_warehouse") / "test.duckdb"
    manifest = generate(load_scenario(Path("data/scenarios/test.yaml")), path)
    return {i["id"]: i for i in manifest["incidents"]}, path


@pytest.fixture(scope="session")
def dev(built):
    """Read-only connection to the generated dev warehouse."""
    return built[0]


@pytest.fixture(scope="session")
def answer_key(built):
    """The manifest's incidents, by id."""
    return {incident["id"]: incident for incident in built[1]["incidents"]}


@pytest.fixture(scope="session")
def guarded_warehouse(built, tmp_path_factory):
    """A copy of the dev warehouse for code that opens it through the SQL guard's locked-down
    connection. DuckDB won't open one file with two different settings in the same process,
    and `built` already holds the original open with default settings."""
    folder = tmp_path_factory.mktemp("guarded_warehouse")
    shutil.copy(built[2], folder / "dev.duckdb")
    shutil.copy(restricted_path(built[2]), folder / "dev_restricted.duckdb")
    return folder / "dev.duckdb"


@pytest.fixture(autouse=True)
def no_langfuse(monkeypatch):
    """Tests never send traces to Langfuse, even if its keys are in the environment."""
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)


@pytest.fixture(scope="session")
def policy_kb(tmp_path_factory):
    """The policy knowledge base, built with the hash test embedder (no model download)."""
    from mcp_servers.policies.build import build
    from mcp_servers.policies.embed import HashEmbedder

    path = tmp_path_factory.mktemp("policies") / "policies.duckdb"
    build(path, HashEmbedder())
    return path


@pytest.fixture(autouse=True)
def test_policy_kb(policy_kb, monkeypatch):
    """Agent sessions in tests use the hash-embedded knowledge base, never the real model."""
    monkeypatch.setenv("POLICY_KB", str(policy_kb))
