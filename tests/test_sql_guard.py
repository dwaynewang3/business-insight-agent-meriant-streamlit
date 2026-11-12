"""The SQL guard lets the agent read the warehouse tables and nothing else.

Each layer is tested on its own: the statement check, the locked-down connection with the
check bypassed, and the time and size limits. The attacks include file reads, several
statements in one query, writes, ATTACH, COPY and INSTALL.
"""

import json
import shutil
import time

import duckdb
import pytest

from evals.cases import load_what_cases, load_why_cases
from mcp_servers.warehouse import (
    Limits,
    QueryFailed,
    QueryRejected,
    QueryTimeout,
    check_sql,
    connect,
    run_query,
)

SECRET = "ANTHROPIC_API_KEY=sk-test-not-a-real-key"


@pytest.fixture(scope="module")
def files(tmp_path_factory):
    """A small warehouse, with a secret file and a CSV file next to it that no query may read."""
    folder = tmp_path_factory.mktemp("guard")
    db = folder / "warehouse.duckdb"
    con = duckdb.connect(str(db))
    con.execute("""
        CREATE TABLE claims AS
        SELECT 'CLM-' || lpad(i::VARCHAR, 6, '0') AS claim_id,
               (1000 + i * 7.25)::DECIMAL(12, 2) AS amount,
               DATE '2026-01-01' + i::INTEGER AS loss_date,
               CASE WHEN i = 1 THEN repeat('long note ', 200) ELSE 'ok' END AS notes
        FROM range(1, 301) AS r(i)
    """)
    con.close()
    secret = folder / ".env"
    secret.write_text(SECRET)
    (folder / "export.csv").write_text(f"secret\n{SECRET}\n")
    return db, secret, folder


@pytest.fixture(scope="module")
def guarded_dev(built, tmp_path_factory):
    """A copy of the dev warehouse. The original is already open with default settings, and
    DuckDB won't open one file with two different settings in the same process."""
    copy = tmp_path_factory.mktemp("guarded") / "dev.duckdb"
    shutil.copy(built[2], copy)
    return copy


ALLOWED = [
    "SELECT 1",
    "SELECT 1;",
    "-- a comment\nSELECT 1 -- and another",
    "SELECT 1 /* ; DROP TABLE claims */",
    "WITH a AS (SELECT 1 AS x) SELECT x FROM a",
    "(SELECT 1) UNION ALL (SELECT 2)",
    "FROM claims LIMIT 1",
    "DESCRIBE claims",
    "SUMMARIZE claims",
]


@pytest.mark.parametrize("sql", ALLOWED)
def test_one_select_statement_is_allowed(sql):
    assert check_sql(sql).type == duckdb.StatementType.SELECT


def test_every_eval_reference_query_is_allowed():
    queries = [sql for case in load_what_cases() for sql in case.reference_sql]
    queries += [case.verify_sql for case in load_why_cases() if case.verify_sql]
    for sql in queries:
        check_sql(sql)


REJECTED = [
    "",
    "SELECT 1; SELECT 2",
    "SELECT 1; DROP TABLE claims",
    "DROP TABLE claims",
    "INSERT INTO claims SELECT * FROM claims",
    "UPDATE claims SET amount = 0",
    "DELETE FROM claims",
    "CREATE TABLE stolen AS SELECT * FROM claims",
    "ALTER TABLE claims ADD COLUMN x INTEGER",
    "ATTACH 'other.duckdb' AS other",
    "DETACH other",
    "COPY claims TO 'claims.csv'",
    "COPY claims FROM 'claims.csv'",
    "EXPORT DATABASE 'dump'",
    "INSTALL httpfs",
    "LOAD httpfs",
    "SET enable_external_access = true",
    "RESET memory_limit",
    "CALL pragma_version()",
    "CHECKPOINT",
    "BEGIN TRANSACTION",
    "CREATE SECRET stolen (TYPE s3, KEY_ID 'x', SECRET 'y')",
    "EXPLAIN SELECT 1",
    "PIVOT claims ON notes USING count(*)",  # DuckDB runs this as a CREATE, then a SELECT
]


@pytest.mark.parametrize("sql", REJECTED)
def test_anything_but_one_select_is_rejected(sql):
    with pytest.raises(QueryRejected):
        check_sql(sql)


def test_sql_that_doesnt_parse_fails_with_the_parser_message():
    with pytest.raises(QueryFailed, match="Parser Error"):
        check_sql("SELEC amount FROM claims")
    with pytest.raises(QueryFailed):
        check_sql("SELECT * INTO stolen FROM claims")


