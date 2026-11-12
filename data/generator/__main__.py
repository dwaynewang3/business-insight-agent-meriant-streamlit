"""Command line: uv run python -m data.generator --scenario data/scenarios/dev.yaml"""

import argparse
import time
from pathlib import Path

from .build import generate, manifest_path
from .config import load_scenario


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the synthetic insurer warehouse.")
    parser.add_argument("--scenario", default="data/scenarios/dev.yaml")
    parser.add_argument("--out", help="DuckDB file to write (default: data/<scenario>.duckdb)")
    args = parser.parse_args()

    scenario = load_scenario(args.scenario)
    out = Path(args.out or f"data/{scenario.name}.duckdb")
    started = time.perf_counter()
    manifest = generate(scenario, out)
    print(f"Wrote {out} and {manifest_path(out).name} in {time.perf_counter() - started:.1f}s")
    for table, rows in manifest["row_counts"].items():
        print(f"  {table:<18} {rows:>8,}")


if __name__ == "__main__":
    main()
