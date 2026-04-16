"""provider/llm/base.py -- Async LiteLLM wrapper with tool-call support.

Changes from Step 00
--------------------
* chat() now accepts an optional `tool_schemas` list.
* Returns a tuple (content, tool_calls) instead of a plain string.
  - content    : text reply (may be empty while the LLM is using tools)
  - tool_calls : list of ToolCall objects, or [] if the LLM stopped normally

Stop reasons:
  "end_turn"  -> LLM is done; content holds the final reply.
  "tool_use"  -> LLM wants to call tools; tool_calls is non-empty.
"""

from __future__ import annotations

from typing import Any, cast

from litellm import Choices, acompletion

from mybot.types import Message, ToolCall


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
        tool_schemas: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> tuple[str, list[ToolCall]]:
        """Send messages to the LLM and return (content, tool_calls).

        Parameters
        ----------
        messages:
            Full conversation history starting with the system prompt.
        tool_schemas:
            Optional list of function-call schemas. If provided, the LLM
            may respond with tool calls instead of (or alongside) text.
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

        if tool_schemas:
            request_kwargs["tools"] = tool_schemas
            request_kwargs["tool_choice"] = "auto"

        request_kwargs.update(kwargs)

        response = await acompletion(**request_kwargs)
        choice = cast(Choices, response.choices[0])
        message = choice.message

        content: str = message.content or ""
        raw_tool_calls = getattr(message, "tool_calls", None) or []

        tool_calls: list[ToolCall] = [
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=tc.function.arguments,
            )
            for tc in raw_tool_calls
        ]

        return content, tool_calls
