# Quick links:
System promt validation by claude : https://claude.ai/share/7ba8bfbb-520e-4c80-a9fe-9c79aa24f67c

At first it did qualify only 2/8 criteria. If you scroll down in the above claude chat link, it satisfies all 8/8 criteria after refinment.

{
  "explicit_reasoning": true,
  "structured_output": true,
  "tool_separation": true,
  "conversation_loop": true,
  "instructional_framing": true,
  "internal_self_checks": true,
  "reasoning_type_awareness": true,
  "fallbacks": true,
  "overall_clarity": "Excellent — all nine criteria met, and this version is stronger than the previous one. Two notable upgrades: (1) Today's Date and Departure Date are now explicit in TRIP CONTEXT, giving the model grounded temporal awareness rather than relying on injected day counts alone; (2) the TOOL USE PROTOCOL now includes a Tool-available row with a {tool_docs} injection point, making real tool calls a first-class citizen alongside LOOKUP flags. The instruction 'CALL the tool — never guess when a tool can answer' is a strong anti-hallucination directive. One thing to watch: {tool_docs} must be populated at runtime — if it renders as an empty string, the Tool-available row becomes a dangling instruction with no tools defined, which could confuse the model. Consider adding a fallback note like 'If no tools are available, treat all live data as [LOOKUP]'."
}



# ✈️ VoyageReady AI

**An autonomous Trip Planning Agent — powered by LLM Gateway V2 with Thinking Mode & MCP Tool Execution.**

VoyageReady AI is a Streamlit-based trip planning dashboard that provides personalised itinerary planning, booking guidance, and destination-specific travel advice. It features an **agentic tool-calling loop** — the LLM autonomously decides when to invoke MCP tools (e.g. live weather lookups via Open-Meteo), validates arguments via Pydantic, executes them over MCP stdio, and feeds results back into the conversation. All LLM calls use **thinking mode** (`reasoning="medium"`) for deeper, more thoughtful responses — with zero hardcoded defaults.

---

## 🎯 Features

### 🌍 Intelligent Trip Planning
- **Destination-aware advice** — Itinerary suggestions, restaurant recommendations, and must-see attractions tailored to your specific destination.
- **Trip type adaptation** — Business trips get meeting venues, co-working spaces, and airport lounge tips; Vacation trips get tourist attractions, street food, and adventure activities.
- **Booking guidance** — Flights, hotels, transit passes, eSIMs, and travel insurance recommendations.

