"""server/agent_worker.py -- Worker that processes InboundEvents via AgentSession."""
from __future__ import annotations
import logging

from mybot.core.agent import Agent, AgentSession
from mybot.core.context import AppContext
from mybot.core.context_guard import ContextGuard
from mybot.core.events import InboundEvent, OutboundEvent
from mybot.core.worker import Worker

logger = logging.getLogger(__name__)


class AgentWorker(Worker):
    """
    Listens for InboundEvents, runs the agent, publishes OutboundEvents.

    Each InboundEvent is matched to a session by session_id.
    Sessions are cached in memory for the lifetime of the process.
    (Step 03 persistence means history survives restarts.)
    """

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self._sessions: dict[str, AgentSession] = {}
        # Subscribe at construction time so we're ready before run() starts.
        context.eventbus.subscribe(InboundEvent, self.handle_inbound)

    # -- event handler --------------------------------------------------------

    async def handle_inbound(self, event: InboundEvent) -> None:
        """Process one inbound message and publish the response."""
        try:
            session = self._get_or_create_session(event.session_id)
            response = await session.chat(event.content)
            await self.context.eventbus.publish(
                OutboundEvent(session_id=event.session_id, content=response)
            )
        except Exception as exc:
            logger.error("AgentWorker error for session %s: %s", event.session_id, exc)
            await self.context.eventbus.publish(
                OutboundEvent(session_id=event.session_id, content="", error=str(exc))
            )

    async def run(self) -> None:
        """AgentWorker has no background loop -- it's purely event-driven."""
        import asyncio
        try:
            while True:
                await asyncio.sleep(3600)  # just keep the task alive
        except asyncio.CancelledError:
            raise

    # -- session management ---------------------------------------------------

    def _get_or_create_session(self, session_id: str) -> AgentSession:
        if session_id not in self._sessions:
            cfg = self.context.config
            agent = Agent(
                llm=self.context.llm,
                name=cfg.agent.name,
                system_prompt=cfg.agent.system_prompt,
            )
            # Load history from the store if this session existed before.
            history_messages = self.context.history_store.get_messages(session_id)

            session = AgentSession(
                agent=agent,
                tools=self.context.tool_registry,
                history_store=self.context.history_store,
                context_guard=ContextGuard(),
            )
            # Restore previous messages into the session state.
            for msg in history_messages:
                session.state.add_message(msg)

            self._sessions[session_id] = session
        return self._sessions[session_id]
