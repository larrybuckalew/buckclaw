"""webread tool -- fetch and return readable content from a URL."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mybot.provider.web_read.base import WebReadProvider
from mybot.tools.base import BaseTool

if TYPE_CHECKING:
    from mybot.core.agent import AgentSession


class WebReadTool(BaseTool):
    name = "webread"
    description = (
        "Fetch the content of a web page and return it as readable text. "
        "Use this after websearch to read the full content of a page, "
        "or to access a specific URL directly."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch.",
            }
        },
        "required": ["url"],
    }

    def __init__(self, provider: WebReadProvider) -> None:
        self.provider = provider

    async def execute(
        self,
        session: "AgentSession",
        url: str = "",
        **_: Any,
    ) -> str:
        result = await self.provider.read(url)
        if result.error:
            return f"Error reading {url}: {result.error}"
        title = result.title or url
        return f"**{title}**\n\n{result.content}"
