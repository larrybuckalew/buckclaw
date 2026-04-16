"""skills/loader.py -- Discover and load SKILL.md files at runtime."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class SkillDef:
    """Metadata + content for one skill."""
    id: str
    name: str
    description: str
    content: str
    path: Path


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


def _parse_skill_file(path: Path) -> SkillDef | None:
    """Parse a SKILL.md file. Returns None on any error."""
    try:
        text = path.read_text(encoding="utf-8")
        m = _FRONTMATTER_RE.match(text)
        if not m:
            return None
        meta = yaml.safe_load(m.group(1)) or {}
        body = m.group(2).strip()
        return SkillDef(
            id=str(meta.get("id", path.stem)),
            name=str(meta.get("name", path.stem)),
            description=str(meta.get("description", "")),
            content=body,
            path=path,
        )
    except Exception:  # noqa: BLE001
        return None


class SkillLoader:
    """Discovers and loads skills from a directory."""

    def __init__(self, skills_dir: Path) -> None:
        self.skills_dir = skills_dir

    def discover_skills(self) -> list[SkillDef]:
        """Return metadata for all valid skill files found."""
        if not self.skills_dir.exists():
            return []
        skills = []
        for path in sorted(self.skills_dir.rglob("*.md")):
            skill = _parse_skill_file(path)
            if skill is not None:
                skills.append(skill)
        return skills

    def load_skill(self, skill_id: str) -> SkillDef | None:
        """Find and return a full skill by id, or None if not found."""
        for skill in self.discover_skills():
            if skill.id == skill_id:
                return skill
        return None
