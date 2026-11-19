"""Run the agent's SQL safely: one read-only SELECT, no file access, a time limit and size caps.

Every query the agent writes goes through run_query. Three layers protect the data:

1. check_sql uses DuckDB's own parser and allows exactly one SELECT statement. It's the same
   parser that runs the query, so the check and the engine can't disagree about what a query
   does.
2. The connection is read-only and can't read or write files, attach other databases or load
   extensions. Its settings are locked, so SQL can't switch any of this back on.
3. A timer stops queries that run too long, and results are capped in rows and characters
   before they reach the model.

The first layer gives the model clear error messages. The other two hold even if a check
misses something.
"""

import json
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime
from datetime import time as time_of_day
from decimal import Decimal
from pathlib import Path

import duckdb

# Every connection uses these settings. DuckDB refuses a second connection to the same file
# with different settings in the same process, so anything that opens the warehouse next to the
# agent's queries (the eval runner, for example) should use connect() too.
CONNECTION_CONFIG = {
    "enable_external_access": False,  # no files, other databases, extensions or network
    "autoinstall_known_extensions": False,
    "autoload_known_extensions": False,
    "memory_limit": "1GB",
    "lock_configuration": True,  # SQL can't change any of these settings
}


@dataclass(frozen=True)
class Limits:
    timeout_seconds: float = 10.0
    max_rows: int = 200
    max_chars: int = 20_000  # characters of row data sent to the model, as JSON
    max_cell_chars: int = 500  # longer text values are cut, for example free-text notes


DEFAULT_LIMITS = Limits()


class QueryError(Exception):
    """A query that didn't run. The message tells the model what to change."""


class QueryRejected(QueryError):
    """Not allowed: more than one statement, not a SELECT, or it touches files."""


class QueryFailed(QueryError):
    """DuckDB couldn't run it, for example because of a typo or an unknown column."""


class QueryTimeout(QueryError):
    """It ran longer than the time limit."""


@dataclass(frozen=True)
class QueryResult:
    sql: str  # exactly the statement that ran
    columns: tuple[str, ...]
    rows: tuple[tuple, ...]  # JSON-friendly values
    truncated: bool  # the query returned more rows or characters than the limits allow
    seconds: float


def connect(db_path: str | Path) -> duckdb.DuckDBPyConnection:
    """A read-only connection that can't touch files, extensions or its own settings."""
    return duckdb.connect(str(db_path), read_only=True, config=CONNECTION_CONFIG)


def check_sql(sql: str) -> duckdb.Statement:
    """The single SELECT statement in sql. Anything else raises QueryRejected saying why."""
    try:
        statements = duckdb.extract_statements(sql)
    except duckdb.Error as error:
        raise QueryFailed(f"The query couldn't be parsed. {error}") from error
    if not statements:
        raise QueryRejected("The query is empty. Send one SELECT statement.")
    kinds = [statement.type.name for statement in statements]
    if len(statements) > 1:
        raise QueryRejected(
            f"Send exactly one SELECT statement per query, not {len(statements)} "
            f"({', '.join(kinds)})."
        )
    if statements[0].type != duckdb.StatementType.SELECT:
        raise QueryRejected(
            f"Only SELECT queries are allowed, not {kinds[0]}. The warehouse is read-only."
        )
    return statements[0]


def reads_no_table(sql: str) -> bool:
    """Whether a query is a SELECT that reads no table, by DuckDB's own parser. `SELECT 1` and
    `SELECT 638 AS claims` read none: their result shows nothing about the warehouse. Anything
    that isn't a single SELECT the parser can read is False, and left to run_query to judge."""
    try:
        tree = json.loads(duckdb.connect().execute(
            "SELECT json_serialize_sql(?)", [sql]).fetchone()[0])
    except (duckdb.Error, TypeError, ValueError):
        return False
    if tree.get("error") or len(tree.get("statements", [])) != 1:
        return False
    return '"type":"BASE_TABLE"' not in json.dumps(tree, separators=(",", ":"))


def run_query(db_path: str | Path, sql: str, limits: Limits = DEFAULT_LIMITS) -> QueryResult:
    """Run one SELECT on a locked-down connection, and return capped, JSON-friendly rows."""
    statement = check_sql(sql)
    started = time.perf_counter()
    con = connect(db_path)
    timer = threading.Timer(limits.timeout_seconds, con.interrupt)
    timer.start()
    try:
        cursor = con.execute(statement)
        columns = tuple(column[0] for column in cursor.description)
        fetched = cursor.fetchmany(limits.max_rows + 1)
    except duckdb.InterruptException as error:
        raise QueryTimeout(
            f"The query ran longer than {limits.timeout_seconds:g} seconds and was stopped. "
            "Filter or aggregate earlier, or join fewer rows."
        ) from error
    except duckdb.PermissionException as error:
        raise QueryRejected(
            "Queries can only read the warehouse tables, not files, other databases or "
            "extensions."
        ) from error
    except duckdb.Error as error:
        raise QueryFailed(str(error)) from error
    finally:
        timer.cancel()
        con.close()
    rows, truncated = _cap(fetched, limits)
    return QueryResult(
        sql=statement.query,
        columns=columns,
        rows=rows,
        truncated=truncated,
        seconds=round(time.perf_counter() - started, 3),
    )


def _cap(fetched: list[tuple], limits: Limits) -> tuple[tuple[tuple, ...], bool]:
    """Keep rows until the row or character limit is reached."""
    truncated = len(fetched) > limits.max_rows
    rows, used = [], 0
    for row in fetched[: limits.max_rows]:
        plain = tuple(_plain(value, limits.max_cell_chars) for value in row)
        used += len(json.dumps(plain)) + 1
        if used > limits.max_chars:
            truncated = True
            break
        rows.append(plain)
    return tuple(rows), truncated


def _plain(value: object, max_chars: int) -> object:
    """A JSON-friendly version of a DuckDB value, with long text cut short."""
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date | datetime | time_of_day):
        return value.isoformat()
    text = value if isinstance(value, str) else str(value)  # intervals, lists, structs, ...
    return text if len(text) <= max_chars else text[:max_chars] + "…"
