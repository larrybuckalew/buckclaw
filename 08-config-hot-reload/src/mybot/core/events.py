"""core/events.py -- Event types for the event-driven architecture."""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid() -> str:
    return str(uuid.uuid4())


@dataclass
class Event:
    """Base class for all events."""
    event_id: str = field(default_factory=_uid)
    timestamp: str = field(default_factory=_now)


@dataclass
class InboundEvent(Event):
    """Message arriving from a user/channel."""
    session_id: str = ""
    content: str = ""
    retry_count: int = 0


@dataclass
class OutboundEvent(Event):
    """Agent response heading back to a user/channel."""
    session_id: str = ""
    content: str = ""
    error: str | None = None