def test_connection_blocks_files_writes_and_settings_even_without_the_check(files):
    """The second layer: statements that skip check_sql still can't do any harm."""
    db, secret, folder = files
    attacks = [
        f"SELECT * FROM read_text('{secret}')",
        f"SELECT * FROM read_csv('{folder}/export.csv')",
        f"SELECT * FROM '{folder}/export.csv'",
        f"SELECT * FROM glob('{folder}/*')",
        f"SELECT * FROM query('SELECT * FROM read_text(''{secret}'')')",
        f"ATTACH '{folder}/other.duckdb' AS other",
        f"COPY claims TO '{folder}/stolen.csv'",
        "INSTALL httpfs",
        "LOAD httpfs",
        "INSERT INTO claims SELECT * FROM claims",
        "UPDATE claims SET amount = 0",
        "DELETE FROM claims",
        "CREATE TABLE stolen AS SELECT 1",
        "DROP TABLE claims",
        "SET enable_external_access = true",
        "SET memory_limit = '10GB'",
        "SET lock_configuration = false",
    ]
    con = connect(db)
    try:
        for sql in attacks:
            with pytest.raises(duckdb.Error) as caught:
                con.execute(sql).fetchall()
            assert SECRET not in str(caught.value), sql
        assert con.execute("SELECT count(*), sum(amount) FROM claims").fetchone() == (
            300, pytest.approx(300 * 1000 + 7.25 * 300 * 301 / 2)
        )
    finally:
        con.close()
    assert not (folder / "stolen.csv").exists()
    assert not (folder / "other.duckdb").exists()


def test_results_come_back_as_plain_values(files):
    db, _, _ = files
    result = run_query(
        db, "SELECT claim_id, amount, loss_date FROM claims ORDER BY claim_id LIMIT 2"
    )
    assert result.columns == ("claim_id", "amount", "loss_date")
    assert result.rows == (
        ("CLM-000001", 1007.25, "2026-01-02"),
        ("CLM-000002", 1014.5, "2026-01-03"),
    )
    assert not result.truncated
    assert result.sql.startswith("SELECT claim_id")


def test_rows_are_capped(files):
    db, _, _ = files
    result = run_query(db, "SELECT claim_id FROM claims", Limits(max_rows=10))
    assert len(result.rows) == 10
    assert result.truncated


def test_characters_are_capped(files):
    db, _, _ = files
    result = run_query(db, "SELECT claim_id, amount FROM claims", Limits(max_chars=500))
    assert 0 < len(result.rows) < 300
    assert result.truncated
    assert sum(len(json.dumps(row)) + 1 for row in result.rows) <= 500


def test_long_text_is_cut_short(files):
    db, _, _ = files
    result = run_query(
        db, "SELECT notes FROM claims WHERE claim_id = 'CLM-000001'", Limits(max_cell_chars=50)
    )
    ((note,),) = result.rows
    assert len(note) == 51
    assert note.endswith("…")


def test_slow_queries_are_stopped(files):
    db, _, _ = files
    started = time.perf_counter()
    with pytest.raises(QueryTimeout, match="0.5 seconds"):
        run_query(
            db,
            "SELECT count(*) FROM range(100000) a, range(100000) b, range(100) c",
            Limits(timeout_seconds=0.5),
        )
    assert time.perf_counter() - started < 5
    assert run_query(db, "SELECT 1").rows == ((1,),)


def test_file_reads_are_rejected_without_revealing_anything(files):
    db, secret, _ = files
    with pytest.raises(QueryRejected) as caught:
        run_query(db, f"SELECT * FROM read_text('{secret}')")
    assert SECRET not in str(caught.value)
    assert str(secret) not in str(caught.value)


def test_writes_are_rejected_before_they_run(files):
    db, _, _ = files
    for sql in ["DELETE FROM claims", "SELECT 1; DELETE FROM claims"]:
        with pytest.raises(QueryRejected):
            run_query(db, sql)
    assert run_query(db, "SELECT count(*) FROM claims").rows == ((300,),)


def test_errors_say_what_went_wrong(files):
    db, _, _ = files
    with pytest.raises(QueryFailed, match="no_such_column"):
        run_query(db, "SELECT no_such_column FROM claims")


def test_eval_reference_queries_run_through_the_guard(dev, guarded_dev):
    """Normal analysis isn't blocked: every "what" reference query runs within the limits."""
    for case in load_what_cases():
        sql = case.reference_sql[0]
        result = run_query(guarded_dev, sql)
        assert result.columns == (*case.keys, *case.values), case.id
        assert len(result.rows) == len(dev.execute(sql).fetchall()), case.id
        assert not result.truncated, case.id
