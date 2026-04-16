"""server/websocket_worker.py -- WebSocket connection manager and event broadcaster."""
from __future__ import annotations
import dataclasses
import json
import logging
from typing import TYPE_CHECKING, Set
from fastapi import WebSocket
from mybot.channel.base import EventSource
from mybot.core.context import AppContext
from mybot.core.events import Event, InboundEvent, OutboundEvent
from mybot.core.worker import Worker

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class WebSocketWorker(Worker):
    """
    Manages WebSocket client connections.

    Responsibilities:
    1. Accept new WebSocket connections (via handle_connection, called by FastAPI)
    2. Read JSON messages from each client and publish InboundEvents
    3. Broadcast all InboundEvents and OutboundEvents to all connected clients

    Wire-up happens in handle_connection -- clients subscribe implicitly by connecting.
    """

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.clients: Set[WebSocket] = set()
        self._source_sessions: dict[str, str] = {}
        # Subscribe to both event types for broadcast
        context.eventbus.subscribe(InboundEvent, self.handle_event)
        context.eventbus.subscribe(OutboundEvent, self.handle_event)

    # -- connection lifecycle -------------------------------------------------

    async def handle_connection(self, ws: WebSocket) -> None:
        """Called by FastAPI for each new WebSocket connection."""
        self.clients.add(ws)
        logger.info("WebSocket client connected (total: %d)", len(self.clients))
        try:
            await self._run_client_loop(ws)
        except Exception as exc:
            logger.debug("WebSocket client error: %s", exc)
        finally:
            self.clients.discard(ws)
            logger.info("WebSocket client disconnected (total: %d)", len(self.clients))

    async def _run_client_loop(self, ws: WebSocket) -> None:
        """Read messages from a single client until it disconnects."""
        async for data in ws.iter_json():
            source_name = str(data.get("source", "anonymous"))
            content = str(data.get("content", "")).strip()
            if not content:
                continue
            source = EventSource(platform="ws", user_id=source_name, chat_id=source_name)
            session_id = self._get_or_create_session_id(source)
            event = InboundEvent(session_id=session_id, content=content, source=source)
            # Populate the context source map so DeliveryWorker can route replies
            self.context.session_source_map[session_id] = source
            await self.context.eventbus.publish(event)

    # -- event broadcasting ---------------------------------------------------

    async def handle_event(self, event: Event) -> None:
        """Broadcast any event to all connected WebSocket clients."""
        if not self.clients:
            return
        try:
            payload = {"type": event.__class__.__name__}
            payload.update(dataclasses.asdict(event))
            for client in list(self.clients):
                try:
                    await client.send_json(payload)
                except Exception:
                    self.clients.discard(client)
        except Exception as exc:
            logger.error("Broadcast error: %s", exc)

    # -- session management ---------------------------------------------------

    def _get_or_create_session_id(self, source: EventSource) -> str:
        key = str(source)
        if key not in self._source_sessions:
            meta = self.context.history_store.create_session(
                agent_id="my-bot",
                agent_name=self.context.config.agent.name,
            )
            self._source_sessions[key] = meta.session_id
            logger.info("New WS session %s for %s", meta.session_id, key)
        return self._source_sessions[key]

    async def run(self) -> None:
        """No background loop -- driven by handle_connection calls from FastAPI."""
        import asyncio
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise
