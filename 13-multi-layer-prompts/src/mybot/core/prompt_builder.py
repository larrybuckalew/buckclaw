"""core/prompt_builder.py -- Assembles layered system prompts."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mybot.channel.base import EventSource
    from mybot.core.agent_loader import AgentDef
    from mybot.core.cron_loader import CronLoader

logger = logging.getLogger(__name__)

# Platform-specific hints injected into the prompt so the agent knows
# which interface the user is speaking from.
_CHANNEL_HINTS: dict[str, str] = {
    "telegram": "You are currently speaking with the user via Telegram. Keep replies concise (Telegram truncates very long messages).",
    "cli":      "You are currently in a CLI terminal session.",
    "ws":       "You are communicating via WebSocket (programmatic client).",
    "cron":     "This message was triggered automatically by a scheduled cron job. No user is present.",
    "heartbeat":"This is a heartbeat check-in. No user is present.",
}


class PromptBuilder:
    """
    Assembles a multi-layer system prompt for an agent session.

    Layers (in order):
    1. Identity  -- AGENT.md body
    2. Soul      -- SOUL.md body (optional)
    3. Bootstrap -- BOOTSTRAP.md + AGENTS.md + active cron list
    4. Runtime   -- current timestamp and session metadata
    5. Channel   -- platform hint based on EventSource
    """

    def __init__(self, workspace_dir: Path, cron_loader: "CronLoader | None" = None) -> None:
        self.workspace_dir = workspace_dir
        self.cron_loader = cron_loader

    def build(
        self,
        agent_def: "AgentDef",
        session_id: str = "",
        source: "EventSource | None" = None,
    ) -> str:
        """Build and return the complete layered system prompt."""
        layers: list[str] = []

        # Layer 1 -- Identity
        if agent_def.system_prompt:
            layers.append(agent_def.system_prompt)

        # Layer 2 -- Soul (optional personality layer)
        if agent_def.soul_md:
            layers.append(f"## Personality\n\n{agent_def.soul_md}")

        # Layer 3 -- Bootstrap context
        bootstrap = self._load_bootstrap_context()
        if bootstrap:
            layers.append(bootstrap)

        # Layer 4 -- Runtime context
        layers.append(self._build_runtime_context(session_id))

        # Layer 5 -- Channel hint
        channel_hint = self._build_channel_hint(source)
        if channel_hint:
            layers.append(channel_hint)

        return "\n\n---\n\n".join(layers)

    # -- layer builders -------------------------------------------------------

    def _load_bootstrap_context(self) -> str:
        """Load BOOTSTRAP.md, AGENTS.md, and active cron list."""
        parts = []

        # BOOTSTRAP.md -- workspace guide
        bootstrap_path = self.workspace_dir / "BOOTSTRAP.md"
        if bootstrap_path.exists():
            text = bootstrap_path.read_text(encoding="utf-8").strip()
            if text:
                parts.append(text)

        # AGENTS.md -- available agents and dispatch patterns
        agents_path = self.workspace_dir / "AGENTS.md"
        if agents_path.exists():
            text = agents_path.read_text(encoding="utf-8").strip()
            if text:
                parts.append(text)

        # Active cron jobs list
        if self.cron_loader:
            crons = self.cron_loader.discover_crons()
            if crons:
                cron_lines = ["## Active Cron Jobs"]
                for c in crons:
                    cron_lines.append(f"- `{c.id}` ({c.schedule}): {c.description}")
                parts.append("\n".join(cron_lines))

        return "\n\n".join(parts)

    def _build_runtime_context(self, session_id: str) -> str:
        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y-%m-%d %H:%M:%S UTC")
        lines = [
            "## Runtime Context",
            f"- Current time: {ts}",
        ]
        if session_id:
            lines.append(f"- Session ID: {session_id}")
        return "\n".join(lines)

    def _build_channel_hint(self, source: "EventSource | None") -> str:
        if source is None:
            return ""
        hint = _CHANNEL_HINTS.get(source.platform, "")
        if not hint:
            hint = f"You are communicating via platform: {source.platform}."
        return f"## Channel\n\n{hint}"
