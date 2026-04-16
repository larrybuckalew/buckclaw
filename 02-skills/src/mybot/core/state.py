"""
state.py — Manages conversation history for a single session.

The LLM always receives the full message history so it has
complete context for every reply.

Design notes
────────────
• Messages are stored as plain dicts (Message TypedDict) so they
  can be serialised to JSON in a later step (03-persistence).
• build_messages() prepends the system prompt every time it is
  called, keeping the stored list clean (no duplicate system msgs).
"""

from __future__ import annotations

from mybot.types import Message


class ConversationState:
    """Holds the ordered list of messages exchanged so far."""

    def __init__(self, system_prompt: str) -> None:
        self.system_prompt = system_prompt
        self._messages: list[Message] = []

    # ── Public API ────────────────────────────────────────────────────────

    def add_message(self, message: Message) -> None:
        """Append a message to the history."""
        self._messages.append(message)

    def build_messages(self) -> list[Message]:
        """
        Return the full message list ready to send to the LLM.

        Always starts with the system prompt, followed by the
        conversation history in chronological order.
        """
        system: Message = {"role": "system", "content": self.system_prompt}
        return [system, *self._messages]

    def clear(self) -> None:
        """Wipe history (keeps system prompt)."""
        self._messages.clear()

    @property
    def message_count(self) -> int:
        """Number of user/assistant turns stored (excludes system prompt)."""
        return len(self._messages)
