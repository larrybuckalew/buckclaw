"""Abstract web reading provider."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ReadResult:
    url: str
    title: str
    content: str
    error: str = ""


class WebReadProvider(ABC):
    @abstractmethod
    async def read(self, url: str) -> ReadResult:
        ...
