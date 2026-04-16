"""tools/post_message_tool.py -- Tool that lets an agent proactively send a message."""
from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Any
from mybot.core.context import AppContext
from mybot.core.events import OutboundEvent
from mybot.tools.base import BaseTool

if TYPE_CHECKING:
    from mybot.core.agent import AgentSession

logger = logging.getLogger(__name__)


def create_post_message_tool(
    context: AppContext,
    delivery_session_id: str,
) -> "PostMessageTool":
    """
    Factory: build a PostMessageTool that delivers to a specific session.

    Parameters
    ----------
    context:
        Shared app context (provides access to the EventBus).
    delivery_session_id:
        The user session that should receive the posted message.
        Typically the session_id of the user who scheduled the cron job.
    """
    return PostMessageTool(context=context, delivery_session_id=delivery_session_id)


class PostMessageTool(BaseTool):
    """
    Publishes an OutboundEvent to a pre-configured delivery session.

    Only injected into cron job sessions -- not user-facing sessions.
    This is what allows a cron agent to proactively reach out to a user.
    """

    name = "post_message"
    description = (
        "Send a message to the user. Use this to deliver cron job results, "
        "reminders, or any proactive communication. "
        "The message is queued for delivery to the user's channel."
    )
    parameters = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The message content to send to the user.",
            }
        },
        "required": ["content"],
    }

    def __init__(self, context: AppContext, delivery_session_id: str) -> None:
        self._context = context
        self._delivery_session_id = delivery_session_id

    async def execute(
        self,
        session: "AgentSession",
        content: str = "",
        **_: Any,
    ) -> str:
        if not content.strip():
            return "Error: content cannot be empty."

        event = OutboundEvent(
            session_id=self._delivery_session_id,
            content=content,
        )
        await self._context.eventbus.publish(event)
        logger.info(
            "post_message queued for session %s: %.60s...",
            self._delivery_session_id, content
        )
        return "Message queued for delivery."
