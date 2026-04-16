"""server/channel_worker.py -- Manages channels and publishes InboundEvents."""
from __future__ import annotations
import asyncio
import logging
from typing import TYPE_CHECKING
from mybot.channel.base import Channel, EventSource
from mybot.core.context import AppContext
from mybot.core.events import InboundEvent
from mybot.core.worker import Worker

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ChannelWorker(Worker):
    """Starts all registered channels and routes messages to the EventBus."""

    def __init__(self, context: AppContext, channels: list[Channel]) -> None:
        super().__init__()
        self.context = context
        self.channels = channels
        # source_id -> session_id mapping (in-memory; also written to runtime config)
        self._source_sessions: dict[str, str] = {}

    async def run(self) -> None:
        logger.info("ChannelWorker starting %d channel(s)", len(self.channels))
        tasks = [
            asyncio.create_task(
                channel.run(self._make_callback(channel)),
                name=f"channel-{channel.platform_name}",
            )
            for channel in self.channels
        ]
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            for ch in self.channels:
                try:
                    await ch.stop()
                except Exception:
                    pass
            raise

    def _make_callback(self, channel: Channel):
        async def on_message(message: str, source: EventSource) -> None:
            session_id = self._get_or_create_session_id(source)
            event = InboundEvent(
                session_id=session_id,
                content=message,
                source=source,
            )
            await self.context.eventbus.publish(event)
        return on_message

    def _get_or_create_session_id(self, source: EventSource) -> str:
        key = str(source)
        if key not in self._source_sessions:
            # Use routing table if available, otherwise use default agent id
            if self.context.routing_table is not None:
                agent_id = self.context.routing_table.resolve(str(source))
            else:
                agent_id = "my-bot"
            import uuid
            session_meta = self.context.history_store.create_session(
                agent_id=agent_id,
                agent_name=self.context.config.agent.name,
            )
            self._source_sessions[key] = session_meta.session_id
            # Persist mapping to runtime config for recovery
            try:
                self.context.config.set_runtime(f"sources.{key}", session_meta.session_id)
            except Exception:
                pass
            logger.info("New session %s (agent: %s) for source %s", session_meta.session_id, agent_id, key)
        return self._source_sessions[key]
