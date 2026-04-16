"""Brave Search API provider."""
from __future__ import annotations

import httpx

from mybot.provider.web_search.base import SearchResult, WebSearchProvider


class BraveSearchProvider(WebSearchProvider):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def search(self, query: str, num_results: int = 5) -> list[SearchResult]:
        """Search using Brave Search API.
        
        Args:
            query: The search query.
            num_results: Number of results to return.
            
        Returns:
            List of SearchResult objects, or empty list on error.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.search.brave.com/res/v1/web/search?q={query}&count={num_results}",
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": self.api_key,
                    },
                )
                response.raise_for_status()
                data = response.json()

                results = []
                for item in data.get("web", {}).get("results", []):
                    results.append(
                        SearchResult(
                            title=item["title"],
                            url=item["url"],
                            snippet=item.get("description", ""),
                        )
                    )
                return results
        except Exception:
            return []
