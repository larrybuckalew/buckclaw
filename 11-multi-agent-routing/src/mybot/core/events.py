"""core/events.py -- Event types."""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mybot.channel.base import EventSource


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid() -> str:
    return str(uuid.uuid4())


@dataclass
class Event:
    event_id: str = field(default_factory=_uid)
    timestamp: str = field(default_factory=_now)


@dataclass
class InboundEvent(Event):
    session_id: str = ""
    content: str = ""
    retry_count: int = 0
    source: "EventSource | None" = None  # NEW: which channel/user sent this


@dataclass
class OutboundEvent(Event):
    session_id: str = ""
    content: str = ""
    error: str | None = None
