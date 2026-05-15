"""
VoyageReady AI — Agent Core
Autonomous Trip Planning Agent with MCP tool support.
Calls the local llm_gatewayV2 REST API with thinking mode enabled.
Tool schemas derived from Pydantic models; executed via MCP.
"""
from __future__ import annotations
from datetime import date, timedelta

import asyncio
import json
import sys
import os
import uuid
from pathlib import Path
from typing import Optional, Type

import httpx
from pydantic import BaseModel

# ── Add llm_gatewayV2 client to path ────────────────────────────────────────
GATEWAY_DIR = Path(__file__).parent.parent / "llm_gatewayV2"
sys.path.insert(0, str(GATEWAY_DIR))

from models import (
    AgentResponse, CheckWeatherInput, LLMMetadata, Message,
    SessionState, TripConfig, TripType,
)

GATEWAY_URL = os.getenv("LLM_GATEWAY_V2_URL", "http://localhost:8100")
MCP_SERVER_PATH = Path(__file__).parent / "mcp_weather.py"
MAX_TOOL_ROUNDS = 5  # Safety limit for tool-calling loop


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic-driven Tool Registry
# ─────────────────────────────────────────────────────────────────────────────
# Add new tools here: Pydantic model → (name, execute via MCP)
# Everything else (schema, docs, validation) is derived automatically.

TOOL_REGISTRY: dict[str, Type[BaseModel]] = {
    "check_weather": CheckWeatherInput,
}


def _get_tool_defs() -> list[dict]:
    """Derive tool definitions for the LLM gateway from Pydantic models."""
    defs = []
    for name, model_cls in TOOL_REGISTRY.items():
        defs.append({
            "name": name,
            "description": (model_cls.__doc__ or "").strip(),
            "input_schema": model_cls.model_json_schema(),
        })
    return defs


def _validate_tool_args(tool_name: str, raw_args: dict) -> dict:
    """Validate LLM-generated arguments against the Pydantic model."""
    model_cls = TOOL_REGISTRY.get(tool_name)
    if model_cls is None:
        raise ValueError(f"Unknown tool: {tool_name}")
    validated = model_cls.model_validate(raw_args)
    return validated.model_dump()


def _build_tool_docs(tools: list[dict]) -> str:
    """Dynamically generate tool documentation from MCP-discovered tool schemas."""
    if not tools:
        return ""

    lines = [
        "## AVAILABLE TOOLS",
        "You have the following tools available. **Always prefer calling a tool**",
        "over guessing when the tool can provide accurate data.\n",
    ]
    for tool in tools:
        name = tool["name"]
        desc = tool.get("description", "").strip().split("\n")[0]  # First line
        schema = tool.get("input_schema", {})
        props = schema.get("properties", {})
        required = schema.get("required", [])

        # Build signature: tool_name(param1: type, param2: type)
        params = []
        for pname, pinfo in props.items():
            ptype = pinfo.get("type", "string")
            req = " *(required)*" if pname in required else ""
            params.append(f"{pname}: {ptype}{req}")
        signature = f"`{name}({', '.join(params)})`"

        lines.append(f"- **{signature}** — {desc}")

    lines.append("")
    lines.append("**Rules for tool use:**")
    lines.append("- When a tool can answer the question, **CALL IT** — never guess.")
    lines.append("- If the tool returns an error, report it and suggest alternatives.")
    lines.append("- Clearly distinguish tool-sourced data from your training knowledge.")
    return "\n".join(lines)


