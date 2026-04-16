"""
core/agent.py -- Agent blueprint + stateful session with tool-calling loop + persistence.

Changes from Step 04
────────────────────
• AgentSession.__init__ now accepts optional context_guard.
• context_guard is stored and used in the chat() loop.
• Before each LLM call, check_and_compact() is called to manage context size.

Changes from Step 03
────────────────────
• AgentSession.__init__ now accepts optional command_registry.
• command_registry is stored and made available to slash commands.

Changes from Step 02
────────────────────
• AgentSession.__init__ now accepts optional history_store and session_meta.
• chat() now calls _save_to_history() after appending user and assistant messages.
• New _save_to_history() method saves messages to the HistoryStore if configured.

Tool-calling flow
─────────────────
  User message
      │
      ├──► Save to history
      │
      ├──► Check context size / compact if needed
      │
      ▼
  LLM call ──► tool_calls? ──Yes──► execute tools
      │                                    │
      │◄───────────────────────────────────┘
      │
      ▼ (no tool calls)
  Final reply
      │
      ├──► Save to history
      │
      ▼
  Returned to user

Design notes
────────────
• Tool results are stored as "tool" role messages so the LLM can refer
  back to them in subsequent turns.
• A MAX_TOOL_ROUNDS guard prevents infinite loops (e.g. if a buggy tool
  always returns an error that prompts another tool call).
• Agent is still intentionally thin (no mutable state).
• History persistence is optional -- pass history_store=None to disable.
• Slash commands are dispatched before reaching the LLM, so they do not
  appear in the conversation history or affect the LLM's context.
• Context compaction is optional -- pass context_guard=None to disable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mybot.core.context_guard import ContextGuard
from mybot.core.history import HistoryStore, SessionMeta
from mybot.core.state import ConversationState
from mybot.provider.llm.base import LLMProvider
from mybot.tools.registry import ToolRegistry
from mybot.types import Message, ToolCall

if TYPE_CHECKING:
    from mybot.core.commands import CommandRegistry

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
    produces a final text response. Messages are optionally saved
    to persistent storage via HistoryStore. Context size is monitored
    and messages are compacted if needed via ContextGuard.
    """

    def __init__(
        self,
        agent: Agent,
        tools: ToolRegistry | None = None,
        history_store: HistoryStore | None = None,
        session_meta: SessionMeta | None = None,
        command_registry: CommandRegistry | None = None,
        context_guard: ContextGuard | None = None,
    ) -> None:
        self.agent = agent
        self.state = ConversationState(agent.system_prompt)
        self.tools = tools or ToolRegistry()
        self.history_store = history_store
        self.session_meta = session_meta
        self.command_registry = command_registry
        self.context_guard = context_guard or ContextGuard()

    # ── Public API ────────────────────────────────────────────────

    async def chat(self, message: str) -> str:
        """
        Send a user message and get a response.

        Handles the full tool-calling loop and persists messages if
        history_store is configured. Monitors context size and compacts
        if needed via context_guard.
        """
        # 1. Store user message
        user_msg: Message = {"role": "user", "content": message}
        self.state.add_message(user_msg)
        self._save_to_history(user_msg)

        # 2. Tool-calling loop
        tool_round = 0
        while tool_round < MAX_TOOL_ROUNDS:
            # Check context size and compact if needed
            self.state, did_compact = await self.context_guard.check_and_compact(
                self.state, self.agent.llm, self.agent.llm.model
            )
            if did_compact:
                # Context was compacted -- update history if available
                pass

            # Build messages and call LLM
            messages = self.state.build_messages()
            response = await self.agent.llm.chat(messages)

            # Handle response based on its type
            if isinstance(response, tuple):
                content, tool_calls = response
                response = {"content": content, "tool_calls": tool_calls}

            # Check for tool calls
            tool_calls = response.get("tool_calls")
            if not tool_calls:
                # No tools called -- we have our final response
                break

            # Execute tools
            assistant_msg: Message = {
                "role": "assistant",
                "content": response.get("content", ""),
            }
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls

            self.state.add_message(assistant_msg)
            self._save_to_history(assistant_msg)

            # Execute each tool and append results
            for tool_call_dict in tool_calls:
                tool_call = ToolCall(
                    id=tool_call_dict["id"],
                    name=tool_call_dict["name"],
                    arguments=tool_call_dict["arguments"],
                )

                result = await self.tools.execute(tool_call)

                tool_result_msg: Message = {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.name,
                    "content": result,
                }
                self.state.add_message(tool_result_msg)
                self._save_to_history(tool_result_msg)

            tool_round += 1

        # 3. Extract final response text
        # If we broke out due to no tool calls, response has the final text.
        # If we hit MAX_TOOL_ROUNDS, response is the last LLM output.
        final_text = response.get("content", "") if isinstance(response, dict) else str(response)

        # 4. Store final assistant message and return
        assistant_msg: Message = {"role": "assistant", "content": final_text}
        self.state.add_message(assistant_msg)
        self._save_to_history(assistant_msg)

        return final_text

    # ── Private helpers ───────────────────────────────────────────

    def _save_to_history(self, message: Message) -> None:
        """Save a message to the history store if configured."""
        if self.history_store and self.session_meta:
            self.history_store.save_message(self.session_meta.session_id, message)
