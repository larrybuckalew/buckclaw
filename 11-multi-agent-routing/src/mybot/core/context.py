"""core/context.py -- Shared application context passed to all workers."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from mybot.utils.config import Config
from mybot.core.eventbus import EventBus
from mybot.core.history import HistoryStore
from mybot.provider.llm.base import LLMProvider
from mybot.skills.loader import SkillLoader
from mybot.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from mybot.server.websocket_worker import WebSocketWorker
    from mybot.core.agent_loader import AgentLoader


@dataclass
class AppContext:
    """
    Single object that wires all shared resources together.

    Passed into every Worker and Adapter so they can access the event bus,
    config, LLM provider, and storage without global state.
    """
    config: Config
    eventbus: EventBus
    llm: LLMProvider
    history_store: HistoryStore
    tool_registry: ToolRegistry
    skill_loader: SkillLoader
    # session_id -> EventSource (populated by ChannelWorker, read by DeliveryWorker)
    session_source_map: dict = field(default_factory=dict)
    websocket_worker: "WebSocketWorker | None" = None
    agent_loader: "AgentLoader | None" = None
    routing_table: Any | None = None   # RoutingTable, typed as Any to avoid circular import
