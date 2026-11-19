"""Check each finding's key numbers against the result of its own evidence SQL.

The plan's trust criterion is that every number in an answer links to the SQL that produced
it (DEV_PLAN.md section 3). This re-runs each finding's `evidence_sql` through the SQL guard
and confirms that each of its key numbers is a fair rounding of the cell it names in the
result, or of that column's total or average (the matching rules are in
agent/key_numbers.py). A number the agent worked out in its head, took from a different query,
or put on the wrong row isn't confirmed.

The result is reported as its own count ("key numbers confirmed"), apart from pass or fail,
because the trust criterion is separate from whether the answer is right. The agent runs the
same check before its answer goes out (agent/graph.py), so this count is after any repair.
"""

from pathlib import Path

from agent.key_numbers import check_numbers
from mcp_servers.warehouse import run_query

from .what import GRADING_LIMITS


class NumberChecker:
    def __init__(self, db_path: str | Path):
        self.db_path = db_path

    def check(self, report: dict | None) -> dict:
        """How many of the report's key numbers its findings' SQL confirms, and which not."""
        def result_for(sql: str):
            result = run_query(self.db_path, sql, GRADING_LIMITS)
            return result.columns, result.rows

        return check_numbers(report, result_for)