def _build_system_prompt(state: SessionState, tools: list[dict] | None = None) -> str:
    cfg = state.config
    tool_docs = _build_tool_docs(tools or [])
    today = date.today()
    departure_date = today + timedelta(days=cfg.days_remaining)

    return f"""You are **VoyageReady AI** — an autonomous Trip Planning Agent.
You help travellers plan every detail of their upcoming trip.

## TRIP CONTEXT
- Today's Date       : {today.isoformat()}
- Destination        : {cfg.destination}
- Trip Type          : {cfg.trip_type.value}
- Departure Date     : {departure_date.isoformat()} ({cfg.days_remaining} days from now)
- Departure Countdown: Day {cfg.current_day} of {cfg.total_days}
- Total Budget       : {cfg.currency_symbol}{cfg.total_budget:,.2f}

---

## REASONING PROTOCOL
Before producing any output, think step-by-step through the following:
1. What does the traveller's **trip type** imply about priorities (pace, formality, activities)?
2. How does the **remaining time** affect what is still actionable vs. too late to book?
3. What is the **budget envelope** per day, and which categories (accommodation, food, transport, activities) should absorb it?
4. For each recommendation, identify the reasoning type driving it:
   - `[BUDGET]` — chosen because it fits the financial constraint
   - `[TIMING]` — chosen because it suits the days remaining or day-of schedule
   - `[TRIP_TYPE]` — chosen because it matches BUSINESS or VACATION context
   - `[LOCAL_INSIGHT]` — chosen based on destination-specific knowledge
   - `[LOOKUP]` — requires live data (prices, availability, weather); flag for verification

Label each recommendation with one or more of these tags inline.

---

## YOUR CAPABILITIES
1. **Itinerary Planning** — Suggest day-by-day activities, must-see attractions, restaurant recommendations.
2. **Booking Guidance** — Advise on flights, hotels, transit passes, eSIMs, travel insurance.
3. **Packing & Preparation** — Provide destination-specific packing lists, visa/document requirements, weather forecasts.
4. **Local Tips** — Share insider knowledge: best neighbourhoods, transport hacks, safety advice, local customs.
5. **Trip Type Adaptation**:
   - BUSINESS → meeting venues, co-working spaces, formal dining, airport lounges.
   - VACATION → tourist attractions, street food, adventure activities, nightlife.

---

## TOOL USE PROTOCOL
Classify every piece of information before using it:

| Type                  | Source                          | Action                                                              |
|-----------------------|---------------------------------|---------------------------------------------------------------------|
| Static knowledge      | Your training data              | Reason and respond directly                                         |
| Live / time-sensitive | Prices, weather, availability   | Flag as `[LOOKUP]` and instruct user to verify or trigger web search |
| **Tool-available**    | See AVAILABLE TOOLS below       | **CALL the tool** — never guess when a tool can answer              |
| Calculations          | Budget math, day counts         | Compute explicitly, show your working                               |

{tool_docs}

Never blend live data with static knowledge without clearly distinguishing them.

---

## OUTPUT FORMAT
Always structure your response as follows:

### 🧠 Reasoning Summary
[2–4 sentences explaining how you weighted trip type, budget, and timing before producing recommendations]

### ✅ Recommendations
[Markdown sections per capability area, each item tagged with reasoning labels]

### 💰 Budget Check
[Itemised estimated spend vs. total budget — show arithmetic]

### ⚠️ Items to Verify
[List any [LOOKUP] items the traveller must confirm independently]

### 🔄 What Would Change This Plan
[State 1–3 assumptions; tell the user what to say to trigger an update]

---

## MULTI-TURN LOOP SUPPORT
This is an ongoing planning session. On every follow-up turn:
- If the user **refines a preference**, update only the affected section and explicitly note: *"Updated: [section] because [reason]."*
- If the user **provides new information** (e.g. confirmed a booking, changed budget), incorporate it and recalculate the Budget Check.
- Carry forward all confirmed decisions from earlier turns as immutable context unless the user explicitly changes them.

---

## SELF-VERIFICATION CHECKLIST
Before finalising any response, verify:
- [ ] Total estimated spend ≤ {cfg.currency_symbol}{cfg.total_budget:,.2f}
- [ ] All time-sensitive recommendations are feasible within {cfg.days_remaining} days remaining
- [ ] BUSINESS vs. VACATION framing is consistently applied throughout
- [ ] No recommendation contradicts a decision confirmed in a prior turn
- [ ] All `[LOOKUP]` items are listed in the "Items to Verify" section

If any check fails, revise the relevant section before responding.

---

## ERROR HANDLING & FALLBACKS
- **Uncertain information**: State your confidence level explicitly (e.g., *"As of my last update, this costs approximately X — verify before booking"*).
- **Unknown or niche destination**: Say so clearly. Provide the best available reasoning and flag the entire response as lower-confidence.
- **Budget conflict**: If recommendations cannot fit within budget, present a tiered plan (Essential / Optional / Splurge) rather than exceeding the limit silently.
- **Conflicting constraints**: Surface the conflict explicitly and ask the user to resolve it before proceeding.
- **Tool or data failure**: If a lookup cannot be completed, note the gap and suggest a direct source (e.g., the airline's website, Google Hotels).

---

## RULES
- Always be specific to {cfg.destination}. Never give generic advice.
- Prioritise actionable recommendations with concrete names, estimated prices, and links where possible.
- Show your reasoning — don't just state conclusions.
- When in doubt, ask one clarifying question rather than assume.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Gateway call helper
# ─────────────────────────────────────────────────────────────────────────────

def _call_gateway(
    messages: list[dict],
    system: str,
    tools: Optional[list[dict]] = None,
    response_format: Optional[dict] = None,
    temperature: float = 0.75,
    max_tokens: int = 2048,
    reasoning: str = "medium",
) -> dict:
    """Synchronous HTTP call to llm_gatewayV2 /v1/chat with thinking mode."""
    body: dict = {
        "messages": messages,
        "system": system,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
        "reasoning": reasoning,
    }
    if tools:
        body["tools"] = tools
    if response_format:
        body["response_format"] = response_format

    resp = httpx.post(
        f"{GATEWAY_URL}/v1/chat",
        json=body,
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()


# ─────────────────────────────────────────────────────────────────────────────
# MCP client — connect to weather server and execute tools
# ─────────────────────────────────────────────────────────────────────────────

async def _execute_mcp_tool(tool_name: str, arguments: dict) -> str:
    """Connect to MCP server and execute a single tool call."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(MCP_SERVER_PATH)],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)

            # Extract text from the result
            parts = []
            for content in result.content:
                if hasattr(content, "text"):
                    parts.append(content.text)
            return "\n".join(parts) if parts else str(result)


