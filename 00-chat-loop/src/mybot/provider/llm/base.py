"""
provider/llm/base.py — Thin async wrapper around LiteLLM.

Why LiteLLM?
────────────
LiteLLM gives us a single, unified interface to dozens of LLM providers
(Anthropic, OpenAI, Mistral, Ollama, …).  Switching providers is just a
config change — no code changes required.

Design notes
────────────
• We only call acompletion() (async).  The rest of the agent is async too,
  so we never block the event loop waiting for an LLM response.
• api_base is optional — it's needed for self-hosted / proxied models.
• Extra kwargs are forwarded to LiteLLM (e.g. temperature, max_tokens).
  This keeps the provider flexible without cluttering the config schema.
"""

from __future__ import annotations

from typing import Any, cast

from litellm import Choices, acompletion

from mybot.types import Message


class LLMProvider:
    """Async LLM client backed by LiteLLM."""

    def __init__(
        self,
        model: str,
        api_key: str,
        api_base: str | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.api_base = api_base

    async def chat(
        self,
        messages: list[Message],
        **kwargs: Any,
    ) -> str:
        """
        Send a list of messages to the LLM and return the reply text.

        Parameters
        ----------
        messages:
            Full conversation history, starting with the system prompt.
        **kwargs:
            Forwarded to LiteLLM (e.g. temperature=0.7, max_tokens=512).
        """
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "api_key": self.api_key,
        }

        if self.api_base:
            request_kwargs["api_base"] = self.api_base

        # Caller-supplied overrides win.
        request_kwargs.update(kwargs)

        response = await acompletion(**request_kwargs)
        message = cast(Choices, response.choices[0]).message

        return message.content or ""
