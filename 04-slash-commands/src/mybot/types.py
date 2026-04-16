"""types.py -- Shared type definitions used across the project."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypedDict


class Message(TypedDict, total=False):
    """A single conversation turn (user, assistant, system, or tool result)."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    # Present on assistant messages that request a tool call
    tool_calls: list[dict[str, Any]]
    # Present on tool-result messages
    tool_call_id: str
    name: str


@dataclass
class ToolCall:
    """A single tool call requested by the LLM."""

    id: str         # Unique call ID assigned by the LLM provider
    name: str       # Tool name to invoke
    arguments: str  # JSON-encoded argument string