def _execute_tool_sync(tool_name: str, arguments: dict) -> str:
    """Sync wrapper for executing an MCP tool."""
    return asyncio.run(_execute_mcp_tool(tool_name, arguments))


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def chat(state: SessionState, user_message: str) -> AgentResponse:
    """
    Main entry point. Accepts a user message, calls the LLM gateway
    with thinking mode and MCP tools, and returns the trip planning response.
    Implements an agentic tool-calling loop.
    """
    # 1. Build conversation messages for the gateway
    gateway_msgs: list[dict] = [
        {"role": m.role, "content": m.content}
        for m in state.conversation
        if m.role != "system"
    ]
    gateway_msgs.append({"role": "user", "content": user_message})

    # 2. Derive tool definitions from Pydantic models (no runtime MCP discovery)
    tool_defs = _get_tool_defs()

    # 3. Build system prompt with Pydantic-derived tool docs
    system_prompt = _build_system_prompt(state, tools=tool_defs)

    # 4. Agentic tool-calling loop
    tool_calls_log: list[dict] = []  # For UI display
    final_result = None
    all_thinking_parts: list[str] = []  # Accumulate thinking text across rounds
    all_text_parts: list[str] = []      # Accumulate response text across rounds

    for round_num in range(MAX_TOOL_ROUNDS):
        result = _call_gateway(
            messages=gateway_msgs,
            system=system_prompt,
            tools=tool_defs if tool_defs else None,
            temperature=0.75,
            max_tokens=2048,
            reasoning="medium",
        )
        final_result = result

        # Preserve thinking text from every round (it's often only in the first)
        round_thinking = result.get("thinking_text", "")
        if round_thinking:
            all_thinking_parts.append(round_thinking)

        # Preserve response text from every round (LLM may produce content
        # alongside tool calls, e.g. a packing list before calling check_weather)
        round_text = result.get("text", "")
        if round_text:
            all_text_parts.append(round_text)

        # If no tool calls, we're done
        if result.get("stop_reason") != "tool_use" or not result.get("tool_calls"):
            break

        # 5. Execute each tool call: validate with Pydantic, then run via MCP
        assistant_msg = {
            "role": "assistant",
            "content": result.get("text", ""),
            "tool_calls": result["tool_calls"],
        }
        gateway_msgs.append(assistant_msg)

        for tc in result["tool_calls"]:
            tool_name = tc["name"]
            raw_args = tc.get("arguments", {})
            tool_id = tc.get("id", f"call_{uuid.uuid4().hex[:8]}")

            try:
                # Validate with Pydantic before execution
                validated_args = _validate_tool_args(tool_name, raw_args)
                # Execute via MCP
                tool_result = _execute_tool_sync(tool_name, validated_args)
                tool_calls_log.append({
                    "tool": tool_name,
                    "args": validated_args,
                    "result": tool_result,
                    "status": "success",
                })
            except Exception as e:
                tool_result = f"Error calling {tool_name}: {e}"
                tool_calls_log.append({
                    "tool": tool_name,
                    "args": raw_args,
                    "result": tool_result,
                    "status": "error",
                })

            # Append tool result for the next LLM round
            gateway_msgs.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "tool_name": tool_name,
                "content": tool_result,
            })

    # 5. Extract final response — combine text from ALL rounds
    assistant_text = "\n\n".join(all_text_parts) if all_text_parts else ""

    # 6. Capture LLM metadata
    combined_thinking = "\n\n---\n\n".join(all_thinking_parts) if all_thinking_parts else ""
    metadata = LLMMetadata(
        provider=final_result.get("provider", "") if final_result else "",
        model=final_result.get("model", "") if final_result else "",
        reasoning_applied=final_result.get("reasoning_applied", False) if final_result else False,
        thinking_text=combined_thinking,
        input_tokens=final_result.get("input_tokens", 0) if final_result else 0,
        output_tokens=final_result.get("output_tokens", 0) if final_result else 0,
        latency_ms=final_result.get("latency_ms", 0) if final_result else 0,
    )

    # 7. Update session conversation
    state.add_user_message(user_message)
    state.add_assistant_message(assistant_text)

    return AgentResponse(
        markdown_output=assistant_text,
        llm_metadata=metadata,
        tool_calls=tool_calls_log,
    )
