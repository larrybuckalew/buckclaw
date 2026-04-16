"""cli/main.py -- Typer application and entry point.

Usage:
  uv run my-bot chat
  uv run my-bot chat --config path/to/config.yaml
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from mybot.cli.chat import ChatLoop
from mybot.config import load_config
from mybot.core.agent import Agent, AgentSession
from mybot.provider.llm.base import LLMProvider
from mybot.tools.builtin import BashTool, ReadFileTool, WriteFileTool
from mybot.tools.registry import ToolRegistry

app = typer.Typer(
    name="my-bot",
    help="BuckClaw tutorial bot -- Step 01: Tools",
    add_completion=False,
)

console = Console()


@app.command()
def chat(
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to a YAML config file (default: default_workspace/config.user.yaml).",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
) -> None:
    """Start an interactive chat session."""
    # 1. Load config.
    try:
        cfg = load_config(config)
    except FileNotFoundError as exc:
        console.print(f"[bold red]Config error:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    if cfg.llm.api_key in ("", "YOUR_API_KEY_HERE"):
        console.print(
            "[bold red]No API key found.[/bold red]  "
            "Copy [cyan]default_workspace/config.example.yaml[/cyan] -> "
            "[cyan]config.user.yaml[/cyan] and add your key."
        )
        raise typer.Exit(1)

    # 2. Wire up the object graph.
    # workspace = two levels up from src/mybot/cli/ -> project root
    workspace = Path(__file__).resolve().parent.parent.parent.parent.parent

    llm = LLMProvider(
        model=cfg.llm.model,
        api_key=cfg.llm.api_key,
        api_base=cfg.llm.api_base,
    )
    tools = ToolRegistry(
        [
            ReadFileTool(workspace_dir=workspace),
            WriteFileTool(workspace_dir=workspace),
            BashTool(workspace_dir=workspace),
        ]
    )
    agent = Agent(llm=llm, name=cfg.agent.name, system_prompt=cfg.agent.system_prompt)
    session = AgentSession(agent=agent, tools=tools)
    loop = ChatLoop(session=session, console=console)

    # 3. Run the async chat loop.
    asyncio.run(loop.run())


if __name__ == "__main__":
    app()
