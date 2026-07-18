"""
Supply Chain Disruption Monitor — MCP Server

Exposes five tools for supply chain intelligence:
  - list_major_ports     : static port reference (grounding tool)
  - get_port_weather     : current conditions + 24h forecast via Open-Meteo
  - get_vessel_positions : live AIS positions via AISStream.io WebSocket
  - search_disruption_news : recent headlines via NewsAPI
  - get_port_congestion  : wait times + utilization (realistically mocked)

Run standalone for development:
    uv run mcp dev server.py

Or wire into a PydanticAI agent (see agent.py).
"""

import asyncio
from dotenv import load_dotenv

load_dotenv()

from mcp.server.fastmcp import FastMCP

from tools.ports import ALL_REGIONS, find_port, ports_by_region, PORTS
from tools.weather import get_port_weather as _get_port_weather
from tools.vessels import get_vessel_positions as _get_vessel_positions
from tools.news import search_disruption_news as _search_disruption_news
from tools.congestion import get_port_congestion as _get_port_congestion

mcp = FastMCP(
    "supply-chain-monitor",
    instructions=(
        "You are a supply chain disruption analyst. Use these tools to assess "
        "risks on shipping routes. Always cross-reference weather, vessel traffic, "
        "news, and port congestion before drawing conclusions. When asked about a "
        "route, identify the key waypoints and assess each one."
    ),
)


# ---------------------------------------------------------------------------
# Tool: list_major_ports
# ---------------------------------------------------------------------------

@mcp.tool()
def list_major_ports(region: str = "") -> dict:
    """
    List major container ports, optionally filtered by region.

    This is the grounding tool — call it first when you need to know which
    ports are relevant to a route or region before calling other tools.

    Args:
        region: Optional region filter. Available regions:
                East Asia, Southeast Asia, South Asia, Middle East, Red Sea,
                Northwest Europe, Mediterranean, North America West,
                North America East.
                Leave empty to list all ports.

    Returns:
        dict with 'region', 'port_count', and 'ports' list
    """
    if region:
        matched = ports_by_region(region)
        if not matched:
            return {
                "error": f"No ports found for region '{region}'.",
                "available_regions": ALL_REGIONS,
                "ports": [],
            }
        return {
            "region": region,
            "port_count": len(matched),
            "ports": [
                {
                    "name": p["name"],
                    "locode": p["locode"],
                    "country": p["country"],
                    "region": p["region"],
                }
                for p in matched
            ],
        }
    else:
        return {
            "region": "all",
            "port_count": len(PORTS),
            "available_regions": ALL_REGIONS,
            "ports": [
                {
                    "name": p["name"],
                    "locode": p["locode"],
                    "country": p["country"],
                    "region": p["region"],
                }
                for p in PORTS.values()
            ],
        }


# ---------------------------------------------------------------------------
# Tool: get_port_weather
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_port_weather(port_name: str) -> dict:
    """
    Get current weather conditions and 24-hour forecast for a port.

    Weather is sourced from Open-Meteo (free, no API key required).
    Pay attention to wind speed in knots — values above 25 kn affect
    large vessel operations; above 40 kn typically suspends port activity.

    Args:
        port_name: Port common name (e.g. "Rotterdam") or UN/LOCODE (e.g. "NLRTM")

    Returns:
        dict with current conditions, wind speed, operational impact assessment,
        and hourly 24h forecast
    """
    return await _get_port_weather(port_name)


# ---------------------------------------------------------------------------
# Tool: get_vessel_positions
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_vessel_positions(region: str, max_vessels: int = 20) -> dict:
    """
    Get live vessel positions from AIS transponder data for a shipping region.

    Uses AISStream.io free WebSocket feed (requires AISSTREAM_API_KEY in .env).
    Listens for ~8 seconds and returns a snapshot of vessels in the region.

    Named regions this tool recognizes (not specific to any one route — use
    whichever apply to the route you're assessing):
      "South China Sea", "East China Sea", "Strait of Malacca",
      "Indian Ocean", "Red Sea", "Suez Canal", "Persian Gulf",
      "Mediterranean", "English Channel", "North Sea", "Taiwan Strait",
      "East Asia", "Northwest Europe", "North America West", "North America East"

    Args:
        region: Named region — see list above, or call list_major_ports() for context
        max_vessels: Maximum vessels to return (default 20)

    Returns:
        dict with vessel_count, underway/anchored breakdown, and per-vessel
        details (MMSI, name, position, speed, course, nav status)
    """
    return await _get_vessel_positions(region, max_vessels=max_vessels)


# ---------------------------------------------------------------------------
# Tool: search_disruption_news
# ---------------------------------------------------------------------------

@mcp.tool()
async def search_disruption_news(query: str, days: int = 7) -> dict:
    """
    Search recent news for supply chain disruption signals.

    Uses NewsAPI (free tier, 100 req/day — requires NEWS_API_KEY in .env).
    Returns articles with a 'flagged_high_signal' list highlighting those
    mentioning strikes, storms, blockages, attacks, or sanctions.

    If the query names a known port or shipping region, results are
    filtered to articles that actually mention that place — this prevents
    e.g. a Red Sea query returning unrelated Strait of Hormuz coverage just
    because both mention "attack". Check the 'location_filter' and
    'filtered_out' fields in the response to see if/how this applied.
    Lead each query with the exact place name for the filter to engage.

    Example query shapes — lead with the place actually relevant to *your*
    route, not necessarily these:
      - "<port name> port delay" (e.g. "Rotterdam port delay")
      - "<region name> attack blockage" (e.g. "Red Sea attack blockage")
      - "<region name> disruption" (e.g. "Suez Canal disruption")
      - "container shipping freight rates" (no location — not filtered)

    Args:
        query: Search query string, ideally leading with a specific place name
        days: Days back to search (default 7, max 30 on free tier)

    Returns:
        dict with articles list, flagged_high_signal subset, and
        location_filter/filtered_out showing whether results were filtered
    """
    return await _search_disruption_news(query, days=days)


# ---------------------------------------------------------------------------
# Tool: get_port_congestion
# ---------------------------------------------------------------------------

@mcp.tool()
def get_port_congestion(port_name: str) -> dict:
    """
    Get current congestion metrics for a port: vessel queue, wait times,
    capacity utilization, trend, and operational advisory.

    Data is realistically mocked (live data requires MarineTraffic or
    FreightWaves enterprise subscription). The interface mirrors what a
    production integration would return.

    Args:
        port_name: Port common name or UN/LOCODE

    Returns:
        dict with capacity_utilization_pct, vessels_queued,
        estimated_wait_hours, trend_vs_yesterday, severity, and advisory
    """
    return _get_port_congestion(port_name)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
