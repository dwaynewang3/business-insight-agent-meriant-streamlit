"""Compile agreed metric definitions into SQL.

Every metric is defined once, in metrics.yaml. `SemanticLayer.compile` turns a request
(metric, dimensions, filters, time grain, date range) into a single SQL query, so every
user and the agent get the same number for the same question, and can see the SQL behind it.
"""

import textwrap
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

import yaml

SEMANTIC_DIR = Path(__file__).parent
GRAINS = ("day", "week", "month", "quarter", "year")


class MetricError(ValueError):
    """A metric request that can't be compiled. The message says how to fix it."""


@dataclass(frozen=True)
class MetricRequest:
    metric: str
    dimensions: tuple[str, ...] = ()
    filters: dict[str, str | list[str]] = field(default_factory=dict)
    grain: str | None = "month"  # None gives one total per dimension combination
    start: date | str | None = None  # inclusive
    end: date | str | None = None  # inclusive


def _literal(value: object) -> str:
    """A SQL string literal, with quotes escaped."""
    return "'" + str(value).replace("'", "''") + "'"


def _as_date(value: date | str | None, name: str) -> date | None:
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise MetricError(f"{name} must be a date like 2026-04-01, not {value!r}.") from error


def _normalize_columns(table: dict) -> dict:
    """Allow `column: description` shorthand in tables.yaml."""
    columns = {
        name: spec if isinstance(spec, dict) else {"description": spec}
        for name, spec in table["columns"].items()
    }
    return {**table, "columns": columns}


class SemanticLayer:
    def __init__(self, directory: Path = SEMANTIC_DIR):
        definitions = yaml.safe_load((directory / "metrics.yaml").read_text())
        self.sources: dict[str, dict] = definitions["sources"]
        self.metrics: dict[str, dict] = definitions["metrics"]
        catalog = yaml.safe_load((directory / "tables.yaml").read_text())
        self.tables = {name: _normalize_columns(t) for name, t in catalog["tables"].items()}
        # A view can list `extends: <table>` to inherit that table's columns, then add its own.
        for table in self.tables.values():
            if parent := table.get("extends"):
                table["columns"] = {**self.tables[parent]["columns"], **table["columns"]}
        self.relationships: list[dict] = catalog.get("relationships", [])
        self.glossary = (directory / "glossary.md").read_text()

    def dimensions(self, metric: str) -> list[str]:
        """Dimensions a metric can be broken down or filtered by."""
        spec = self._metric(metric)
        if spec.get("type") == "ratio":
            denominator = self.dimensions(spec["denominator"])
            return [d for d in self.dimensions(spec["numerator"]) if d in denominator]
        return list(self.sources[spec["source"]]["dimensions"])

    def describe(self, metric: str) -> dict:
        """Everything a user needs to know about a metric, including how it's computed."""
        spec = self._metric(metric)
        info = {
            "name": metric,
            "label": spec["label"],
            "description": spec["description"],
            "unit": spec["unit"],
            "dimensions": self.dimensions(metric),
        }
        if spec.get("type") == "ratio":
            info["definition"] = (
                f"{spec.get('scale', 1)} * {spec['numerator']} / {spec['denominator']}"
            )
        else:
            info["definition"] = f"{spec['expression']} over {spec['source']}"
            info["time_column"] = spec["time_column"]
        if "notes" in spec:
            info["notes"] = spec["notes"]
        return info

    def compile(self, request: MetricRequest) -> str:
        """SQL that returns the metric as a `value` column, by period and dimensions."""
        spec = self._metric(request.metric)
        request = self._validated(request)
        if spec.get("type") == "ratio":
            return self._compile_ratio(request, spec)
        return self._compile_simple(request, spec)

    def _metric(self, name: str) -> dict:
        if name not in self.metrics:
            raise MetricError(
                f"Unknown metric {name!r}. Available metrics: {', '.join(self.metrics)}."
            )
        return self.metrics[name]

    def _validated(self, request: MetricRequest) -> MetricRequest:
        allowed = self.dimensions(request.metric)
        for dimension in [*request.dimensions, *request.filters]:
            if dimension not in allowed:
                raise MetricError(
                    f"{dimension!r} isn't a dimension of {request.metric}. "
                    f"Available: {', '.join(allowed)}."
                )
        if request.grain is not None and request.grain not in GRAINS:
            raise MetricError(f"grain must be one of {', '.join(GRAINS)}, or None for totals.")
        start, end = _as_date(request.start, "start"), _as_date(request.end, "end")
        if start and end and start > end:
            raise MetricError("start must be on or before end.")
        return replace(request, start=start, end=end)

    def _compile_simple(self, request: MetricRequest, spec: dict) -> str:
        source = self.sources[spec["source"]]
        time_column = spec["time_column"]
        columns = []
        if request.grain:
            columns.append(f"CAST(date_trunc('{request.grain}', {time_column}) AS DATE) AS period")
        columns += request.dimensions
        columns.append(f"{spec['expression']} AS value")

        conditions = []
        if request.start:
            # Monthly sources store the first day of each month, so compare whole months.
            start = request.start.replace(day=1) if time_column == "month" else request.start
            conditions.append(f"{time_column} >= DATE '{start.isoformat()}'")
        if request.end:
            conditions.append(f"{time_column} <= DATE '{request.end.isoformat()}'")
        for dimension, value in request.filters.items():
            values = value if isinstance(value, list) else [value]
            conditions.append(f"{dimension} IN ({', '.join(_literal(v) for v in values)})")

        sql = (
            f"WITH source AS (\n{textwrap.indent(source['sql'].strip(), '    ')}\n)\n"
            f"SELECT {', '.join(columns)}\nFROM source"
        )
        if conditions:
            sql += "\nWHERE " + "\n  AND ".join(conditions)
        if request.grain or request.dimensions:
            sql += "\nGROUP BY ALL\nORDER BY ALL"
        return sql

    def _compile_ratio(self, request: MetricRequest, spec: dict) -> str:
        keys = (["period"] if request.grain else []) + list(request.dimensions)
        parts = {
            role: self._compile_simple(
                replace(request, metric=spec[role]), self._metric(spec[role])
            )
            for role in ("numerator", "denominator")
        }
        join = f"USING ({', '.join(keys)})" if keys else "ON TRUE"
        value = (
            f"{spec.get('scale', 1)} * numerator.value / nullif(denominator.value, 0) AS value"
        )
        return (
            f"WITH numerator AS (\n{textwrap.indent(parts['numerator'], '    ')}\n),\n"
            f"denominator AS (\n{textwrap.indent(parts['denominator'], '    ')}\n)\n"
            f"SELECT {', '.join([*keys, value])}\n"
            f"FROM numerator JOIN denominator {join}"
            + ("\nORDER BY ALL" if keys else "")
        )
