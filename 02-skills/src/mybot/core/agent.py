"""
core/agent.py — Agent blueprint + stateful session with tool-calling loop.

Changes from Step 00
────────────────────
• AgentSession now accepts a ToolRegistry.
• chat() loops: after each LLM call it checks for tool_calls; if present it
  executes them, appends the results, and calls the LLM again.  The loop
  exits when the LLM returns with no pending tool calls ("end_turn").

Tool-calling flow
─────────────────
  User message
      │
      ▼
  LLM call ──► tool_calls? ──Yes──► execute tools
      │                                    │
      │◄───────────────────────────────────┘
      │
      ▼ (no tool calls)
  Final reply returned to user

Design notes
────────────
• Tool results are stored as "tool" role messages so the LLM can refer
  back to them in subsequent turns.
• A MAX_TOOL_ROUNDS guard prevents infinite loops (e.g. if a buggy tool
  always returns an error that prompts another tool call).
• Agent is still intentionally thin (no mutable state).
"""

from __future__ import annotations

from mybot.core.state import ConversationState
from mybot.provider.llm.base import LLMProvider
from mybot.tools.registry import ToolRegistry
from mybot.types import Message, ToolCall

MAX_TOOL_ROUNDS = 10  # safety limit on consecutive tool calls


class Agent:
    """
    Immutable blueprint for an agent.

    Holds the LLM provider reference, the agent's display name,
    and the system prompt that defines its personality / capabilities.
    """

    def __init__(
        self,
        llm: LLMProvider,
        name: str,
        system_prompt: str,
    ) -> None:
        self.llm = llm
        self.name = name
        self.system_prompt = system_prompt


class AgentSession:
    """
    A single, stateful conversation with an agent.

    Each call to chat() drives the tool-calling loop until the LLM
    produces a final text response.
    """

    def __init__(self, agent: Agent, tools: ToolRegistry | None = None) -> None:
        self.agent = agent
        self.state = ConversationState(agent.system_prompt)
        self.tools = tools or ToolRegistry()

    # ── Public API ────────────────────────────────────────────────