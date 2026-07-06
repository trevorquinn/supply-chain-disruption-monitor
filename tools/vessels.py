"""
Vessel positions via AISStream.io — free WebSocket AIS feed.
Sign up at https://aisstream.io/ to get an API key.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import websockets

from tools import repository

# Bounding boxes [min_lat, min_lon, max_lat, max_lon] for major shipping regions.
# Source of truth: data/regions.toml
REGION_BBOXES: dict[str, list[list[float]]] = repository.region_bboxes()


def _normalize_region(region: str) -> str:
    return region.strip().lower()


def _find_bbox(region: str) -> list[list[float]] | None:
    key = _normalize_region(region)
    if key in REGION_BBOXES:
        return REGION_BBOXES[key]
    # Partial match
    for k, v in REGION_BBOXES.items():
        if key in k or k in key:
            return v
    return None


async def get_vessel_positions(region: str, max_vessels: int = 20, timeout_s: int = 8) -> dict:
    """
    Fetch active vessel positions in a region via AISStream.io WebSocket feed.

    Args:
        region: Named region (e.g. "South China Sea", "Strait of Malacca", "Red Sea")
        max_vessels: Maximum number of vessels to return (default 20)
        timeout_s: Seconds to listen before closing connection (default 8)

    Returns:
        dict with 'region', 'vessel_count', and 'vessels' list
    """
    api_key = os.getenv("AISSTREAM_API_KEY", "")
    if not api_key or api_key == "your_aisstream_key_here":
        return {
            "error": "AISSTREAM_API_KEY not set. Sign up free at https://aisstream.io/ and add the key to .env",
            "region": region,
            "vessels": [],
        }

    bbox = _find_bbox(region)
    if not bbox:
        available = list(REGION_BBOXES.keys())
        return {
            "error": f"Region '{region}' not recognized.",
            "available_regions": available,
            "vessels": [],
        }

    subscribe_msg = {
        "APIKey": api_key,
        "BoundingBoxes": bbox,
        "FilterMessageTypes": ["PositionReport"],
    }

    vessels: list[dict[str, Any]] = []
    seen_mmsi: set[str] = set()

    try:
        async with websockets.connect(
            "wss://stream.aisstream.io/v0/stream",
            ping_interval=None,
            open_timeout=10,
        ) as ws:
            await ws.send(json.dumps(subscribe_msg))

            deadline = asyncio.get_event_loop().time() + timeout_s
            while len(vessels) < max_vessels:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                except asyncio.TimeoutError:
                    break

                msg = json.loads(raw)
                if msg.get("MessageType") != "PositionReport":
                    continue

                meta = msg.get("MetaData", {})
                pos = msg.get("Message", {}).get("PositionReport", {})
                mmsi = str(meta.get("MMSI", ""))
                if mmsi in seen_mmsi:
                    continue
                seen_mmsi.add(mmsi)

                vessels.append(
                    {
                        "mmsi": mmsi,
                        "name": meta.get("ShipName", "Unknown").strip(),
                        "lat": round(pos.get("Latitude", 0), 4),
                        "lon": round(pos.get("Longitude", 0), 4),
                        "speed_kn": round(pos.get("Sog", 0), 1),  # Speed over ground
                        "course_deg": pos.get("Cog"),
                        "heading_deg": pos.get("TrueHeading"),
                        "nav_status": _nav_status(pos.get("NavigationalStatus", 0)),
                        "time_utc": meta.get("time_utc"),
                    }
                )

    except (OSError, websockets.exceptions.WebSocketException) as exc:
        return {
            "error": f"WebSocket connection failed: {exc}",
            "region": region,
            "vessels": [],
        }

    # Simple speed-based summary
    underway = [v for v in vessels if v["speed_kn"] > 0.5]
    anchored = [v for v in vessels if v["speed_kn"] <= 0.5]

    return {
        "region": region,
        "bounding_box": bbox,
        "vessel_count": len(vessels),
        "underway": len(underway),
        "anchored_or_moored": len(anchored),
        "vessels": vessels,
        "note": f"Snapshot collected over {timeout_s}s from live AIS feed.",
    }


_NAV_STATUS_MAP = {
    0: "Underway using engine",
    1: "At anchor",
    2: "Not under command",
    3: "Restricted manoeuvrability",
    4: "Constrained by draught",
    5: "Moored",
    6: "Aground",
    7: "Engaged in fishing",
    8: "Underway sailing",
    15: "Unknown",
}


def _nav_status(code: int) -> str:
    return _NAV_STATUS_MAP.get(code, f"Status {code}")
