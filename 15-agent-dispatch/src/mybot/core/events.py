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
    source: "EventSource | None" = None


@dataclass
class OutboundEvent(Event):
    session_id: str = ""
    content: str = ""
    error: str | None = None


@dataclass
class DispatchEvent(Event):
    """Internal event: trigger agent with a prompt (cron/heartbeat/agent-dispatch)."""
    session_id: str = ""
    content: str = ""
    source: "EventSource | None" = None
    parent_session_id: str = ""    # NEW: set by subagent_dispatch for tracing


@dataclass
class DispatchResultEvent(Event):
    """Result of a DispatchEvent."""
    session_id: str = ""
    content: str = ""
    error: str | None = None
    trigger_event_id: str = ""
