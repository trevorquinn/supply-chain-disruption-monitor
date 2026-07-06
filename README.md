# Supply Chain Disruption Monitor

An MCP server exposing supply chain intelligence tools, with a PydanticAI agent that synthesizes them to answer disruption questions.

**Demo scenario:** *"What disruptions could affect shipments from Shanghai to Rotterdam right now?"*

The agent calls multiple tools, synthesizes the results, and produces a structured risk assessment — demonstrating that the value is in the reasoning across sources, not any single data lookup.

Built as a self-training project and portfolio artifact.

---

## Tech stack

| Layer | Choice | Notes |
|---|---|---|
| MCP server | Python MCP SDK (`mcp`) | FastMCP decorator API, stdio transport |
| Agent framework | PydanticAI | `MCPToolset` + `StdioTransport` to wire agent → server |
| LLM | qwen2.5:7b via Ollama | Local, reliable tool calling |
| Vessel data | AISStream.io | Free WebSocket AIS feed |
| Weather | Open-Meteo | Free, no API key |
| News | NewsAPI | Free tier (100 req/day) |
| Port congestion | Mocked | Realistic synthetic data |

---

## Setup

### 1. Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — `pip install uv` or `brew install uv`
- [Ollama](https://ollama.com/) — for the local LLM

### 2. Install dependencies

```bash
cd supply-chain-disruption-monitor
uv sync
```

### 3. Pull the model

```bash
ollama pull qwen2.5:7b
```

### 4. Configure API keys

```bash
cp .env.example .env
```

Edit `.env` and fill in:

- **AISSTREAM_API_KEY** — Free at [aisstream.io](https://aisstream.io/). Provides real-time vessel positions via WebSocket AIS feed.
- **NEWS_API_KEY** — Free at [newsapi.org](https://newsapi.org/). 100 requests/day on the free tier.

The weather tool (Open-Meteo) needs no key.

---

## Running

### MCP server (standalone — for development / MCP Inspector)

```bash
uv run mcp dev server.py
```

This opens the MCP Inspector in your browser so you can call tools interactively.

### Agent only

> **Note:** `agent.py` is a sample **MCP client**, not part of the server itself. It plays the same role Claude Desktop, Codex, or any other MCP client would — it launches `server.py` over stdio, runs the agent loop against a local model (Ollama), and synthesizes the tool results. The server is the deliverable; the agent is just one interchangeable consumer of it. It imports nothing from `server.py` and talks to it purely over the MCP protocol, so you can swap in any other MCP client without touching the server.

```bash
# Default query: Shanghai to Rotterdam risk assessment
uv run agent.py

# Custom query
uv run agent.py "What risks affect container ships transiting the Red Sea?"
```

### Full demo (tool outputs + agent synthesis)

```bash
uv run demo.py              # tools + agent
uv run demo.py --tools-only # just raw tool outputs
uv run demo.py --agent-only # just the agent synthesis
```

---

## MCP tools

| Tool | Source | Returns |
|---|---|---|
| `list_major_ports(region)` | Static | Major ports by region — use this first to identify route waypoints |
| `get_port_weather(port_name)` | Open-Meteo | Current conditions + 24h forecast, wind speed in knots, operational impact |
| `get_vessel_positions(region)` | AISStream.io | Live vessel snapshot: MMSI, name, position, speed, nav status |
| `search_disruption_news(query, days)` | NewsAPI | Recent headlines + high-signal flag (strikes, attacks, blockages) |
| `get_port_congestion(port_name)` | Mocked | Utilization %, queue depth, wait hours, trend, advisory |

The agent synthesizes across all five — there is no single `assess_route_risk` tool. The multi-tool reasoning is the point.

---

## Add this server to Claude Desktop

Add to your Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "supply-chain-monitor": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/supply-chain-disruption-monitor", "python", "server.py"],
      "env": {
        "AISSTREAM_API_KEY": "your_key_here",
        "NEWS_API_KEY": "your_key_here"
      }
    }
  }
}
```

---

## Project structure

```
supply-chain-disruption-monitor/
├── server.py           # FastMCP server — all 5 tools
├── agent.py            # Sample MCP client (PydanticAI) — interchangeable with Claude Desktop, Codex, etc.
├── demo.py             # Demo script (tool outputs + agent synthesis)
├── tools/
│   ├── ports.py        # Static port data + coordinates (27 major ports)
│   ├── weather.py      # Open-Meteo integration
│   ├── vessels.py      # AISStream.io WebSocket integration
│   ├── news.py         # NewsAPI integration
│   └── congestion.py   # Mocked port congestion (realistic synthetic data)
├── pyproject.toml
├── .env.example
└── README.md
```

---

## Design notes

**Why mock port congestion?** Live data (MarineTraffic, FreightWaves) requires enterprise subscriptions (£100+/month). Mocking gives full demo control — a "Shanghai congestion spike" can be shown without paywall friction. The tool interface is identical to what a real API would return.

**Why AISStream.io?** It's a free, real-time WebSocket AIS feed. A vessel actually moving through the South China Sea is a better demo moment than a static mock.

**Why qwen2.5:7b?** Reliable tool-calling behavior at a size that runs well on consumer hardware (16 GB RAM). Swap in any model with Ollama support by changing `OLLAMA_MODEL` in `.env`.

**Why PydanticAI?** PydanticAI co-maintains the official Python MCP SDK, so using their stack is thematically coherent. `MCPServerStdio` is the native path for agent → MCP server wiring.
