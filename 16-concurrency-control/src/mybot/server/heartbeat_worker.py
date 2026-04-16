"""server/heartbeat_worker.py -- Single periodic pulse in the main session."""
from __future__ import annotations
import asyncio
import logging
from mybot.channel.base import EventSource
from mybot.core.context import AppContext
from mybot.core.events import DispatchEvent
from mybot.core.worker import Worker

logger = logging.getLogger(__name__)

HEARTBEAT_SOURCE = EventSource(platform="heartbeat", user_id="main", chat_id="main")


class HeartbeatWorker(Worker):
    """Fires a DispatchEvent every `interval_seconds` in the main session."""

    def __init__(
        self,
        context: AppContext,
        session_id: str,
        prompt: str,
        interval_seconds: int = 1800,  # 30 minutes default
    ) -> None:
        super().__init__()
        self.context = context
        self.session_id = session_id
        self.prompt = prompt
        self.interval = interval_seconds

    async def run(self) -> None:
        logger.info("HeartbeatWorker started (interval=%ds)", self.interval)
        try:
            while True:
                await asyncio.sleep(self.interval)
                await self._pulse()
        except asyncio.CancelledError:
            logger.info("HeartbeatWorker stopping")
            raise

    async def _pulse(self) -> None:
        event = DispatchEvent(
            session_id=self.session_id,
            content=self.prompt,
            source=HEARTBEAT_SOURCE,
        )
        logger.info("Heartbeat pulse -> session %s", self.session_id)
        await self.context.eventbus.publish(event)
