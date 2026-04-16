from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from mybot.core.eventbus import EventBus
from mybot.core.history import HistoryStore
from mybot.provider.llm.base import LLMProvider
from mybot.skills.loader import SkillLoader
from mybot.tools.registry import ToolRegistry
from mybot.utils.config import Config

if TYPE_CHECKING:
    from mybot.core.agent_loader import AgentLoader
    from mybot.core.cron_loader import CronLoader
    from mybot.core.prompt_builder import PromptBuilder
    from mybot.server.websocket_worker import WebSocketWorker


@dataclass
class AppContext:
    config: Config
    eventbus: EventBus
    llm: LLMProvider
    history_store: HistoryStore
    tool_registry: ToolRegistry
    skill_loader: SkillLoader
    session_source_map: dict = field(default_factory=dict)
    websocket_worker: "WebSocketWorker | None" = None
    agent_loader: "AgentLoader | None" = None
    routing_table: Any = None
    cron_loader: "CronLoader | None" = None
    heartbeat_session_id: str = ""
    prompt_builder: "PromptBuilder | None" = None
