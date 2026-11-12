"""The first-start data build: only on a copy with no warehouse, everything in order, and the
optional parts may fail without stopping the app."""

import sys
from types import SimpleNamespace

import pytest

from app.setup import STEPS, WAREHOUSE_FILES, build_data, data_missing


def test_data_is_built_only_when_the_claims_warehouse_is_missing(tmp_path):
    assert data_missing(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / WAREHOUSE_FILES[0]).touch()
    assert data_missing(tmp_path)  # the copy without personal data is needed too
    (tmp_path / WAREHOUSE_FILES[1]).touch()
    assert not data_missing(tmp_path)
    assert not data_missing()  # this repository has its data, so the app starts at once


def test_the_build_runs_what_make_data_and_make_test_data_run(tmp_path):
    ran = []

    def run(command, **options):
        ran.append((command, options["cwd"]))
        return SimpleNamespace(returncode=0, stderr="")

    assert build_data(tmp_path, run) == []
    assert [command for command, _ in ran] == [
        [sys.executable, "-m", "data.generator", "--scenario", "data/scenarios/dev.yaml"],
        [sys.executable, "-m", "data.generator", "--scenario", "data/scenarios/test.yaml"],
        [sys.executable, "-m", "mcp_servers.policies.build"]]
    assert {cwd for _, cwd in ran} == {tmp_path}
    makefile = open("Makefile").read()  # the same commands as the Makefile's
    for _, module, _ in STEPS:
        assert "uv run python -m " + " ".join(module) in makefile


def test_the_app_can_start_without_the_optional_parts_but_not_without_the_warehouse(tmp_path):
    def fails(part):
        return lambda command, **options: SimpleNamespace(
            returncode=int(part in " ".join(command)), stderr="no network")

    assert build_data(tmp_path, fails("policies")) == ["the policy knowledge base"]
    assert build_data(tmp_path, fails("test.yaml")) == ["the held-out test warehouse"]
    with pytest.raises(RuntimeError, match="the claims warehouse: no network"):
        build_data(tmp_path, fails("dev.yaml"))
