"""
config.py — Load and validate configuration from YAML.

Looks for config.user.yaml first (your real keys),
then falls back to config.example.yaml (safe defaults).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


# ── Where to look for config files ──────────────────────────────────────────

_HERE = Path(__file__).parent
_WORKSPACE = _HERE.parent.parent.parent / "default_workspace"


def _find_config() -> Path:
    """Return the first existing config file: user → example."""
    for name in ("config.user.yaml", "config.example.yaml"):
        candidate = _WORKSPACE / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "No config file found.  "
        "Copy default_workspace/config.example.yaml → config.user.yaml "
        "and fill in your API key."
    )


# ── Typed config dataclasses ─────────────────────────────────────────────────

@dataclass
class LLMConfig:
    model: str = "anthropic/claude-3-5-haiku-20241022"
    api_key: str = ""
    api_base: str | None = None


@dataclass
class AgentConfig:
    name: str = "my-bot"
    system_prompt: str = "You are a helpful AI assistant."


@dataclass
class WebSearchConfig:
    provider: str = "brave"
    api_key: str = ""


@dataclass
class WebReadConfig:
    provider: str = "httpx"


@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    websearch: WebSearchConfig = field(default_factory=WebSearchConfig)
    webread: WebReadConfig = field(default_factory=WebReadConfig)


# ── Loader ───────────────────────────────────────────────────────────────────

def load_config(path: Path | None = None) -> AppConfig:
    """Parse YAML and return a typed AppConfig."""
    config_path = path or _find_config()

    with open(config_path) as f:
        raw: dict = yaml.safe_load(f) or {}

    llm_raw = raw.get("llm", {})
    agent_raw = raw.get("agent", {})
    websearch_raw = raw.get("websearch", {})
    webread_raw = raw.get("webread", {})

    # Allow the API key to be overridden by an environment variable.
    api_key = os.environ.get("LLM_API_KEY") or llm_raw.get("api_key", "")

    return AppConfig(
        llm=LLMConfig(
            model=llm_raw.get("model", "anthropic/claude-3-5-haiku-20241022"),
            api_key=api_key,
            api_base=llm_raw.get("api_base"),
        ),
        agent=AgentConfig(
            name=agent_raw.get("name", "my-bot"),
            system_prompt=agent_raw.get(
                "system_prompt", "You are a helpful AI assistant."
            ),
        ),
        websearch=WebSearchConfig(
            provider=websearch_raw.get("provider", "brave"),
            api_key=websearch_raw.get("api_key", ""),
        ),
        webread=WebReadConfig(
            provider=webread_raw.get("provider", "httpx"),
        ),
    )
