"""core/eventbus.py -- Pub/sub EventBus with optional OutboundEvent persistence."""
from __future__ import annotations
import asyncio
import json
import logging
import os
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Awaitable, Callable, TypeVar

from mybot.core.events import Event, InboundEvent, OutboundEvent
from mybot.core.worker import Worker

logger = logging.getLogger(__name__)
Handler = Callable[[Event], Awaitable[None]]
E = TypeVar("E", bound=Event)


def _serialize_event(event: Event) -> dict:
    d = asdict(event) if hasattr(event, "__dataclass_fields__") else vars(event)
    d["__type__"] = type(event).__name__
    return d


def _deserialize_event(data: dict) -> Event | None:
    etype = data.pop("__type__", None)
    if etype == "OutboundEvent":
        return OutboundEvent(**{k: v for k, v in data.items() if k in OutboundEvent.__dataclass_fields__})
    return None


class EventBus(Worker):
    def __init__(self, pending_dir: Path | None = None) -> None:
        super().__init__()
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._handlers: dict[type, list[Handler]] = defaultdict(list)
        self.pending_dir = pending_dir
        if pending_dir:
            pending_dir.mkdir(parents=True, exist_ok=True)

    def subscribe(self, event_class: type[E], handler: Callable[[E], Awaitable[None]]) -> None:
        self._handlers[event_class].append(handler)  # type: ignore[arg-type]

    def unsubscribe(self, handler: Handler) -> None:
        for handlers in self._handlers.values():
            if handler in handlers:
                handlers.remove(handler)

    async def publish(self, event: Event) -> None:
        await self._queue.put(event)

    def ack(self, event: Event) -> None:
        """Mark an OutboundEvent as successfully delivered -- deletes its persisted file."""
        if not self.pending_dir:
            return
        filename = f"{event.event_id}.json"
        path = self.pending_dir / filename
        if path.exists():
            path.unlink()
            logger.debug("Acked event %s", event.event_id)

    async def run(self) -> None:
        logger.info("EventBus started")
        await self._recover()
        try:
            while True:
                event = await self._queue.get()
                try:
                    await self._dispatch(event)
                except Exception as exc:
                    logger.error("Error dispatching event %s: %s", event, exc)
                finally:
                    self._queue.task_done()
        except asyncio.CancelledError:
            logger.info("EventBus stopping")
            raise

    async def _dispatch(self, event: Event) -> None:
        if isinstance(event, OutboundEvent):
            await self._persist_outbound(event)
        handlers = self._handlers.get(type(event), [])
        for handler in handlers:
            await handler(event)

    async def _persist_outbound(self, event: OutboundEvent) -> None:
        if not self.pending_dir:
            return
        try:
            data = _serialize_event(event)
            filename = f"{event.event_id}.json"
            tmp_path = self.pending_dir / (filename + ".tmp")
            final_path = self.pending_dir / filename
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
                f.flush()
                os.fsync(f.fileno())
            tmp_path.rename(final_path)
        except Exception as exc:
            logger.error("Failed to persist event %s: %s", event.event_id, exc)

    async def _recover(self) -> int:
        if not self.pending_dir:
            return 0
        pending = list(self.pending_dir.glob("*.json"))
        if pending:
            logger.info("Recovering %d pending events", len(pending))
        for path in pending:
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                event = _deserialize_event(data)
                if event:
                    handlers = self._handlers.get(type(event), [])
                    for handler in handlers:
                        await handler(event)
            except Exception as exc:
                logger.error("Failed to recover event from %s: %s", path, exc)
        return len(pending)
