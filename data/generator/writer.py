"""Write the generated tables to a DuckDB file."""

import csv
import tempfile
from datetime import date
from pathlib import Path

import duckdb

# Column names and types for each table, in order.
SCHEMAS: dict[str, list[tuple[str, str]]] = {
    "warehouse_info": [
        ("extract_date", "DATE"),
        ("data_start", "DATE"),
        ("data_end", "DATE"),
    ],
    "policyholders": [
        ("policyholder_id", "VARCHAR PRIMARY KEY"),
        ("full_name", "VARCHAR"),
        ("email", "VARCHAR"),
        ("state", "VARCHAR"),
        ("postcode", "VARCHAR"),
        ("age_band", "VARCHAR"),
        ("customer_since", "DATE"),
    ],
    "policies": [
        ("policy_id", "VARCHAR PRIMARY KEY"),
        ("policyholder_id", "VARCHAR"),
        ("product", "VARCHAR"),
        ("state", "VARCHAR"),
        ("region", "VARCHAR"),
        ("metro", "VARCHAR"),
        ("postcode", "VARCHAR"),
        ("channel", "VARCHAR"),
        ("start_date", "DATE"),
        ("end_date", "DATE"),
        ("annual_premium", "DECIMAL(10,2)"),
        ("excess", "INTEGER"),
    ],
    "exposure_monthly": [
        ("month", "DATE"),
        ("state", "VARCHAR"),
        ("region", "VARCHAR"),
        ("product", "VARCHAR"),
        ("policies_in_force", "DECIMAL(12,2)"),
        ("earned_premium", "DECIMAL(14,2)"),
    ],
    "claims": [
        ("claim_id", "VARCHAR PRIMARY KEY"),
        ("policy_id", "VARCHAR"),
        ("product", "VARCHAR"),
        ("cause", "VARCHAR"),
        ("state", "VARCHAR"),
        ("region", "VARCHAR"),
        ("postcode", "VARCHAR"),
        ("loss_date", "DATE"),
        ("report_date", "DATE"),
        ("status", "VARCHAR"),
        ("adjuster_id", "VARCHAR"),
        ("repair_shop_id", "VARCHAR"),
        ("reserve_amount", "DECIMAL(12,2)"),
        ("close_date", "DATE"),
        ("notes", "VARCHAR"),
    ],
    "claim_payments": [
        ("payment_id", "VARCHAR PRIMARY KEY"),
        ("claim_id", "VARCHAR"),
        ("payment_date", "DATE"),
        ("amount", "DECIMAL(12,2)"),
        ("payee_type", "VARCHAR"),
        ("load_batch", "VARCHAR"),
    ],
    "adjusters": [
        ("adjuster_id", "VARCHAR PRIMARY KEY"),
        ("full_name", "VARCHAR"),
        ("region", "VARCHAR"),
        ("team", "VARCHAR"),
        ("hire_date", "DATE"),
        ("leave_date", "DATE"),
    ],
    "repair_shops": [
        ("repair_shop_id", "VARCHAR PRIMARY KEY"),
        ("name", "VARCHAR"),
        ("state", "VARCHAR"),
        ("metro", "VARCHAR"),
        ("network_status", "VARCHAR"),
    ],
    "weather_events": [
        ("event_id", "VARCHAR PRIMARY KEY"),
        ("state", "VARCHAR"),
        ("area", "VARCHAR"),
        ("event_type", "VARCHAR"),
        ("start_date", "DATE"),
        ("end_date", "DATE"),
        ("severity", "VARCHAR"),
    ],
}


def _cell(value) -> str:
    if value is None:
        return ""  # loaded as NULL
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def write_warehouse(tables: dict[str, list[dict]], out_path: Path) -> None:
    """Create a fresh DuckDB file with every table, loading rows through CSV for speed."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    for stale in (out_path, out_path.with_name(out_path.name + ".wal")):
        stale.unlink(missing_ok=True)

    con = duckdb.connect(str(out_path))
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for table, columns in SCHEMAS.items():
                column_sql = ", ".join(f"{name} {kind}" for name, kind in columns)
                con.execute(f"CREATE TABLE {table} ({column_sql})")
                rows = tables.get(table, [])
                if not rows:
                    continue
                csv_path = Path(tmp) / f"{table}.csv"
                with csv_path.open("w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(name for name, _ in columns)
                    writer.writerows([_cell(row[name]) for name, _ in columns] for row in rows)
                con.execute(f"COPY {table} FROM '{csv_path.as_posix()}' (HEADER)")
    finally:
        con.close()
