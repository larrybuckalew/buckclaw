"""utils/config.py -- Configuration management."""
from __future__ import annotations
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
import yaml


class LLMConfig(BaseModel):
    model: str = "claude-3-5-sonnet-20241022"
    api_key: str = "YOUR_API_KEY_HERE"
    api_base: Optional[str] = None


class WebSearchConfig(BaseModel):
    api_key: str = "YOUR_BRAVE_SEARCH_API_KEY"


class TelegramConfig(BaseModel):
    token: str = "YOUR_TELEGRAM_BOT_TOKEN"


class ChannelsConfig(BaseModel):
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)


class APIConfig(BaseModel):
    enabled: bool = False
    host: str = "localhost"
    port: int = 8000


class AgentConfig(BaseModel):
    name: str = "my-bot"
    description: str = "An AI assistant"


class HeartbeatConfig(BaseModel):
    enabled: bool = False
    interval_seconds: int = 1800
    prompt: str = "Check in: summarize any pending tasks or reminders."


class Config(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    websearch: WebSearchConfig = Field(default_factory=WebSearchConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    heartbeat: HeartbeatConfig = Field(default_factory=HeartbeatConfig)

    @classmethod
    def load(cls, workspace_dir: Path) -> Config:
        """Load config from workspace, merging example + user overrides."""
        example_path = workspace_dir / "config.example.yaml"
        user_path = workspace_dir / "config.user.yaml"

        config_dict = {}
        if example_path.exists():
            with open(example_path) as f:
                config_dict = yaml.safe_load(f) or {}
        if user_path.exists():
            with open(user_path) as f:
                user_dict = yaml.safe_load(f) or {}
                config_dict = {**config_dict, **user_dict}

        return cls(**config_dict) if config_dict else cls()

    def save_example(self, workspace_dir: Path) -> None:
        """Save config.example.yaml."""
        path = workspace_dir / "config.example.yaml"
        with open(path, "w") as f:
            yaml.dump(self.model_dump(mode="json"), f, default_flow_style=False, sort_keys=False)
