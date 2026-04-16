"""Abstract web search provider."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


class WebSearchProvider(ABC):
    @abstractmethod
    async def search(self, query: str, num_results: int = 5) -> list[SearchResult]:
        ...
