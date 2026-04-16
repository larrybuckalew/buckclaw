"""websearch tool -- query the web and return ranked snippets."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mybot.provider.web_search.base import WebSearchProvider
from mybot.tools.base import BaseTool

if TYPE_CHECKING:
    from mybot.core.agent import AgentSession


class WebSearchTool(BaseTool):
    name = "websearch"
    description = (
        "Search the web and return a ranked list of results with titles, "
        "URLs, and snippets. Use this to find current information, news, "
        "documentation, or anything outside your training data."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (default 5, max 10).",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    def __init__(self, provider: WebSearchProvider) -> None:
        self.provider = provider

    async def execute(
        self,
        session: "AgentSession",
        query: str = "",
        num_results: int = 5,
        **_: Any,
    ) -> str:
        results = await self.provider.search(query, min(num_results, 10))
        if not results:
            return "No results found."
        output = []
        for i, r in enumerate(results, 1):
            output.append(f"{i}. **{r.title}**\n   {r.url}\n   {r.snippet}")
        return "\n\n".join(output)
