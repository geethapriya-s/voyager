"""
VoyageReady AI — Pydantic v2 Models
All domain data-structures for trip initialisation
and structured LLM output.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class TripType(str, Enum):
    BUSINESS = "BUSINESS"
    VACATION = "VACATION"


# ─────────────────────────────────────────────────────────────────────────────
# Trip Initialisation
# ─────────────────────────────────────────────────────────────────────────────

class TripConfig(BaseModel):
    """Injected variables that seed the entire agent session."""
    destination: str = Field(..., description="Country / State / City of the trip")
    trip_type: TripType = Field(..., description="BUSINESS or VACATION")
    total_days: int = Field(..., ge=1, le=365, description="Total days until departure")
    current_day: int = Field(1, ge=1, description="Current countdown day (1 = just started)")
    total_budget: float = Field(..., gt=0, description="Total trip budget in the given currency")
    currency_symbol: str = Field("$", description="Currency symbol e.g. $, €, ₹, ¥")

    @field_validator("current_day")
    @classmethod
    def day_within_range(cls, v: int, info: Any) -> int:
        total = info.data.get("total_days")
        if total and v > total:
            raise ValueError(f"current_day ({v}) cannot exceed total_days ({total})")
        return v

    @property
    def days_remaining(self) -> int:
        return self.total_days - self.current_day + 1


# ─────────────────────────────────────────────────────────────────────────────
# MCP Tool Input Schemas (Pydantic = single source of truth)
# ─────────────────────────────────────────────────────────────────────────────

class CheckWeatherInput(BaseModel):
    """Check the weather forecast for a city on a specific date."""
    city: str = Field(description="City name, e.g. 'Tokyo', 'Paris', 'New York'")
    date: str = Field(
        description="Date in YYYY-MM-DD format (forecast up to ~16 days, or historical)",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Agent Response (output format)
# ─────────────────────────────────────────────────────────────────────────────

class LLMMetadata(BaseModel):
    """Metadata from the LLM gateway response — surfaced in the UI."""
    provider: str = ""
    model: str = ""
    reasoning_applied: bool = False
    thinking_text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0


class AgentResponse(BaseModel):
    """
    Top-level structured output from VoyageReady AI.
    Contains the raw markdown response, LLM metadata, and tool call log.
    """
    # Raw markdown string for the complete formatted response
    markdown_output: str = ""
    # LLM call metadata (thinking mode, provider, tokens)
    llm_metadata: LLMMetadata = Field(default_factory=LLMMetadata)
    # MCP tool calls executed during this response
    tool_calls: list[dict] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Conversation / Session state
# ─────────────────────────────────────────────────────────────────────────────

class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class SessionState(BaseModel):
    """Full mutable session — serialisable for Streamlit st.session_state."""
    config: TripConfig
    conversation: list[Message] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def initialise(cls, config: TripConfig) -> "SessionState":
        return cls(config=config)

    def add_user_message(self, text: str) -> None:
        self.conversation.append(Message(role="user", content=text))

    def add_assistant_message(self, text: str) -> None:
        self.conversation.append(Message(role="assistant", content=text))
