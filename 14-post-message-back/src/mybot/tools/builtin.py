"""
tools/builtin.py — Three built-in tools: read_file, write_file, bash.

These three tools give the agent surprising power:
  • read_file  — inspect any file the agent needs context from
  • write_file — create or update files on disk
  • bash       — run arbitrary shell commands

Together they let the agent read its own README, edit code, run tests,
install packages, and much more — without any special integrations.

Design notes
────────────
• All paths are kept relative to a configurable workspace_dir
  (defaults to the current working directory) so the agent can't
  accidentally escape the project folder.
• bash output is capped at MAX_OUTPUT_CHARS to avoid flooding the
  context window with huge command outputs.
• Errors are returned as strings rather than raised — the LLM sees
  the error message and can decide how to recover.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mybot.tools.base import BaseTool

if TYPE_CHECKING:
    from mybot.core.agent import AgentSession

MAX_OUTPUT_CHARS = 8_000


def _safe_path(workspace: Path, rel_path: str) -> Path:
    """Resolve rel_path inside workspace; raise if it would escape."""
    resolved = (workspace / rel_path).resolve()
    if not str(resolved).startswith(str(workspace.resolve())):
        raise ValueError(f"Path '{rel_path}' escapes the workspace.")
    return resolved


# ── read_file ────────────────────────────────────────────────────────────────

class ReadFileTool(BaseTool):
    name = "read_file"
    description = (
        "Read the contents of a file.  "
        "Path is relative to the project workspace."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path to the file to read.",
            }
        },
        "required": ["path"],
    }

    def __init__(self, workspace_dir: Path | None = None) -> None:
        self.workspace = (workspace_dir or Path.cwd()).resolve()

    async def execute(self, session: "AgentSession", path: str = "", **_: Any) -> str:
        try:
            file_path = _safe_path(self.workspace, path)
            content = file_path.read_text(encoding="utf-8", errors="replace")
            if len(content) > MAX_OUTPUT_CHARS:
                content = content[:MAX_OUTPUT_CHARS] + "\n… [truncated]"
            return content
        except Exception as exc:  # noqa: BLE001
            return f"Error reading '{path}': {exc}"


# ── write_file ───────────────────────────────────────────────────────────────

class WriteFileTool(BaseTool):
    name = "write_file"
    description = (
        "Write (or overwrite) a file with the given content.  "
        "Creates parent directories if needed.  "
        "Path is relative to the project workspace."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path to write to.",
            },
            "content": {
                "type": "string",
                "description": "Text content to write.",
            },
        },
        "required": ["path", "content"],
    }

    def __init__(self, workspace_dir: Path | None = None) -> None:
        self.workspace = (workspace_dir or Path.cwd()).resolve()

    async def execute(
        self,
        session: "AgentSession",
        path: str = "",
        content: str = "",
        **_: Any,
    ) -> str:
        try:
            file_path = _safe_path(self.workspace, path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return f"Successfully wrote {len(content)} characters to '{path}'."
        except Exception as exc:  # noqa: BLE001
            return f"Error writing '{path}': {exc}"


# ── bash ─────────────────────────────────────────────────────────────────────

class BashTool(BaseTool):
    name = "bash"
    description = (
        "Run a shell command and return its output (stdout + stderr combined).  "
        "Working directory is the project workspace.  "
        "Prefer safe, read-only commands; avoid commands that could damage the system."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute.",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default 30).",
                "default": 30,
            },
        },
        "required": ["command"],
    }

    def __init__(self, workspace_dir: Path | None = None) -> None:
        self.workspace = (workspace_dir or Path.cwd()).resolve()

    async def execute(
        self,
        session: "AgentSession",
        command: str = "",
        timeout: int = 30,
        **_: Any,
    ) -> str:
        try:
            result = await asyncio.to_thread(
                lambda: subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=str(self.workspace),
                    timeout=timeout,
                    env={**os.environ, "PYTHONUNBUFFERED": "1"},
                )
            )
            output = result.stdout + result.stderr
            if len(output) > MAX_OUTPUT_CHARS:
                output = output[:MAX_OUTPUT_CHARS] + "\n… [truncated]"
            if not output.strip():
                output = f"(exit code {result.returncode}, no output)"
            return output
        except subprocess.TimeoutExpired:
            return f"Command timed out after {timeout}s."
        except Exception as exc:  # noqa: BLE001
            return f"Error running command: {exc}"
