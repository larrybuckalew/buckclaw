"""cli/main.py -- Entry point for Step 06: Web Tools."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from mybot.cli.chat import ChatLoop
from mybot.config import load_config
from mybot.core.agent import Agent, AgentSession
from mybot.core.commands import HelpCommand, SessionCommand, SkillsCommand
from mybot.core.commands.builtin import CompactCommand, ContextCommand
from mybot.core.context_guard import ContextGuard
from mybot.core.commands import CommandRegistry
from mybot.core.history import HistoryStore
from mybot.provider.llm.base import LLMProvider
from mybot.provider.web_search.brave import BraveSearchProvider
from mybot.provider.web_read.httpx_provider import HttpxReadProvider
from mybot.skills.loader import SkillLoader
from mybot.tools.builtin import BashTool, ReadFileTool, WriteFileTool
from mybot.tools.registry import ToolRegistry
from mybot.tools.skill_tool import create_skill_tool
from mybot.tools.websearch_tool import WebSearchTool
from mybot.tools.webread_tool import WebReadTool

app = typer.Typer(
    name="my-bot",
    help="BuckClaw tutorial bot -- Step 06: Web Tools",
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

    tools_list = [
        ReadFileTool(workspace_dir=workspace),
        WriteFileTool(workspace_dir=workspace),
        BashTool(workspace_dir=workspace),
        skill_tool,
    ]

    # Wire up web tools if configured
    if cfg.websearch.api_key not in ("", "YOUR_BRAVE_SEARCH_API_KEY"):
        tools_list.append(WebSearchTool(BraveSearchProvider(cfg.websearch.api_key)))
        tools_list.append(WebReadTool(HttpxReadProvider()))

    tools = ToolRegistry(tools_list)

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
    cmd_registry.register(ContextCommand())
    cmd_registry.register(CompactCommand())

    # Create context guard for managing context size
    context_guard = ContextGuard()

    agent   = Agent(llm=llm, name=cfg.agent.name, system_prompt=cfg.agent.system_prompt)
    session = AgentSession(
        agent=agent,
        tools=tools,
        history_store=history_store,
        session_meta=session_meta,
        command_registry=cmd_registry,
        context_guard=context_guard,
    )
    loop    = ChatLoop(session=session, console=console)

    discovered = skill_loader.discover_skills()
    if discovered:
        names = ", ".join(s.name for s in discovered)
        console.print(f"[dim]Skills loaded: {names}[/dim]")
    else:
        console.print("[dim]No skills found in default_workspace/skills/[/dim]")

    # Print active tools
    active_tools = [t.name for t in tools_list]
    console.print(f"[dim]Tools: {', '.join(active_tools)}[/dim]\n")

    asyncio.run(loop.run())


if __name__ == "__main__":
    app()
