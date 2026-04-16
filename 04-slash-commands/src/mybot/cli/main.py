"""cli/main.py -- Entry point for Step 04: Slash Commands."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from mybot.cli.chat import ChatLoop
from mybot.config import load_config
from mybot.core.agent import Agent, AgentSession
from mybot.core.commands import CommandRegistry, HelpCommand, SessionCommand, SkillsCommand
from mybot.core.history import HistoryStore
from mybot.provider.llm.base import LLMProvider
from mybot.skills.loader import SkillLoader
from mybot.tools.builtin import BashTool, ReadFileTool, WriteFileTool
from mybot.tools.registry import ToolRegistry
from mybot.tools.skill_tool import create_skill_tool

app = typer.Typer(
    name="my-bot",
    help="BuckClaw tutorial bot -- Step 04: Slash Commands",
    add_completion=False,
)

console = Console()


@app.command()
def chat(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c",
        help="Path to a YAML config file.",
        exists=True, file_okay=True, dir_okay=False,
    ),
) -> None:
    """Start an interactive chat session."""
    try:
        cfg = load_config(config)
    except FileNotFoundError as exc:
        console.print(f"[bold red]Config error:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    if cfg.llm.api_key in ("", "YOUR_API_KEY_HERE"):
        console.print(
            "[bold red]No API key found.[/bold red]  "
            "Copy default_workspace/config.example.yaml -> config.user.yaml and add your key."
        )
        raise typer.Exit(1)

    # Resolve paths relative to the project root (parent of src/)
    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    workspace    = project_root
    skills_dir   = project_root / "default_workspace" / "skills"

    llm = LLMProvider(
        model=cfg.llm.model,
        api_key=cfg.llm.api_key,
        api_base=cfg.llm.api_base,
    )

    skill_loader = SkillLoader(skills_dir=skills_dir)
    skill_tool   = create_skill_tool(skill_loader)

    tools = ToolRegistry(
        [
            ReadFileTool(workspace_dir=workspace),
            WriteFileTool(workspace_dir=workspace),
            BashTool(workspace_dir=workspace),
            skill_tool,
        ]
    )

    # Initialize history store and create a new session
    history_store = HistoryStore(base_dir=project_root / ".history")
    session_meta = history_store.create_session(
        agent_id="my-bot",
        agent_name=cfg.agent.name,
    )
    console.print(f"[dim]Session ID: {session_meta.session_id}[/dim]")

    # Build command registry
    cmd_registry = CommandRegistry()
    cmd_registry.register(HelpCommand())
    cmd_registry.register(SkillsCommand(skill_loader=skill_loader))
    cmd_registry.register(SessionCommand())

    agent   = Agent(llm=llm, name=cfg.agent.name, system_prompt=cfg.agent.system_prompt)
    session = AgentSession(
        agent=agent,
        tools=tools,
        history_store=history_store,
        session_meta=session_meta,
        command_registry=cmd_registry,
    )
    loop    = ChatLoop(session=session, console=console)

    discovered = skill_loader.discover_skills()
    if discovered:
        names = ", ".join(s.name for s in discovered)
        console.print(f"[dim]Skills loaded: {names}[/dim]\n")
    else:
        console.print("[dim]No skills found in default_workspace/skills/[/dim]\n")

    asyncio.run(loop.run())


if __name__ == "__main__":
    app()
