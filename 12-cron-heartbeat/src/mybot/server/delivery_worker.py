"""server/delivery_worker.py -- Delivers OutboundEvents back to the originating channel."""
from __future__ import annotations
import logging
from mybot.channel.base import Channel, EventSource
from mybot.core.context import AppContext
from mybot.core.events import OutboundEvent
from mybot.core.worker import Worker

logger = logging.getLogger(__name__)


class DeliveryWorker(Worker):
    """Subscribes to OutboundEvents and sends replies via the right channel."""

    def __init__(
        self,
        context: AppContext,
        channels: list[Channel],
        source_map: dict[str, EventSource],  # session_id -> EventSource
    ) -> None:
        super().__init__()
        self.context = context
        self._channels: dict[str, Channel] = {ch.platform_name: ch for ch in channels}
        self._source_map = source_map  # shared with ChannelWorker
        context.eventbus.subscribe(OutboundEvent, self.handle_outbound)

    async def handle_outbound(self, event: OutboundEvent) -> None:
        source = self._source_map.get(event.session_id)
        if source is None:
            logger.warning("No source found for session %s", event.session_id)
            self.context.eventbus.ack(event)
            return
        channel = self._channels.get(source.platform)
        if channel is None:
            logger.warning("No channel for platform %s", source.platform)
            self.context.eventbus.ack(event)
            return
        try:
            if event.error:
                await channel.reply(f"Error: {event.error}", source)
            else:
                await channel.reply(event.content, source)
            self.context.eventbus.ack(event)
        except Exception as exc:
            logger.error("Delivery failed for session %s: %s", event.session_id, exc)

    async def run(self) -> None:
        import asyncio
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise
