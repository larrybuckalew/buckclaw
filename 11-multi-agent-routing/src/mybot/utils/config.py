"""utils/config.py -- Pydantic config with hot reload and deep merge."""
from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


class LLMConfig(BaseModel):
    model: str = "anthropic/claude-3-5-haiku-20241022"
    api_key: str = ""
    api_base: str | None = None


class AgentConfig(BaseModel):
    name: str = "my-bot"
    system_prompt: str = "You are a helpful AI assistant."


class WebSearchConfig(BaseModel):
    provider: str = "brave"
    api_key: str = ""


class WebReadConfig(BaseModel):
    provider: str = "httpx"


class TelegramConfig(BaseModel):
    token: str = ""
    allowed_user_ids: list[int] = []   # empty = allow all users


class ChannelsConfig(BaseModel):
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)


class ApiConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    enabled: bool = True


class Config(BaseModel):
    """Live application config with hot-reload support."""

    workspace: Path = Field(default_factory=Path.cwd, exclude=True)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    websearch: WebSearchConfig = Field(default_factory=WebSearchConfig)
    webread: WebReadConfig = Field(default_factory=WebReadConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    routing: dict = Field(default_factory=dict)   # {"bindings": [...]}
    default_agent: str = "my-bot"

    model_config = {"arbitrary_types_allowed": True}

    # -- factory -----------------------------------------------------------

    @classmethod
    def load(cls, workspace_dir: Path) -> "Config":
        """Load and merge config files, return a new Config."""
        data = cls._load_merged_configs(workspace_dir)
        obj = cls.model_validate(data)
        obj.workspace = workspace_dir
        # Allow env var override for LLM API key
        if env_key := os.environ.get("LLM_API_KEY"):
            obj.llm.api_key = env_key
        return obj

    # -- hot reload --------------------------------------------------------

    def reload(self) -> bool:
        """Re-read config files and update this object in-place. Returns True on success."""
        try:
            data = self._load_merged_configs(self.workspace)
            new = Config.model_validate(data)
            new.workspace = self.workspace
            for field_name in Config.model_fields:
                if field_name == "workspace":
                    continue
                setattr(self, field_name, getattr(new, field_name))
            logger.info("Config reloaded from %s", self.workspace)
            return True
        except Exception as exc:
            logger.error("Config reload failed: %s", exc)
            return False

    def set_runtime(self, dotted_key: str, value: object) -> None:
        """Write a value to config.runtime.yaml under a dotted key path."""
        runtime_path = self.workspace / "config.runtime.yaml"
        data = {}
        if runtime_path.exists():
            with open(runtime_path) as f:
                data = yaml.safe_load(f) or {}
        # Set nested key
        parts = dotted_key.split(".")
        node = data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
        with open(runtime_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    # -- helpers -----------------------------------------------------------

    @classmethod
    def _load_merged_configs(cls, workspace_dir: Path) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for filename in ("config.user.yaml", "config.runtime.yaml"):
            path = workspace_dir / filename
            if path.exists():
                with open(path) as f:
                    raw = yaml.safe_load(f) or {}
                data = _deep_merge(data, raw)
        if not data:
            # Try example config as last resort
            example = workspace_dir / "config.example.yaml"
            if example.exists():
                with open(example) as f:
                    data = yaml.safe_load(f) or {}
        return data
