"""tools/skill_tool.py -- Dynamic skill-loading tool.

How it works
------------
1. At startup, SkillLoader.discover_skills() scans the skills directory.
2. create_skill_tool() builds a SkillTool whose description lists every
   available skill (name + description) in XML so the LLM knows what exists.
3. When the agent calls the skill tool with a skill_id, it returns the
   full SKILL.md body as a plain string.
4. The LLM reads that content and can now follow the skill's instructions.

This is the "Tool Approach":
  - Skills are lazy-loaded (content fetched only when needed).
  - The tool schema itself advertises what skills are available.
  - No system-prompt injection required in this step.
  (See Step 13 for the system-prompt injection approach used by BuckClaw.)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mybot.skills.loader import SkillLoader
from mybot.tools.base import BaseTool

if TYPE_CHECKING:
    from mybot.core.agent import AgentSession


def create_skill_tool(skill_loader: SkillLoader) -> "SkillTool":
    """Factory: build a SkillTool wired to the given loader."""
    skills = skill_loader.discover_skills()

    # Embed available skills in the tool description so the LLM
    # knows what it can load without making an extra call.
    if skills:
        skills_xml = "<skills>\n"
        for s in skills:
            skills_xml += f'  <skill id="{s.id}" name="{s.name}">{s.description}</skill>\n'
        skills_xml += "</skills>"
    else:
        skills_xml = "<skills>(none found)</skills>"

    description = (
        "Load the full instructions for a skill by its id. "
        "Read the skill content carefully and follow its guidance.\n"
        + skills_xml
    )

    return SkillTool(skill_loader=skill_loader, description=description)


class SkillTool(BaseTool):
    """Tool that loads a skill's full content on demand."""

    name = "skill"
    parameters = {
        "type": "object",
        "properties": {
            "skill_id": {
                "type": "string",
                "description": "The id of the skill to load.",
            }
        },
        "required": ["skill_id"],
    }

    def __init__(self, skill_loader: SkillLoader, description: str) -> None:
        self.skill_loader = skill_loader
        self.description = description  # set dynamically by factory

    async def execute(
        self,
        session: "AgentSession",
        skill_id: str = "",
        **_: Any,
    ) -> str:
        skill = self.skill_loader.load_skill(skill_id)
        if skill is None:
            available = [s.id for s in self.skill_loader.discover_skills()]
            return (
                f"Skill '{skill_id}' not found. "
                f"Available skill ids: {available}"
            )
        return skill.content
