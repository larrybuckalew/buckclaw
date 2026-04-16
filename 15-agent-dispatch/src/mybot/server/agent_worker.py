"""server/agent_worker.py -- Background worker that runs chat sessions and invokes tools."""
from __future__ import annotations
import asyncio
import logging
from mybot.core.context import AppContext
from mybot.core.events import InboundEvent, DispatchEvent, DispatchResultEvent
from mybot.core.worker import Worker

logger = logging.getLogger(__name__)


class AgentWorker(Worker):
    """Listens on EventBus for InboundEvent and DispatchEvent, runs agent chat."""

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self._sessions = {}
        context.eventbus.subscribe(InboundEvent, self.handle_inbound)
        context.eventbus.subscribe(DispatchEvent, self.handle_dispatch)

    async def run(self) -> None:
        logger.info("AgentWorker started")
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("AgentWorker stopping")
            raise

    async def handle_inbound(self, event: InboundEvent) -> None:
        """Process an InboundEvent (user message)."""
        try:
            session = self._get_or_create_session(event.session_id)
            if event.source:
                self.context.session_source_map[event.session_id] = event.source
                # Refresh prompt if source changed and prompt_builder is available
                if self.context.prompt_builder and event.session_id in self._sessions:
                    self._refresh_session_prompt(event.session_id)
            response = await session.chat(event.content)
            from mybot.core.events import OutboundEvent
            await self.context.eventbus.publish(
                OutboundEvent(
                    session_id=event.session_id,
                    content=response,
                )
            )
        except Exception as exc:
            logger.error("Inbound error for session %s: %s", event.session_id, exc)
            from mybot.core.events import OutboundEvent
            await self.context.eventbus.publish(
                OutboundEvent(
                    session_id=event.session_id,
                    content="",
                    error=str(exc),
                )
            )

    async def handle_dispatch(self, event: DispatchEvent) -> None:
        """Process a cron/heartbeat dispatch -- publishes DispatchResultEvent."""
        try:
            session = self._get_or_create_session(event.session_id)
            if event.source:
                self.context.session_source_map[event.session_id] = event.source
            response = await session.chat(event.content)
            await self.context.eventbus.publish(
                DispatchResultEvent(
                    session_id=event.session_id,
                    content=response,
                    trigger_event_id=event.event_id,
                )
            )
        except Exception as exc:
            logger.error("Dispatch error for session %s: %s", event.session_id, exc)
            await self.context.eventbus.publish(
                DispatchResultEvent(
                    session_id=event.session_id,
                    content="",
                    error=str(exc),
                    trigger_event_id=event.event_id,
                )
            )

    def _get_or_create_session(self, session_id: str):
        """Get or create an Agent session by id."""
        from mybot.core.agent import Agent, AgentSession
        if session_id not in self._sessions:
            cfg = self.context.config
            agent_name = cfg.agent.name
            system_prompt = cfg.agent.system_prompt
            current_agent_id = "my-bot"

            if self.context.agent_loader:
                session_meta = self.context.history_store.get_session(session_id)
                if session_meta and session_meta.agent_id:
                    current_agent_id = session_meta.agent_id
                    agent_def = self.context.agent_loader.load(session_meta.agent_id)
                    if agent_def:
                        agent_name = agent_def.name
                        if self.context.prompt_builder:
                            source = self.context.session_source_map.get(session_id)
                            system_prompt = self.context.prompt_builder.build(
                                agent_def=agent_def,
                                session_id=session_id,
                                source=source,
                            )
                        else:
                            system_prompt = agent_def.system_prompt

            agent = Agent(llm=self.context.llm, name=agent_name, system_prompt=system_prompt)
            history_messages = self.context.history_store.get_messages(session_id)

            # Start with base tool registry
            tools = self.context.tool_registry

            # Inject post_message for cron sessions with a delivery target
            delivery_session_id = self.context.cron_delivery_map.get(session_id)
            if delivery_session_id:
                from mybot.tools.post_message_tool import create_post_message_tool
                from mybot.tools.registry import ToolRegistry
                all_tools = list(tools._tools.values())
                post_msg_tool = create_post_message_tool(self.context, delivery_session_id)
                all_tools.append(post_msg_tool)
                tools = ToolRegistry(all_tools)
                logger.info("Injected post_message for cron session %s -> %s", session_id, delivery_session_id)

            # Inject subagent_dispatch if multiple agents available
            if self.context.agent_loader:
                from mybot.tools.subagent_tool import create_subagent_dispatch_tool
                from mybot.tools.registry import ToolRegistry
                dispatch_tool = create_subagent_dispatch_tool(
                    current_agent_id=current_agent_id,
                    context=self.context,
                )
                if dispatch_tool:
                    all_tools = list(tools._tools.values())
                    all_tools.append(dispatch_tool)
                    tools = ToolRegistry(all_tools)
                    logger.debug("Injected subagent_dispatch for agent %s", current_agent_id)

            from mybot.core.context_guard import ContextGuard
            session = AgentSession(
                agent=agent,
                tools=tools,
                history_store=self.context.history_store,
                context_guard=ContextGuard(),
            )
            for msg in history_messages:
                session.state.add_message(msg)
            self._sessions[session_id] = session
        return self._sessions[session_id]

    def _refresh_session_prompt(self, session_id: str) -> None:
        """Rebuild system prompt for a session using PromptBuilder."""
        if session_id not in self._sessions:
            return
        session = self._sessions[session_id]
        meta = self.context.history_store.get_session(session_id)
        if not meta or not meta.agent_id or not self.context.agent_loader:
            return
        agent_def = self.context.agent_loader.load(meta.agent_id)
        if not agent_def or not self.context.prompt_builder:
            return
        source = self.context.session_source_map.get(session_id)
        new_system_prompt = self.context.prompt_builder.build(
            agent_def=agent_def,
            session_id=session_id,
            source=source,
        )
        # Update the session's agent system prompt
        session.agent.system_prompt = new_system_prompt
