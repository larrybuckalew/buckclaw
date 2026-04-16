"""
tools/registry.py — Manages the set of tools available to an agent.

Responsibilities
────────────────
• Stores tools by name for O(1) lookup during execution.
• Produces the list of JSON schemas to send to the LLM.
• Dispatches tool calls: given a name + kwargs, finds the right tool
  and calls execute().

Design notes
────────────
• ToolRegistry is intentionally decoupled from AgentSession; it's created
  once and passed in at construction time.  This makes it easy to give
  different sessions different tool sets (useful in step 11, Multi-Agent).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from mybot.tools.base import BaseTool

if TYPE_CHECKING:
    from mybot.core.agent import AgentSession


class ToolRegistry:
    """Container for all tools available to an agent."""

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        self._tools: dict[str, BaseTool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: BaseTool) -> None:
        """Add a tool to the registry."""
        self._tools[tool.name] = tool

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Return JSON schemas for all registered tools (sent to the LLM)."""
        return [t.get_tool_schema() for t in self._tools.values()]

    async def execute(
        self,
        session: "AgentSession",
        tool_name: str,
        arguments: str | dict[str, Any],
    ) -> str:
        """
        Look up a tool by name and execute it.

        `arguments` can be a JSON string (as returned by the LLM) or a dict.
        Returns the tool's output as a plain string.
        """
        tool = self._tools.get(tool_name)
        if tool is None:
            return f"Unknown tool: '{tool_name}'. Available: {list(self._tools)}"

        if isinstance(arguments, str):
            try:
                kwargs: dict[str, Any] = json.loads(arguments)
            except json.JSONDecodeError as exc:
                return f"Invalid JSON arguments for '{tool_name}': {exc}"
        else:
            kwargs = arguments

        return await tool.execute(session, **kwargs)

    def __len__(self) -> int:
        return len(self._tools)
