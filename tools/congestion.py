"""
Port congestion data — realistically mocked.

Design intent: The tool interface is identical to what a live API would look like
(MarineTraffic, FreightWaves, etc.). Mocking gives full demo control — a "Shanghai
congestion spike" can be scripted without a paywall.

The mock is seeded deterministically per port so results are stable across calls
within a session, but not entirely uniform (ports have realistic relative congestion).
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone

from tools import repository
from tools.ports import find_port

# Base congestion profiles per port — represents relative typical load.
# Scale: 0.0 (empty) to 1.0 (at capacity). Source of truth: data/port_profiles.toml
_PORT_PROFILES: dict[str, dict] = repository.port_profiles()

_DEFAULT_PROFILE = {"base_util": 0.65, "volatility": 0.12, "typical_wait_h": 24, "berths": 20}


def _pseudo_random(seed: str, low: float = 0.0, high: float = 1.0) -> float:
    """Deterministic pseudo-random float from a string seed."""
    digest = hashlib.md5(seed.encode()).hexdigest()
    val = int(digest[:8], 16) / 0xFFFFFFFF
    return low + val * (high - low)


def _compute_congestion(locode: str, port_name: str) -> dict:
    profile = _PORT_PROFILES.get(locode, _DEFAULT_PROFILE)

    # Generate a stable daily variation using today's date as part of the seed
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    seed = f"{locode}:{today}"
    daily_delta = _pseudo_random(seed, -profile["volatility"], profile["volatility"])

    utilization = min(0.99, max(0.10, profile["base_util"] + daily_delta))

    # Scale wait time with utilization (nonlinear — congestion spikes near capacity)
    util_factor = 1 + max(0, (utilization - 0.75) / 0.25) ** 2
    wait_hours = round(profile["typical_wait_h"] * util_factor * (0.8 + daily_delta), 1)

    # Vessels queued: rough approximation
    vessels_queued = max(0, int(profile["berths"] * max(0, utilization - 0.70) * 2.5))

    # Trend: compare to yesterday
    yesterday = (
        datetime.now(timezone.utc)
        .replace(hour=0, minute=0, second=0)
        .__class__
    )
    yesterday_seed = f"{locode}:{today}_minus1"
    yesterday_delta = _pseudo_random(yesterday_seed, -profile["volatility"], profile["volatility"])
    yesterday_util = min(0.99, max(0.10, profile["base_util"] + yesterday_delta))

    trend_delta = utilization - yesterday_util
    if trend_delta > 0.05:
        trend = "worsening"
    elif trend_delta < -0.05:
        trend = "improving"
    else:
        trend = "stable"

    # Severity assessment
    if utilization > 0.90:
        severity = "critical"
        advisory = "Severe congestion. Expect significant delays; consider alternate routing."
    elif utilization > 0.80:
        severity = "high"
        advisory = "High congestion. Plan for extended dwell times and vessel queuing."
    elif utilization > 0.70:
        severity = "moderate"
        advisory = "Moderate congestion. Standard buffers should absorb delays."
    else:
        severity = "low"
        advisory = "Port operating within normal parameters."

    return {
        "port": port_name,
        "locode": locode,
        "capacity_utilization_pct": round(utilization * 100, 1),
        "vessels_queued": vessels_queued,
        "estimated_wait_hours": wait_hours,
        "trend_vs_yesterday": trend,
        "severity": severity,
        "advisory": advisory,
        "berths_total": profile["berths"],
        "data_source": "mocked — representative of live MarineTraffic/FreightWaves data",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def get_port_congestion(port_name: str) -> dict:
    """
    Get current congestion metrics for a named port.

    Args:
        port_name: Common name or UN/LOCODE of the port

    Returns:
        dict with utilization, wait times, vessel queue, trend, and advisory
    """
    port = find_port(port_name)
    if not port:
        return {
            "error": f"Port '{port_name}' not found. Use list_major_ports() to see available ports.",
            "port": port_name,
        }
    return _compute_congestion(port["locode"], port["name"])
