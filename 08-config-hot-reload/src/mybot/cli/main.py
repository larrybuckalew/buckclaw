"""cli/main.py -- Entry point for Step 08: Config Hot Reload."""
from __future__ import annotations
import asyncio
import logging
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from mybot.cli.adapter import CLIAdapter
from mybot.core.context import AppContext
from mybot.core.eventbus import EventBus
from mybot.core.history import HistoryStore
from mybot.provider.llm.base import LLMProvider
from mybot.provider.web_read.httpx_provider import HttpxReadProvider
from mybot.provider.web_search.brave import BraveSearchProvider
from mybot.server.agent_worker import AgentWorker
from mybot.skills.loader import SkillLoader
from mybot.tools.builtin import BashTool, ReadFileTool, WriteFileTool
from mybot.tools.registry import ToolRegistry
from mybot.tools.skill_tool import create_skill_tool
from mybot.tools.websearch_tool import WebSearchTool
from mybot.tools.webread_tool import WebReadTool
from mybot.utils.config import Config
from mybot.utils.config_reloader import ConfigReloader

app = typer.Typer(name="my-bot", help="BuckClaw tutorial bot -- Step 08: Config Hot Reload", add_completion=False)
console = Console()


@app.command()
def chat(
    config: Optional[Path] = typer.Option(None, "--config", "-c", file_okay=True, dir_okay=False),
) -> None:
    """Start an interactive chat session with config hot-reload."""
    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    workspace_dir = project_root / "default_workspace"
    if config:
        workspace_dir = config.parent
    asyncio.run(_run(workspace_dir, project_root))


async def _run(workspace_dir: Path, project_root: Path) -> None:
    try:
        cfg = Config.load(workspace_dir)
    except Exception as exc:
        console.print(f"[bold red]Config error:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    if cfg.llm.api_key in ("", "YOUR_API_KEY_HERE"):
        console.print("[bold red]No API key found.[/bold red]  Copy config.example.yaml -> config.user.yaml and add your key.")
        return

    skills_dir  = project_root / "default_workspace" / "skills"
    history_dir = project_root / ".history"

    llm           = LLMProvider(model=cfg.llm.model, api_key=cfg.llm.api_key, api_base=cfg.llm.api_base)
    history_store = HistoryStore(base_dir=history_dir)
    skill_loader  = SkillLoader(skills_dir=skills_dir)
    skill_tool    = create_skill_tool(skill_loader)

    tools_list = [
        ReadFileTool(workspace_dir=project_root),
        WriteFileTool(workspace_dir=project_root),
        BashTool(workspace_dir=project_root),
        skill_tool,
    ]
    if cfg.websearch.api_key not in ("", "YOUR_BRAVE_SEARCH_API_KEY"):
        tools_list.append(WebSearchTool(BraveSearchProvider(cfg.websearch.api_key)))
        tools_list.append(WebReadTool(HttpxReadProvider()))
        console.print("[dim]Web tools: enabled[/dim]")

    tool_registry = ToolRegistry(tools_list)
    eventbus      = EventBus()

    session_meta = history_store.create_session(agent_id="my-bot", agent_name=cfg.agent.name)
    console.print(f"[dim]Session: {session_meta.session_id}[/dim]")

    context = AppContext(
        config=cfg,
        eventbus=eventbus,
        llm=llm,
        history_store=history_store,
        tool_registry=tool_registry,
        skill_loader=skill_loader,
    )

    agent_worker    = AgentWorker(context=context)
    cli_adapter     = CLIAdapter(context=context, session_id=session_meta.session_id, console=console)
    config_reloader = ConfigReloader(config=cfg)

    await eventbus.start()
    await agent_worker.start()
    await config_reloader.start()
    console.print("[dim]Config hot-reload: enabled[/dim]\n")

    try:
        await cli_adapter.run()
    finally:
        await config_reloader.stop()
        await agent_worker.stop()
        await eventbus.stop()


if __name__ == "__main__":
    app()
