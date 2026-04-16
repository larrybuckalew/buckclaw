"""
tools/base.py — Abstract base class for all agent tools.

A tool has three things:
  name        — unique identifier used in LLM function-call JSON.
  description — plain-English explanation shown to the LLM.
  parameters  — JSON Schema dict describing the tool's arguments.

The LLM decides *which* tool to call and *what arguments* to pass;
the tool's execute() method then runs the actual logic.

Design notes
────────────
• execute() is async so tools can do I/O (disk, network, subprocess)
  without blocking the event loop.
• We pass the full AgentSession into execute() so advanced tools can
  read conversation state, spawn sub-sessions, etc. (used in step 15).
• get_tool_schema() produces the OpenAI-compatible function-call JSON
  that LiteLLM forwards to whichever LLM provider is configured.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mybot.core.agent import AgentSession


class BaseTool(ABC):
    """Contract that every tool must satisfy."""

    name: str
    description: str
    parameters: dict[str, Any]

    @abstractmethod
    async def execute(self, session: "AgentSession", **kwargs: Any) -> str:
        """
        Run the tool and return a plain-text result.

        The result is added to the conversation history as a
        tool-result message so the LLM can reason about it.
        """

    def get_tool_schema(self) -> dict[str, Any]:
        """Return the OpenAI function-call schema for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
