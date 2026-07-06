"""
Supply Chain Disruption Monitor — Demo Script

Scripted demo of the "Shanghai to Rotterdam" scenario.
Runs each tool directly (no agent) so you can see raw tool output,
then runs the full agent query to demonstrate multi-tool synthesis.

Usage:
    uv run demo.py              # full demo: tool outputs + agent synthesis
    uv run demo.py --tools-only # just tool outputs, skip the agent
    uv run demo.py --agent-only # skip tool outputs, just the agent synthesis
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def _print_section(title: str) -> None:
    print(f"\n{'─'*70}")
    print(f"  {title}")
    print(f"{'─'*70}")


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))


# ---------------------------------------------------------------------------
# Tool demos
# ---------------------------------------------------------------------------

async def demo_tools() -> None:
    from tools.ports import ports_by_region
    from tools.weather import get_port_weather
    from tools.vessels import get_vessel_positions
    from tools.news import search_disruption_news
    from tools.congestion import get_port_congestion

    # 1. Route waypoints
    _print_section("TOOL: list_major_ports — route waypoints")
    for region in ["East Asia", "Southeast Asia", "Red Sea", "Northwest Europe"]:
        ports = ports_by_region(region)
        print(f"\n{region}:")
        for p in ports:
            print(f"  {p['locode']:8s}  {p['name']} ({p['country']})")

    # 2. Weather at origin and destination
    for port in ["Shanghai", "Rotterdam"]:
        _print_section(f"TOOL: get_port_weather — {port}")
        result = await get_port_weather(port)
        summary = {
            "port": result.get("port"),
            "condition": result.get("current", {}).get("condition"),
            "wind_speed_kn": result.get("current", {}).get("wind_speed_kn"),
            "wind_description": result.get("current", {}).get("wind_description"),
            "operational_impact": result.get("operational_impact"),
        }
        _print_json(summary)

    # 3. Vessel traffic at key chokepoints
    chokepoints = ["Strait of Malacca", "Red Sea", "Suez Canal"]
    for region in chokepoints:
        _print_section(f"TOOL: get_vessel_positions — {region}")
        result = await get_vessel_positions(region, max_vessels=10)
        if "error" in result:
            print(f"  ⚠  {result['error']}")
        else:
            summary = {
                "region": result["region"],
                "vessel_count": result["vessel_count"],
                "underway": result["underway"],
                "anchored_or_moored": result["anchored_or_moored"],
                "sample_vessels": result["vessels"][:3],
            }
            _print_json(summary)

    # 4. Disruption news
    queries = [
        ("Red Sea shipping attack Houthi", 14),
        ("Suez Canal disruption 2025", 30),
        ("Shanghai port congestion", 7),
    ]
    for query, days in queries:
        _print_section(f"TOOL: search_disruption_news — \"{query}\"")
        result = await search_disruption_news(query, days=days)
        if "error" in result:
            print(f"  ⚠  {result['error']}")
        else:
            summary = {
                "query": result["query"],
                "article_count": result["article_count"],
                "flagged_high_signal": result["flagged_high_signal"][:3],
                "top_articles": [
                    {"title": a["title"], "source": a["source"], "published_at": a["published_at"]}
                    for a in result["articles"][:3]
                ],
            }
            _print_json(summary)

    # 5. Congestion at key ports
    key_ports = ["Shanghai", "Singapore", "Port Said", "Rotterdam"]
    for port in key_ports:
        _print_section(f"TOOL: get_port_congestion — {port}")
        result = get_port_congestion(port)
        _print_json(result)


# ---------------------------------------------------------------------------
# Agent demo
# ---------------------------------------------------------------------------

async def demo_agent() -> None:
    from agent import run_query  # noqa: PLC0415

    _print_section("AGENT SYNTHESIS — Shanghai to Rotterdam full risk assessment")
    print("  (The agent calls tools autonomously and synthesizes the results.)")
    print("  This may take 30–90 seconds depending on your hardware.\n")

    query = (
        "What disruptions could affect shipments from Shanghai to Rotterdam right now? "
        "Walk through the key waypoints and chokepoints, check weather, vessel traffic, "
        "recent news, and port congestion, then give me a structured risk assessment."
    )

    answer = await run_query(query)
    print(answer)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    args = set(sys.argv[1:])
    run_tools = "--agent-only" not in args
    run_agent = "--tools-only" not in args

    print("Supply Chain Disruption Monitor — Demo")
    print("Shanghai to Rotterdam Route Assessment")
    print("=" * 70)

    if run_tools:
        await demo_tools()

    if run_agent:
        await demo_agent()

    print("\n" + "=" * 70)
    print("Demo complete.")


if __name__ == "__main__":
    asyncio.run(main())
