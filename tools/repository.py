"""
Data-access layer for static reference data.

This is the ONLY module that knows the reference data lives in TOML files under
``data/``. Everything else asks this module for whole tables and never touches the
storage format directly. To move to a real database later (SQLite, DuckDB, Postgres),
reimplement the loaders here — the function signatures stay the same, so the tool
modules that depend on them never change.
"""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=None)
def _load(filename: str) -> dict[str, Any]:
    """Load and cache a TOML file from the data directory."""
    with open(_DATA_DIR / filename, "rb") as f:
        return tomllib.load(f)


def ports() -> dict[str, dict[str, Any]]:
    """Port reference data keyed by common short name."""
    return _load("ports.toml")["ports"]


def region_bboxes() -> dict[str, list[list[float]]]:
    """Shipping-region bounding boxes keyed by lowercase region name."""
    return _load("regions.toml")["regions"]


def port_profiles() -> dict[str, dict[str, Any]]:
    """Per-port congestion profiles keyed by UN/LOCODE."""
    return _load("port_profiles.toml")["profiles"]


def supply_chain_terms() -> list[str]:
    """Default search terms biasing news queries toward disruption signals."""
    return _load("news_terms.toml")["supply_chain_terms"]


def alert_terms() -> list[str]:
    """High-signal terms scanned in article text to flag disruption events."""
    return _load("news_terms.toml")["alert_terms"]
