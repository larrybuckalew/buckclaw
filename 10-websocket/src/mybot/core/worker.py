"""core/worker.py -- Worker abstract base and SubscriberWorker."""
from __future__ import annotations
import asyncio
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class Worker(ABC):
    """Lifecycle contract for background async tasks."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Create and schedule the background task."""
        self._task = asyncio.create_task(self.run(), name=self.__class__.__name__)

    async def stop(self) -> None:
        """Cancel and await the background task."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    @abstractmethod
    async def run(self) -> None:
        """Main loop. Override in subclasses."""
