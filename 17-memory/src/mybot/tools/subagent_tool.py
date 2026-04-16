"""tools/subagent_tool.py -- Tool that lets an agent delegate to another agent."""
from __future__ import annotations
import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any
from mybot.channel.base import EventSource
from mybot.core.context import AppContext
from mybot.core.events import DispatchEvent, DispatchResultEvent
from mybot.tools.base import BaseTool

if TYPE_CHECKING:
    from mybot.core.agent import AgentSession

logger = logging.getLogger(__name__)

# Timeout waiting for a subagent to respond (seconds)
DISPATCH_TIMEOUT = 120


def create_subagent_dispatch_tool(
    current_agent_id: str,
    context: AppContext,
) -> "SubagentDispatchTool | None":
    """
    Factory: build a SubagentDispatchTool for the given agent.

    Returns None if there are no other agents to dispatch to.
    """
    if context.agent_loader is None:
        return None
    available = context.agent_loader.discover_agents()
    dispatchable = [a for a in available if a.id != current_agent_id]
    if not dispatchable:
        return None
    # Embed available agents in the tool description (XML, like the skill tool)
    agents_xml = "<available_agents>\n"
    for a in dispatchable:
        agents_xml += f'  <agent id="{a.id}">{a.description}</agent>\n'
    agents_xml += "</available_agents>"
    description = (
        "Delegate a task to a specialized subagent and return its response.\n"
        "Use this when another agent is better suited for the task.\n"
        + agents_xml
    )
    return SubagentDispatchTool(
        context=context,
        current_agent_id=current_agent_id,
        description=description,
    )


class SubagentDispatchTool(BaseTool):
    """Dispatches a task to a subagent via the EventBus and returns the result."""

    name = "subagent_dispatch"
    parameters = {
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "description": "The id of the agent to dispatch to.",
            },
            "task": {
                "type": "string",
                "description": "The task or question for the subagent.",
            },
            "context": {
                "type": "string",
                "description": "Optional additional context to pass to the subagent.",
                "default": "",
            },
        },
        "required": ["agent_id", "task"],
    }

    def __init__(
        self,
        context: AppContext,
        current_agent_id: str,
        description: str,
    ) -> None:
        self._context = context
        self._current_agent_id = current_agent_id
        self.description = description  # dynamic, set by factory

    async def execute(
        self,
        session: "AgentSession",
        agent_id: str = "",
        task: str = "",
        context: str = "",
        **_: Any,
    ) -> str:
        if not agent_id or not task:
            return "Error: agent_id and task are required."

        # Create a fresh session for the subagent
        meta = self._context.history_store.create_session(
            agent_id=agent_id,
            agent_name=agent_id,
        )
        sub_session_id = meta.session_id

        # Build the message to dispatch
        content = task
        if context.strip():
            content = f"{task}\n\nContext:\n{context}"

        # Register source for the subagent session
        agent_source = EventSource(
            platform="agent",
            user_id=self._current_agent_id,
            chat_id=sub_session_id,
        )
        self._context.session_source_map[sub_session_id] = agent_source

        # Set up a future to await the result
        loop = asyncio.get_running_loop()
        result_future: asyncio.Future[str] = loop.create_future()

        async def handle_result(event: DispatchResultEvent) -> None:
            if event.session_id == sub_session_id:
                if not result_future.done():
                    if event.error:
                        result_future.set_exception(Exception(event.error))
                    else:
                        result_future.set_result(event.content)

        # Subscribe BEFORE publishing to avoid race condition
        self._context.eventbus.subscribe(DispatchResultEvent, handle_result)

        try:
            dispatch_event = DispatchEvent(
                session_id=sub_session_id,
                content=content,
                source=agent_source,
                parent_session_id=session.state.system_prompt[:50],  # tracing hint
            )
            await self._context.eventbus.publish(dispatch_event)

            response = await asyncio.wait_for(result_future, timeout=DISPATCH_TIMEOUT)
        except asyncio.TimeoutError:
            return f"Subagent '{agent_id}' timed out after {DISPATCH_TIMEOUT}s."
        except Exception as exc:
            return f"Subagent '{agent_id}' error: {exc}"
        finally:
            self._context.eventbus.unsubscribe(handle_result)

        return json.dumps({"result": response, "session_id": sub_session_id})
