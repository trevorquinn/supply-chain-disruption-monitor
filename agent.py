"""
Supply Chain Disruption Monitor — PydanticAI Agent

Wires a PydanticAI agent to the MCP server via MCPServerStdio.
Uses qwen2.5:7b via Ollama (OpenAI-compatible endpoint at localhost:11434).

Prerequisites:
    ollama serve                    # start the Ollama daemon
    ollama pull qwen2.5:7b          # pull the model (~4.7 GB)
    cp .env.example .env            # set AISSTREAM_API_KEY and NEWS_API_KEY

Usage:
    uv run agent.py "What disruptions could affect shipments from Shanghai to Rotterdam?"
    uv run agent.py  # runs the default demo query
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Windows consoles default to cp1252, which can't encode the em-dash and other
# non-ASCII characters this script prints. Force UTF-8 output where supported.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.mcp import MCPToolset, StdioTransport

# ---------------------------------------------------------------------------
# Model setup — qwen2.5:7b via Ollama (OpenAI-compatible API)
# ---------------------------------------------------------------------------

def build_model() -> OpenAIChatModel:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    model_name = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    provider = OpenAIProvider(
        base_url=base_url,
        api_key="ollama",  # Ollama ignores the key but the field is required
    )
    return OpenAIChatModel(model_name, provider=provider)


# ---------------------------------------------------------------------------
# MCP toolset — launches server.py as a subprocess via stdio transport
# ---------------------------------------------------------------------------

def build_toolset() -> MCPToolset:
    server_path = Path(__file__).parent / "server.py"
    transport = StdioTransport(
        command="python",
        args=[str(server_path)],
        env=dict(os.environ),  # pass current env so .env values reach the server
    )
    return MCPToolset(transport)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are a supply chain disruption analyst. Your job is to assess risk on
shipping routes by synthesizing data from multiple sources.

When given a route (e.g. Shanghai to Rotterdam), follow this process:
1. Use list_major_ports() to identify key waypoints and chokepoints on the route.
2. Check weather at the origin and destination ports.
3. Check vessel traffic density at the major chokepoints.
4. Search for recent disruption news related to the route and key waypoints.
5. Check congestion at the key ports.
6. Synthesize into a structured risk assessment.

Be specific. Cite the data you retrieved. Flag any tool errors clearly rather
than inventing data. If a tool returns an error about a missing API key, note
it as a gap in the assessment rather than treating it as a failure.

Your final answer should have these sections:
- Route Overview (waypoints and chokepoints)
- Active Disruption Signals (what you found — weather, traffic, news, congestion)
- Risk Assessment (overall level: low / moderate / high / critical, with reasoning)
- Recommended Actions (what a logistics planner should do given the current picture)
""".strip()


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

def build_agent(toolset: MCPToolset) -> Agent:
    return Agent(
        model=build_model(),
        toolsets=[toolset],
        system_prompt=SYSTEM_PROMPT,
        model_settings={"temperature": 0.1},  # lower temp = more consistent tool use
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def run_query(query: str) -> str:
    toolset = build_toolset()
    agent = build_agent(toolset)

    print(f"\n{'='*70}")
    print(f"Query: {query}")
    print(f"{'='*70}\n")

    async with toolset:
        result = await agent.run(query)

    return result.data


async def main() -> None:
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = (
            "What disruptions could affect shipments from Shanghai to Rotterdam right now? "
            "Give me a full risk assessment."
        )

    answer = await run_query(query)
    print("\n" + "="*70)
    print("ASSESSMENT")
    print("="*70)
    print(answer)


if __name__ == "__main__":
    asyncio.run(main())
