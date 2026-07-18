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

from pydantic_ai import Agent, UsageLimits
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.mcp import MCPToolset, StdioTransport

# ---------------------------------------------------------------------------
# Model setup — qwen2.5:7b via Ollama (OpenAI-compatible API)
# ---------------------------------------------------------------------------

def build_model() -> OpenAIChatModel:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    model_name = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    provider = OllamaProvider(base_url=base_url)
    # Ollama's OpenAI-compat endpoint silently ignores `max_completion_tokens`
    # (the OpenAI o-series field pydantic-ai maps `max_tokens` to by default)
    # and only honors the legacy `max_tokens` field, so force that mapping.
    profile = OpenAIModelProfile(openai_chat_supports_max_completion_tokens=False)
    return OpenAIChatModel(model_name, provider=provider, profile=profile)


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
1. Use list_major_ports() to identify the chokepoints on the route (e.g. straits,
   canals). This is a reference lookup, not a checklist — do not call other
   tools for every port it returns.
2. Check weather at exactly the origin and destination ports (2 calls total).
3. Check vessel traffic at up to 2 chokepoints directly on the route.
4. Run at most 3 targeted news searches covering the route's chokepoints and
   ports of most concern.
5. Check congestion at exactly the origin port, destination port, and any
   chokepoint ports identified in step 1 — not ports outside the route.
6. Synthesize into a structured risk assessment.

Call each tool at most once per port or query — never repeat an identical
call. Stay within roughly 10-12 tool calls total for a single assessment.

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
        model_settings={
            "temperature": 0.1,  # lower temp = more consistent tool use
            "max_tokens": 1024,  # bounds worst-case generation length if the model loops
            "frequency_penalty": 0.4,  # discourages repeating near-identical tool calls
            "parallel_tool_calls": False,  # one call per turn, not a batch a loop can inflate
        },
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

    tool_calls_limit = int(os.getenv("AGENT_TOOL_CALLS_LIMIT", "20"))

    async with toolset:
        result = await agent.run(
            query,
            usage_limits=UsageLimits(tool_calls_limit=tool_calls_limit),
        )

    return result.output


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
