"""Build the demo data on first start, for a host that only runs the app.

`make demo` and the Docker image build the data before the app starts. A host such as
Streamlit Community Cloud runs `streamlit run app/main.py` on a fresh copy of the repository,
which has no data, so the app builds it once, on the first visit: both warehouses, then the
policy knowledge base (which downloads a 70 MB embedding model).

It builds only when the claims warehouse is missing. A copy that already has one (a
developer's machine, CI, the Docker image) is left alone, so nothing is rebuilt or downloaded
by surprise.
"""

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE_FILES = ("data/dev.duckdb", "data/dev_restricted.duckdb")
# What to build, as `python -m` arguments, and whether the app can run without it.
STEPS = (
    ("the claims warehouse", ("data.generator", "--scenario", "data/scenarios/dev.yaml"), True),
    ("the held-out test warehouse",
     ("data.generator", "--scenario", "data/scenarios/test.yaml"), False),
    ("the policy knowledge base", ("mcp_servers.policies.build",), False),
)


def data_missing(root: Path = PROJECT_ROOT) -> bool:
    return not all((root / name).exists() for name in WAREHOUSE_FILES)


def build_data(root: Path = PROJECT_ROOT, run: Callable = subprocess.run) -> list[str]:
    """Build the demo data, as `make data` and `make test-data` do. Returns the parts that
    couldn't be built and that the app can run without (their saved answers then show without
    charts or clause text); raises if the claims warehouse itself can't be built."""
    skipped = []
    for name, module, required in STEPS:
        done = run([sys.executable, "-m", *module], cwd=root, capture_output=True, text=True)
        if done.returncode and required:
            raise RuntimeError(f"Couldn't build {name}: {done.stderr.strip()[-500:]}")
        if done.returncode:
            skipped.append(name)
    return skipped