### 🌦️ Live Weather via MCP Tool
- **`check_weather(city, date)`** — Real-time weather forecasts (up to 16 days) and historical data via the free [Open-Meteo API](https://open-meteo.com/).
- **Fully autonomous** — The LLM decides when to call the weather tool based on the conversation context.
- **Rich output** — Temperature range, condition (WMO codes → emoji), precipitation, rain probability, wind speed, and UV index.

### 🔧 Agentic Tool-Calling Loop
- **Multi-round execution** — The agent loops up to 5 tool-calling rounds per user message, allowing it to chain multiple tool calls before producing a final response.
- **Pydantic-validated arguments** — Every tool call's arguments are validated against a Pydantic model (`CheckWeatherInput`) before execution, preventing malformed requests.
- **MCP stdio transport** — Tools are executed via the Model Context Protocol over stdio, connecting to `mcp_weather.py` as a subprocess.
- **Tool call transparency** — Every tool call is logged and displayed in the UI with expandable result details.

### 📋 Packing & Preparation
- **Destination-specific packing lists** — Weather-aware, activity-appropriate gear suggestions.
- **Visa & document requirements** — Country-specific entry requirements and paperwork.
- **Local tips** — Best neighbourhoods, transport hacks, safety advice, and cultural customs.

### 🧠 Thinking Mode (LLM Reasoning)
- **Deep reasoning enabled** — All LLM calls use `reasoning="medium"` for richer, more thoughtful responses.
- **No hardcoded defaults** — Every recommendation comes directly from the LLM.
- **Visible thinking** — Click "🧠 View LLM Thinking Process" below any response to see exactly what the model reasoned through before answering.

### 🔍 LLM Thinking & Tool Visibility
- **Thinking text exposed** — The LLM's internal reasoning (`thought: true` parts) is separated from the response and shown in a collapsible purple expander.
- **Tool call expanders** — Each MCP tool invocation is shown with its arguments, result, and success/error status in a collapsible section above the AI response.
- **Per-response metadata badge** — Every AI response shows: thinking mode status, tool call count, provider, model, token counts, and latency.
- **Full transparency** — See the LLM's chain of thought AND the tools it used, not just the final answer.

### 💬 Conversational Interface
- **Natural language chat** — Ask anything about your trip planning needs.
- **Quick-start prompt chips** — One-click prompts: "Plan my first 3 days", "What's the weather like?", "Best neighbourhoods to stay", "Create a packing list".
- **Full conversation history** — Beautifully styled chat bubbles with persistent context.

---

## 🏗️ Architecture

```
Voyager/
├── .env                        # API keys & gateway configuration
├── llm_gatewayV2/              # Multi-provider LLM Gateway (separate service)
│   ├── main.py                 # FastAPI server entry point
│   ├── providers.py            # Provider adapters (Gemini, NVIDIA, Groq, etc.)
│   ├── router.py               # Request routing & failover logic
│   ├── schemas.py              # API request/response schemas
│   ├── cache.py                # Response caching layer
│   ├── db.py                   # SQLite persistence
│   └── client.py               # Python client for the gateway
└── voyager/                    # VoyageReady AI application
    ├── app.py                  # Streamlit UI (sidebar + dashboard + chat)
    ├── agent.py                # Agent core — agentic loop, MCP client, LLM calls
    ├── models.py               # Pydantic v2 domain models & tool input schemas
    ├── mcp_weather.py          # MCP Weather Tool Server (Open-Meteo, stdio)
    └── pyproject.toml          # Project metadata & dependencies
```

### 4 Files, 4 Clear Roles

| File | Role | Calls LLM? | Uses MCP? |
|------|------|:-----------:|:---------:|
| `app.py` | **UI** — Streamlit frontend, sidebar form, metrics, chat, tool call display | ❌ Never | ❌ |
| `agent.py` | **Brain** — System prompt, gateway HTTP call, agentic tool loop, MCP client | ✅ **Only here** | ✅ Client |
| `models.py` | **Data** — Pydantic v2 schemas, tool input models, session state | ❌ Never | ❌ |
| `mcp_weather.py` | **Tool Server** — Exposes `check_weather` via FastMCP over stdio | ❌ Never | ✅ Server |

### Request Flow

```
User types message
       │
       ▼
  app.py ──── ag.chat(state, msg) ────► agent.py
                                            │
                                  ┌─────────┴──────────┐
                                  │  Agentic Loop       │
                                  │  (up to 5 rounds)   │
                                  │                     │
                                  │  1. _call_gateway() │
                                  │     reasoning="medium"
                                  │     POST /v1/chat ──────► llm_gatewayV2
                                  │                              │
                                  │                         failover chain
                                  │                         Gemini → NVIDIA → Groq → …
                                  │                              │
                                  │  2. Tool call?  ◄────────────┘
                                  │     │ YES                │ NO
                                  │     ▼                    ▼
                                  │  _validate_tool_args()   break → final response
                                  │  (Pydantic validation)
                                  │     │
                                  │     ▼
                                  │  _execute_tool_sync()
                                  │     │
                                  │     ▼
                                  │  MCP stdio ──────► mcp_weather.py
                                  │     │               (Open-Meteo API)
                                  │     ▼
                                  │  Append tool result
                                  │  to messages → loop
                                  └─────────────────────┘
                                            │
       ◄────────────────────────────────────┘
  Renders markdown in chat bubble
  Shows tool call expanders
  Updates dashboard metrics
```

---

## 📦 Tech Stack

| Layer              | Technology                                     |
|--------------------|-------------------------------------------------|
| **Frontend**       | Streamlit (dark glassmorphism theme)             |
| **Agent Core**     | Python 3.12+, Pydantic v2, httpx                |
| **Tool Protocol**  | MCP (Model Context Protocol) over stdio          |
| **Tool Server**    | FastMCP (`mcp_weather.py`)                       |
| **Weather API**    | Open-Meteo (free, no API key required)           |
| **LLM Gateway**    | FastAPI, multi-provider failover                 |
| **LLM Reasoning**  | Thinking mode (`reasoning="medium"`)             |
| **LLM Providers**  | Gemini, NVIDIA, Groq, Cerebras, OpenRouter, GitHub Models |
| **Styling**        | Custom CSS (Inter + Sora fonts, glassmorphism)   |

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.12+**
- **uv** (recommended) or **pip** for dependency management
- At least one valid LLM API key (see [Configuration](#%EF%B8%8F-configuration))

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Voyager
```

### 2. Configure Environment Variables

Copy or edit the `.env` file in the project root:

```env
# Required — at least one provider key must be valid
GEMINI_API_KEY=your-gemini-key
GEMINI_MODEL=gemini-2.5-flash

NVIDIA_API_KEY=your-nvidia-key
NVIDIA_MODEL=deepseek-ai/deepseek-v4-pro

# Optional additional providers
GROQ_API_KEY=your-groq-key
GROQ_MODEL=llama-3.3-70b-versatile

CEREBRAS_API_KEY=your-cerebras-key
CEREBRAS_MODEL=qwen-3-235b-a22b-instruct-2507

OPEN_ROUTER_API_KEY=your-openrouter-key
OPENROUTER_MODEL=nvidia/nemotron-3-super-120b-a12b:free

GITHUB_ACCESS_TOKEN=your-github-token
GITHUB_MODEL=openai/gpt-4.1-mini

# Provider priority order (failover chain)
LLM_ORDER=gemini,nvidia,groq,cerebras,openrouter,github

# Gateway port
GATEWAY_PORT=8100
```

### 3. Install Dependencies

**Using uv (recommended):**

```bash
# Install llm_gatewayV2 dependencies
cd llm_gatewayV2
uv sync
cd ..

# Install voyager dependencies
cd voyager
uv sync
cd ..
```

**Using pip:**

```bash
pip install -r llm_gatewayV2/requirements.txt
pip install httpx pydantic python-dotenv streamlit "mcp[cli]"
```

### 4. Start the LLM Gateway

```bash
cd llm_gatewayV2
uv run python main.py
# or: python main.py
```

The gateway will start on `http://localhost:8100`. Verify it's running:

```bash
curl http://localhost:8100/health
```

### 5. Launch VoyageReady AI

In a **new terminal**:

```bash
cd voyager
uv run streamlit run app.py
# or: streamlit run app.py
```

The dashboard will open at `http://localhost:8501`.

---

## 🎮 Usage

1. **Configure your trip** in the sidebar:
   - Destination (e.g., "Tokyo, Japan")
   - Trip type (Business / Vacation)
   - Days until departure & current countdown day
   - Total budget & currency

2. **Click "🚀 Initialise Trip"** to start your session.

3. **Chat with the agent** using the chat input or quick-start prompt chips:
   - *"Plan my first 3 days"*
   - *"What's the weather like?"*
   - *"Best neighbourhoods to stay"*
   - *"Create a packing list"*

4. **Watch the agent work** — when the LLM decides it needs live data (e.g. weather), you'll see:
   - 🔧 **Tool call expanders** showing the function name, arguments, and result
   - 🧠 **Thinking process** revealing the LLM's chain-of-thought reasoning
   - 📡 **Metadata badges** with provider, model, tokens, and latency

---

## 🧩 Pydantic Domain Models

The application is built on Pydantic v2 models in `models.py`:

| Model              | Purpose                                              |
|--------------------|------------------------------------------------------|
| `TripConfig`       | Onboarding variables — destination, budget, trip type, days, currency |
| `CheckWeatherInput` | MCP tool input schema — city + date with regex validation |
| `LLMMetadata`      | Provider, model, reasoning_applied, thinking text, tokens, latency |
| `AgentResponse`    | Top-level output: markdown + LLM metadata + tool call log |
| `Message`          | Single conversation message (role + content)          |
| `SessionState`     | Full mutable session — config + conversation history  |

### Tool Registry (Pydantic-Driven)

Tools are registered in `agent.py` via a simple mapping from tool name → Pydantic model:

```python
TOOL_REGISTRY: dict[str, Type[BaseModel]] = {
    "check_weather": CheckWeatherInput,
}
```

This single registry drives:
- **Schema generation** — `model_json_schema()` produces the tool definition for the LLM
- **Argument validation** — `model_validate()` catches malformed LLM arguments before execution
- **Documentation** — Docstrings and field descriptions are injected into the system prompt automatically via `_build_tool_docs()`

To add a new tool: define a Pydantic model in `models.py`, add it to `TOOL_REGISTRY` in `agent.py`, and implement the handler in `mcp_weather.py` (or a new MCP server).

---

## 🧠 System Prompt Design

The system prompt in `agent.py` (`_build_system_prompt()`) follows a structured design with 8 key sections:

| Section | Purpose |
|---------|---------|
| **Trip Context** | Injects live session variables (destination, budget, dates, departure countdown) |
| **Reasoning Protocol** | Forces step-by-step thinking with labelled reasoning tags (`[BUDGET]`, `[TIMING]`, `[TRIP_TYPE]`, `[LOCAL_INSIGHT]`, `[LOOKUP]`) |
| **Capabilities** | Defines the 5 capability areas (itinerary, booking, packing, local tips, trip type adaptation) |
| **Tool Use Protocol** | Classifies information types (static knowledge, live/time-sensitive, tool-available, calculations) and enforces tool use when available |
| **Available Tools** | Auto-generated from Pydantic models — signatures, descriptions, and usage rules |
| **Output Format** | Mandates structured sections: Reasoning Summary → Recommendations → Budget Check → Items to Verify → What Would Change |
| **Multi-Turn Loop** | Handles follow-up messages, refinements, and confirmed decisions across conversation turns |
| **Self-Verification** | Pre-response checklist: budget fit, timing feasibility, trip type consistency, lookup flagging |

---

## ⚙️ Configuration

### LLM Gateway

The gateway supports **automatic failover** across multiple providers. Configure the priority order via `LLM_ORDER` in `.env`. If the first provider fails, the gateway automatically tries the next one.

### MCP Weather Server

The weather tool (`mcp_weather.py`) runs as a subprocess via MCP stdio transport. It requires **no API keys** — it uses the free Open-Meteo API for:
- **Forecast data** — Up to ~16 days ahead
- **Historical data** — Automatic fallback to the archive API for past dates
- **Geocoding** — City name → lat/lon resolution via Open-Meteo's geocoding endpoint

### Agent Configuration

| Parameter | Default | Location |
|-----------|---------|----------|
| `MAX_TOOL_ROUNDS` | 5 | `agent.py` |
| `GATEWAY_URL` | `http://localhost:8100` | `.env` / `agent.py` |
| `temperature` | 0.75 | `agent.py` |
| `max_tokens` | 2048 | `agent.py` |
| `reasoning` | `"medium"` | `agent.py` |

---

## 🛠️ Development

### Project Structure

- **`models.py`** — All Pydantic models + tool input schemas. Edit here to add new tool inputs or extend the data schema.
- **`agent.py`** — Agent orchestration with thinking mode and MCP tool loop. The ONLY file that calls the LLM.
- **`app.py`** — Streamlit UI. Adjust layout, styling, or add new dashboard panels.
- **`mcp_weather.py`** — MCP tool server. Add new `@mcp.tool()` functions here for additional tools.

### Adding a New MCP Tool

1. **Define the input schema** in `models.py`:
   ```python
   class SearchFlightsInput(BaseModel):
       """Search for flight options between two cities."""
       origin: str = Field(description="Departure city")
       destination: str = Field(description="Arrival city")
       date: str = Field(description="Travel date YYYY-MM-DD")
   ```

2. **Register it** in `agent.py`:
   ```python
   TOOL_REGISTRY["search_flights"] = SearchFlightsInput
   ```

3. **Implement the handler** in `mcp_weather.py` (or a new server):
   ```python
   @mcp.tool()
   async def search_flights(origin: str, destination: str, date: str) -> str:
       # ... implementation
   ```

### Running Tests

```bash
cd voyager
uv run pytest
```

---

## 📄 License

This project is part of the EAG V3 coursework (Assignment 5).

---

<p align="center">
  Built with ❤️ using Streamlit, Pydantic v2, MCP & LLM Gateway V2
</p>
