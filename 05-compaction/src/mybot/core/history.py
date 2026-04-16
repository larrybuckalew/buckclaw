"""
core/history.py -- JSONL-based conversation persistence.

Stores sessions and messages in a .history/ directory with two files:
  - .history/index.jsonl: one SessionMeta per line
  - .history/sessions/{session_id}.jsonl: one HistoryMessage per line

Changes from Step 02
────────────────────
• New HistoryMessage dataclass: session_id, role, content, timestamp, optional
  tool_calls, tool_call_id, name for tool results.
• New SessionMeta dataclass: session_id, agent_id, agent_name, created_at,
  message_count.
• New HistoryStore class: manages creation, retrieval, and listing of sessions.
  Uses UUID for session IDs and JSON line protocol for persistence.

Design notes
────────────
• JSONL format allows for easy append-only writes and streaming reads.
• SessionMeta is written to index.jsonl on session creation and updated
  when messages are added (message_count increments).
• Each session lives in its own file, so multiple agents can share the same
  .history/ directory without conflicts.
• Timestamps are ISO 8601 strings for easy parsing and sorting.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class HistoryMessage:
    """A single message in the conversation history."""

    session_id: str
    role: str  # "user", "assistant", "system", "tool"
    content: str
    timestamp: str  # ISO 8601 string
    tool_calls: Optional[list[dict]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dict, excluding None fields."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class SessionMeta:
    """Metadata about a conversation session."""

    session_id: str
    agent_id: str
    agent_name: str
    created_at: str  # ISO 8601 string
    message_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dict."""
        return asdict(self)


class HistoryStore:
    """Manages JSONL-based persistence for sessions and messages."""

    def __init__(self, base_dir: Path) -> None:
        """
        Initialize the store.

        Creates .history/ and .history/sessions/ directories if needed.
        """
        self.base_dir = Path(base_dir)
        self.index_file = self.base_dir / "index.jsonl"
        self.sessions_dir = self.base_dir / "sessions"

        # Create directories
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        agent_id: str,
        agent_name: str,
    ) -> SessionMeta:
        """
        Create a new session.

        Generates a UUID session_id, writes metadata to index.jsonl,
        and returns the SessionMeta.
        """
        session_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat() + "Z"

        meta = SessionMeta(
            session_id=session_id,
            agent_id=agent_id,
            agent_name=agent_name,
            created_at=created_at,
            message_count=0,
        )

        # Append to index
        with open(self.index_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(meta.to_dict()) + "\n")

        return meta

    def save_message(self, session_id: str, message: dict) -> None:
        """
        Append a message to the session's JSONL file.

        Also increments message_count in index.jsonl.
        """
        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.utcnow().isoformat() + "Z"

        # Write message to session file
        session_file = self.sessions_dir / f"{session_id}.jsonl"
        with open(session_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(message) + "\n")

        # Update message_count in index
        self._increment_message_count(session_id)

    def get_messages(self, session_id: str) -> list[dict]:
        """
        Read all messages from a session's JSONL file.

        Returns a list of dicts (messages), or empty list if not found.
        """
        session_file = self.sessions_dir / f"{session_id}.jsonl"
        if not session_file.exists():
            return []

        messages = []
        with open(session_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    messages.append(json.loads(line))

        return messages

    def list_sessions(self) -> list[SessionMeta]:
        """
        Read all sessions from index.jsonl.

        Returns a list of SessionMeta objects.
        """
        if not self.index_file.exists():
            return []

        sessions = []
        with open(self.index_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    sessions.append(SessionMeta(**data))

        return sessions

    def get_session(self, session_id: str) -> SessionMeta | None:
        """
        Retrieve a specific session by ID.

        Returns SessionMeta if found, None otherwise.
        """
        for session in self.list_sessions():
            if session.session_id == session_id:
                return session

        return None

    def _increment_message_count(self, session_id: str) -> None:
        """Update message_count for a session in index.jsonl."""
        sessions = self.list_sessions()

        for session in sessions:
            if session.session_id == session_id:
                session.message_count += 1

        # Rewrite the entire index file
        with open(self.index_file, "w", encoding="utf-8") as f:
            for session in sessions:
                f.write(json.dumps(session.to_dict()) + "\n")
