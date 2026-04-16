"""tools/memory_tools.py -- Scoped file tools for the memory agent.

Three lean tools that operate only inside the memories/ subdirectory:

  read_memory   -- read a single memory file
  write_memory  -- create or overwrite a memory file (creates dirs)
  list_memories -- list all .md files under memories/ (recursive)

Keeping memory writes scoped to one directory makes it easy to
audit, backup, or wipe the memory store independently of the rest
of the workspace.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from mybot.tools.base import BaseTool

if TYPE_CHECKING:
    from mybot.core.agent import AgentSession

MAX_READ_CHARS = 8_000


def _safe_memory_path(memory_root: Path, rel_path: str) -> Path:
    """Resolve rel_path inside memory_root; raise if it escapes."""
    resolved = (memory_root / rel_path).resolve()
    if not str(resolved).startswith(str(memory_root.resolve())):
        raise ValueError(f"Path '{rel_path}' would escape the memory store.")
    return resolved


# ---------------------------------------------------------------------------
# read_memory
# ---------------------------------------------------------------------------

class ReadMemoryTool(BaseTool):
    name = "read_memory"
    description = (
        "Read the contents of a memory file. "
        "Path is relative to the memories/ directory (e.g. 'topics/identity.md'). "
        "Returns the file contents, or an error string if the file does not exist."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path relative to memories/ directory.",
            }
        },
        "required": ["path"],
    }

    def __init__(self, memory_root: Path) -> None:
        self.memory_root = memory_root.resolve()

    async def execute(self, session: "AgentSession", path: str = "", **_: Any) -> str:
        try:
            file_path = _safe_memory_path(self.memory_root, path)
            if not file_path.exists():
                return f"Memory file '{path}' does not exist yet."
            content = file_path.read_text(encoding="utf-8", errors="replace")
            if len(content) > MAX_READ_CHARS:
                content = content[:MAX_READ_CHARS] + "\n... [truncated]"
            return content
        except Exception as exc:
            return f"Error reading memory '{path}': {exc}"


# ---------------------------------------------------------------------------
# write_memory
# ---------------------------------------------------------------------------

class WriteMemoryTool(BaseTool):
    name = "write_memory"
    description = (
        "Write (or overwrite) a memory file with the given markdown content. "
        "Creates parent directories automatically. "
        "Path is relative to the memories/ directory (e.g. 'topics/identity.md'). "
        "Always write well-structured markdown; include a '# Title' header and "
        "keep entries concise."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path relative to memories/ directory.",
            },
            "content": {
                "type": "string",
                "description": "Markdown content to store.",
            },
        },
        "required": ["path", "content"],
    }

    def __init__(self, memory_root: Path) -> None:
        self.memory_root = memory_root.resolve()

    async def execute(
        self,
        session: "AgentSession",
        path: str = "",
        content: str = "",
        **_: Any,
    ) -> str:
        try:
            file_path = _safe_memory_path(self.memory_root, path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return f"Memory saved: '{path}' ({len(content)} chars)."
        except Exception as exc:
            return f"Error writing memory '{path}': {exc}"


# ---------------------------------------------------------------------------
# list_memories
# ---------------------------------------------------------------------------

class ListMemoriesTool(BaseTool):
    name = "list_memories"
    description = (
        "List all memory files (*.md) stored under the memories/ directory. "
        "Returns a newline-separated list of relative paths. "
        "Use this to discover what memories already exist before reading them."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def __init__(self, memory_root: Path) -> None:
        self.memory_root = memory_root.resolve()

    async def execute(self, session: "AgentSession", **_: Any) -> str:
        try:
            if not self.memory_root.exists():
                return "No memories directory found."
            files = sorted(self.memory_root.rglob("*.md"))
            if not files:
                return "No memory files found yet."
            lines = [str(f.relative_to(self.memory_root)) for f in files]
            return "\n".join(lines)
        except Exception as exc:
            return f"Error listing memories: {exc}"
