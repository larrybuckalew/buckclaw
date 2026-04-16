"""core/agent_loader.py -- Discovers and loads agent definitions from AGENT.md files."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path
import yaml


@dataclass
class AgentDef:
    """Static definition of an agent loaded from AGENT.md (+ optional SOUL.md)."""
    id: str
    name: str
    description: str
    system_prompt: str      # full AGENT.md body (Layer 1)
    soul_md: str            # SOUL.md body (Layer 2, may be empty)
    path: Path
    max_concurrency: int = field(default=0)  # 0 = unlimited


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


def _parse_agent_file(path: Path) -> AgentDef | None:
    try:
        text = path.read_text(encoding="utf-8")
        m = _FRONTMATTER_RE.match(text)
        if not m:
            return None
        meta = yaml.safe_load(m.group(1)) or {}
        body = m.group(2).strip()
        # Also load SOUL.md from the same directory if present
        soul_path = path.parent / "SOUL.md"
        soul_md = soul_path.read_text(encoding="utf-8").strip() if soul_path.exists() else ""
        raw_mc = meta.get("max_concurrency", 0)
        try:
            max_concurrency = int(raw_mc)
        except (TypeError, ValueError):
            max_concurrency = 0
        return AgentDef(
            id=str(meta.get("id", path.parent.name)),
            name=str(meta.get("name", path.parent.name)),
            description=str(meta.get("description", "")),
            system_prompt=body,
            soul_md=soul_md,
            path=path,
            max_concurrency=max_concurrency,
        )
    except Exception:
        return None


class AgentLoader:
    """Discovers agent definitions from a directory of AGENT.md files."""

    def __init__(self, agents_dir: Path) -> None:
        self.agents_dir = agents_dir
        self._cache: dict[str, AgentDef] = {}

    def discover_agents(self) -> list[AgentDef]:
        if not self.agents_dir.exists():
            return []
        agents = []
        for path in sorted(self.agents_dir.rglob("AGENT.md")):
            agent = _parse_agent_file(path)
            if agent is not None:
                agents.append(agent)
                self._cache[agent.id] = agent
        return agents

    def load(self, agent_id: str) -> AgentDef | None:
        if agent_id in self._cache:
            return self._cache[agent_id]
        self.discover_agents()
        return self._cache.get(agent_id)
