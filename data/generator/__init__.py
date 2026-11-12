"""Synthetic data generator for the Business Insights Agent demo.

Builds the claims warehouse of Meridian General Insurance, a fictional Australian motor and home
insurer, in DuckDB from a scenario file.
The same scenario and seed always produce the same data.
"""

from .build import generate

__all__ = ["generate"]
