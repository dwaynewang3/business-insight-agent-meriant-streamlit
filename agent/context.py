"""What the model is told: the system prompt, and each session's context.

The system prompt is the same for every user and every question (the instructions, the table
docs and the glossary), so the prompt cache can reuse it. Anything that varies, such as the
user's role and the warehouse's extract date, goes in the session's first user message.

The Phase 1 agent gets the table docs and the glossary but not the agreed metric definitions,
which is the "semantic layer off" arm of Experiment 1. Phase 2 adds the metric tools.
"""

import hashlib
import json
from pathlib import Path

from data.semantic.layer import SemanticLayer
from mcp_servers.warehouse import connect
from mcp_servers.warehouse.access import ROLES

PROMPTS_DIR = Path(__file__).parent / "prompts"


def column_types(db_path: str | Path) -> dict[str, dict[str, str]]:
    """table -> column -> DuckDB type, read from the warehouse."""
    con = connect(db_path)
    try:
        rows = con.execute(
            "SELECT table_name, column_name, data_type FROM information_schema.columns "
            "ORDER BY table_name, ordinal_position"
        ).fetchall()
    finally:
        con.close()
    types: dict[str, dict[str, str]] = {}
    for table, column, data_type in rows:
        types.setdefault(table, {})[column] = data_type
    return types


def describe_tables(layer: SemanticLayer, types: dict[str, dict[str, str]]) -> str:
    """The table docs as Markdown, with each column's type and access notes."""
    parts = []
    for name, table in layer.tables.items():
        lines = [f"### {name}", table["description"].strip()]
        inherited = set(layer.tables[table["extends"]]["columns"]) if "extends" in table else set()
        if inherited:
            lines.append(f"Every column of {table['extends']}, plus:")
        for column, spec in table["columns"].items():
            if column in inherited:
                continue
            tags = [types.get(name, {}).get(column, "?")]
            if spec.get("pii"):
                tags.append("personal data, only in the fraud team's warehouse")
            if spec.get("free_text"):
                tags.append("free text")
            text = " ".join(spec["description"].split())
            if "values" in spec:
                text += f" Values: {', '.join(str(v) for v in spec['values'])}."
            lines.append(f"- {column} ({', '.join(tags)}): {text}")
        parts.append("\n".join(lines))
    joins = "\n".join(f"- {r['from']} = {r['to']}" for r in layer.relationships)
    return "\n\n".join(parts) + f"\n\n### How the tables join\n{joins}"


def system_prompt(db_path: str | Path, layer: SemanticLayer | None = None) -> str:
    layer = layer or SemanticLayer()
    instructions = (PROMPTS_DIR / "system.md").read_text().strip()
    tables = describe_tables(layer, column_types(db_path))
    glossary = layer.glossary.strip().removeprefix("# Glossary").strip()
    return (
        f"{instructions}\n\n## Warehouse tables\n\n{tables}\n\n"
        f"## Glossary\n\n{glossary}\n"
    )


def warehouse_dates(db_path: str | Path) -> dict[str, str]:
    con = connect(db_path)
    try:
        extract, start, end = con.execute(
            "SELECT extract_date, data_start, data_end FROM warehouse_info"
        ).fetchone()
    finally:
        con.close()
    return {"extract_date": extract.isoformat(), "data_start": start.isoformat(),
            "data_end": end.isoformat()}


def session_context(role: str, dates: dict[str, str]) -> str:
    """The first block of a session's first message. The app sets it, not the user."""
    if role not in ROLES:
        raise ValueError(f"Unknown role {role!r}. Roles: {', '.join(ROLES)}.")
    return (
        "Session context, set by the app:\n"
        f"- User's role: {ROLES[role]}\n"
        f"- Warehouse extract date (today): {dates['extract_date']}. "
        f"Loss dates run from {dates['data_start']} to {dates['data_end']}."
    )


def fingerprint(*parts: object) -> str:
    """A short hash of everything that shapes the model's behavior, recorded with each run so
    results can be traced to the exact prompt, tools and settings that produced them."""
    text = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()[:10]
