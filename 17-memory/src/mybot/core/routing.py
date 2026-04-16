"""core/routing.py -- Source-to-agent routing with tiered regex bindings."""
from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from re import Pattern
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mybot.channel.base import EventSource
    from mybot.core.context import AppContext

logger = logging.getLogger(__name__)


def _compute_tier(value: str) -> int:
    """Compute specificity tier for a pattern string.

    Tier 0 -- exact match (no regex metacharacters)
    Tier 1 -- specific regex (has metacharacters but not .*)
    Tier 2 -- wildcard (contains .*)
    """
    metacharacters = set(r".*+?[](){}|^$\\")
    if not any(c in value for c in metacharacters):
        return 0
    if ".*" in value:
        return 2
    return 1


@dataclass
class Binding:
    """Maps a source pattern to an agent id."""
    agent: str
    value: str
    tier: int = field(init=False)
    pattern: Pattern = field(init=False)

    def __post_init__(self) -> None:
        self.tier = _compute_tier(self.value)
        try:
            self.pattern = re.compile(self.value)
        except re.error:
            self.pattern = re.compile(re.escape(self.value))


class RoutingTable:
    """Resolves an EventSource to an agent id using ordered bindings."""

    def __init__(self, context: "AppContext") -> None:
        self.context = context

    def _load_bindings(self) -> list[Binding]:
        """Load and sort bindings from config (most specific first)."""
        raw = self.context.config.routing.get("bindings", []) if hasattr(self.context.config, "routing") else []
        bindings_with_order = [
            (Binding(agent=b["agent"], value=b["value"]), i)
            for i, b in enumerate(raw)
        ]
        # Sort by tier ASC (exact first), then by original order within each tier
        bindings_with_order.sort(key=lambda x: (x[0].tier, x[1]))
        return [b for b, _ in bindings_with_order]

    def resolve(self, source: str) -> str:
        """Return the agent id for the given source string."""
        for binding in self._load_bindings():
            if binding.pattern.match(source):
                logger.debug("Routing %s -> %s (pattern: %s)", source, binding.agent, binding.value)
                return binding.agent
        default = getattr(self.context.config, "default_agent", "my-bot")
        logger.debug("Routing %s -> %s (default)", source, default)
        return default

    def add_binding(self, source_pattern: str, agent_id: str) -> None:
        """Add a binding at runtime and persist to config.runtime.yaml."""
        bindings = self.context.config.routing.get("bindings", [])
        bindings.append({"agent": agent_id, "value": source_pattern})
        self.context.config.routing["bindings"] = bindings
        try:
            self.context.config.set_runtime("routing.bindings", bindings)
        except Exception as exc:
            logger.error("Failed to persist binding: %s", exc)

    def list_bindings(self) -> list[Binding]:
        return self._load_bindings()
