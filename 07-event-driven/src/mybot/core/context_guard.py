"""
core/context_guard.py -- Manages context window size and message compaction.

The ContextGuard implements a two-stage strategy for keeping token count under control:
1. Truncate large tool results (first-pass to reduce noise)
2. Summarize entire conversation (if still over threshold)

Design notes
────────────
• Uses litellm.token_counter() to estimate token usage.
• Falls back to len(str(messages)) // 4 if token counting fails.
• token_threshold defaults to 160,000 (80% of Claude's 200k context limit).
• Tool result messages are truncated to 2,000 chars with "[truncated]" marker.
• Compaction creates a new ConversationState with a summary from the LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mybot.core.state import ConversationState
    from mybot.provider.llm.base import LLMProvider

from mybot.types import Message


@dataclass
class ContextGuard:
    """Monitors and manages conversation context size."""

    token_threshold: int = 160_000  # 80% of 200k Claude context
    max_tool_result_chars: int = 2_000

    # ── Public API ────────────────────────────────────────────────────────

    def estimate_tokens(self, state: ConversationState, model: str) -> int:
        """
        Estimate token count for the current conversation.

        Falls back to character-based approximation if token_counter unavailable.
        """
        try:
            from litellm import token_counter

            messages = state.build_messages()
            return token_counter(model=model, messages=messages)
        except Exception:
            # Fallback: rough approximation (1 token ~ 4 chars)
            messages_str = str(state.build_messages())
            return len(messages_str) // 4

    async def check_and_compact(
        self,
        state: ConversationState,
        llm: LLMProvider,
        model: str,
    ) -> tuple[ConversationState, bool]:
        """
        Check context size and compact if needed.

        Returns:
            (updated_state, did_compact)
            - If under threshold: returns original state, False
            - If truncation reduces below threshold: returns truncated state, False
            - If still over after truncation: returns compacted state, True
        """
        # 1. Check initial token count
        token_count = self.estimate_tokens(state, model)
        if token_count < self.token_threshold:
            return state, False

        # 2. Try truncating large tool results
        truncated_state = self._truncate_large_tool_results_inplace(state)
        token_count = self.estimate_tokens(truncated_state, model)
        if token_count < self.token_threshold:
            return truncated_state, False

        # 3. Still over -- compact the conversation
        compacted_state = await self._compact_messages(
            truncated_state, llm, model
        )
        return compacted_state, True

    # ── Private helpers ───────────────────────────────────────────────────

    def _truncate_large_tool_results_inplace(
        self, state: ConversationState
    ) -> ConversationState:
        """
        Truncate tool result messages that exceed max_tool_result_chars.

        Returns a new ConversationState with truncated messages.
        """
        from mybot.core.state import ConversationState

        new_state = ConversationState(state.system_prompt)

        for msg in state._messages:
            if (
                msg.get("role") == "tool"
                and len(msg.get("content", "")) > self.max_tool_result_chars
            ):
                # Truncate and mark
                truncated_msg = msg.copy()
                truncated_msg["content"] = (
                    msg["content"][: self.max_tool_result_chars] + "\n[truncated]"
                )
                new_state.add_message(truncated_msg)
            else:
                new_state.add_message(msg)

        return new_state

    async def _compact_messages(
        self,
        state: ConversationState,
        llm: LLMProvider,
        model: str,
    ) -> ConversationState:
        """
        Summarize conversation and return a new state with the summary.

        Calls the LLM to create a summary of all prior messages, then
        returns a fresh ConversationState with a single assistant message
        containing the summary.
        """
        from mybot.core.state import ConversationState

        # Build the conversation so far for summarization
        messages_to_summarize = state.build_messages()

        # Request a summary from the LLM
        system_msg: Message = {
            "role": "system",
            "content": state.system_prompt,
        }
        summary_request: Message = {
            "role": "user",
            "content": (
                "Please summarize our conversation so far in 2-3 paragraphs, "
                "capturing the key points, decisions made, and any important "
                "context needed to continue."
            ),
        }

        summary_response = await llm.chat([system_msg, summary_request])
        summary_text = (
            summary_response[0] if isinstance(summary_response, tuple) else summary_response
        )

        # Create a new state with the summary
        new_state = ConversationState(state.system_prompt)
        summary_msg: Message = {
            "role": "assistant",
            "content": f"[Previous conversation summary]\n\n{summary_text}",
        }
        new_state.add_message(summary_msg)

        return new_state
