"""core/eventbus.py -- Central pub/sub event bus."""
from __future__ import annotations
import asyncio
import logging
from collections import defaultdict
from typing import Awaitable, Callable, TypeVar

from mybot.core.events import Event
from mybot.core.worker import Worker

logger = logging.getLogger(__name__)

E = TypeVar("E", bound=Event)
Handler = Callable[[Event], Awaitable[None]]


class EventBus(Worker):
    """
    Async pub/sub queue.

    Subscribers register interest in a specific Event subclass.
    Events are dispatched sequentially from an internal asyncio.Queue.
    """

    def __init__(self) -> None:
        super().__init__()
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._handlers: dict[type, list[Handler]] = defaultdict(list)

    # -- subscription management ------------------------------------------

    def subscribe(
        self,
        event_class: type[E],
        handler: Callable[[E], Awaitable[None]],
    ) -> None:
        """Register handler to be called for every event of event_class."""
        self._handlers[event_class].append(handler)  # type: ignore[arg-type]

    def unsubscribe(self, handler: Handler) -> None:
        """Remove handler from all subscriptions."""
        for handlers in self._handlers.values():
            if handler in handlers:
                handlers.remove(handler)

    # -- publishing -----------------------------------------------------------

    async def publish(self, event: Event) -> None:
        """Enqueue an event (non-blocking)."""
        await self._queue.put(event)

    # -- main loop ------------------------------------------------------------

    async def run(self) -> None:
        """Drain the queue and dispatch events to registered handlers."""
        logger.info("EventBus started")
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
        handlers = self._handlers.get(type(event), [])
        for handler in handlers:
            await handler(event)
