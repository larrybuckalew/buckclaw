"""channel/base.py -- Abstract channel and EventSource base classes."""
from __future__ import annotations
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass
class EventSource:
    """Identifies the origin of a message -- platform + sender + chat."""
    platform: str               # e.g. "telegram", "cli"
    user_id: str = ""           # platform user identifier
    chat_id: str = ""           # platform chat/channel identifier
    source_id: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.source_id = f"{self.platform}:{self.user_id}:{self.chat_id}"

    def __str__(self) -> str:
        return self.source_id

    def __hash__(self) -> int:
        return hash(self.source_id)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, EventSource) and self.source_id == other.source_id


class Channel(ABC, Generic[T]):
    """Abstract base for messaging platforms."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Unique platform identifier (e.g. 'telegram', 'cli')."""

    @abstractmethod
    async def run(self, on_message: Callable[[str, T], Awaitable[None]]) -> None:
        """Start receiving messages. Calls on_message for each one. Blocks."""

    @abstractmethod
    async def reply(self, content: str, source: T) -> None:
        """Send a reply back to the originating source."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel and clean up resources."""
