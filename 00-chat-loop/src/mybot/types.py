"""
types.py — Shared type definitions used across the project.
"""

from typing import Literal, TypedDict


class Message(TypedDict):
    """A single conversation turn."""
    role: Literal["system", "user", "assistant"]
    content: str
