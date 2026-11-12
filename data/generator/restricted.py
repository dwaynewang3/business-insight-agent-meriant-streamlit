"""Write the copy of the warehouse that every role except the fraud team lead connects to.

It has every table and row, but no personal-data columns. Which columns those are comes from
the table docs (`pii: true` in data/semantic/tables.yaml), so there's one list to keep current.
"""

from pathlib import Path

import duckdb

from data.semantic.layer import SemanticLayer


def personal_data_columns(layer: SemanticLayer | None = None) -> dict[str, list[str]]:
    layer = layer or SemanticLayer()
    columns = {
        table: [name for name, spec in info["columns"].items() if spec.get("pii")]
        for table, info in layer.tables.items()
    }
    return {table: names for table, names in columns.items() if names}


def write_restricted_copy(full_path: Path, out_path: Path) -> dict[str, list[str]]:
    """Copy every table from full_path to out_path, leaving out personal-data columns.
    Returns the columns left out, by table."""
    removed = personal_data_columns()
    for stale in (out_path, out_path.with_name(out_path.name + ".wal")):
        stale.unlink(missing_ok=True)
    con = duckdb.connect(str(out_path))
    try:
        con.execute(f"ATTACH '{full_path.as_posix()}' AS full_warehouse (READ_ONLY)")
        tables = [row[0] for row in con.execute(
            "SELECT table_name FROM duckdb_tables() WHERE database_name = 'full_warehouse' "
            "ORDER BY table_name"
        ).fetchall()]
        for table in tables:
            exclude = removed.get(table)
            columns = f"* EXCLUDE ({', '.join(exclude)})" if exclude else "*"
            con.execute(f"CREATE TABLE {table} AS SELECT {columns} FROM full_warehouse.{table}")
        con.execute("DETACH full_warehouse")
    finally:
        con.close()
    return removed
