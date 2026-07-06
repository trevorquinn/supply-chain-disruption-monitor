"""
Static port reference data: coordinates, UN/LOCODE, and regional groupings.
Used by weather tool (needs lat/lon) and list_major_ports tool.

The port records themselves live in ``data/ports.toml`` and are loaded through
``tools.repository``; this module owns the lookup/normalization logic on top.
"""

from __future__ import annotations
from typing import TypedDict, cast

from tools import repository


class PortInfo(TypedDict):
    name: str
    locode: str
    country: str
    lat: float
    lon: float
    region: str


# Canonical port list — major container ports on key trade routes.
# Source of truth: data/ports.toml
PORTS: dict[str, PortInfo] = cast("dict[str, PortInfo]", repository.ports())

# Normalize lookup: lowercase/stripped name → canonical key
_LOOKUP: dict[str, str] = {k.lower(): k for k in PORTS}
# Also index by locode
_LOCODE_LOOKUP: dict[str, str] = {v["locode"].upper(): k for k, v in PORTS.items()}


def find_port(name: str) -> PortInfo | None:
    """Case-insensitive lookup by name or UN/LOCODE."""
    key = name.strip().lower()
    canonical = _LOOKUP.get(key)
    if canonical:
        return PORTS[canonical]
    # Try LOCODE
    canonical = _LOCODE_LOOKUP.get(name.strip().upper())
    if canonical:
        return PORTS[canonical]
    # Partial match
    for k, v in PORTS.items():
        if key in k.lower() or key in v["locode"].lower():
            return v
    return None


def ports_by_region(region: str) -> list[PortInfo]:
    """Return all ports for a region (case-insensitive substring match)."""
    region_lower = region.lower()
    return [p for p in PORTS.values() if region_lower in p["region"].lower()]


ALL_REGIONS = sorted({p["region"] for p in PORTS.values()})
