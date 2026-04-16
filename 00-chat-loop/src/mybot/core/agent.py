"""
agent.py — Core agent and session logic.

Two classes live here:

  Agent        — static configuration (LLM provider + system prompt + name).
                 Think of it as the agent's "blueprint".

  AgentSession — a live conversation.  Wires together the Agent blueprint
                 with a ConversationState to produce a stateful chat session.

Design notes
────────────
• Agent is intentionally thin: it holds no mutable state.
• AgentSession owns the ConversationState, so each session has its own
  independent history (important once we add persistence in step 03).
• The chat() method is the only public entrypoint needed for step 00.
  Later steps will add tool-calling, skill injection, etc. here.
"""

from __future__ import annotations

from mybot.core.state import ConversationState
from mybot.provider.llm.base import LLMProvider
from mybot.types import Message


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

    Each call to chat() appends both the user message and the
    assistant reply to the session's ConversationState, so the LLM
    always receives the full history.
    """

    def __init__(self, agent: Agent) -> None:
        self.agent = agent
        self.state = ConversationState(agent.system_prompt)

    async def chat(self, message: str) -> str:
        """
        Send a user message, get a response, update history.

        Returns the assistant's reply as a plain string.
        """
        # 1. Store the user's message.
        user_msg: Message = {"role": "user", "content": message}
        self.state.add_message(user_msg)

        # 2. Build the full message list (system + history) and call the LLM.
        messages = self.state.build_messages()
        response = await self.agent.llm.chat(messages)

        # 3. Store the assistant's reply so future turns have full context.
        assistant_msg: Message = {"role": "assistant", "content": response}
        self.state.add_message(assistant_msg)

        return response
