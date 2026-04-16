"""cli/main.py -- Entry point for Step 09: Channels."""
from __future__ import annotations
import asyncio
import logging
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from mybot.channel.cli_channel import CLIChannel
from mybot.channel.telegram import TelegramChannel
from mybot.core.context import AppContext
from mybot.core.eventbus import EventBus
from mybot.core.history import HistoryStore
from mybot.provider.llm.base import LLMProvider
from mybot.provider.web_read.httpx_provider import HttpxReadProvider
from mybot.provider.web_search.brave import BraveSearchProvider
from mybot.server.agent_worker import AgentWorker
from mybot.server.channel_worker import ChannelWorker
from mybot.server.delivery_worker import DeliveryWorker
from mybot.skills.loader import SkillLoader
from mybot.tools.builtin import BashTool, ReadFileTool, WriteFileTool
from mybot.tools.registry import ToolRegistry
from mybot.tools.skill_tool import create_skill_tool
from mybot.tools.websearch_tool import WebSearchTool
from mybot.tools.webread_tool import WebReadTool
from mybot.utils.config import Config
from mybot.utils.config_reloader import ConfigReloader

app = typer.Typer(name="my-bot", help="BuckClaw tutorial bot -- Step 09: Channels", add_completion=False)
console = Console()


@app.command()
def server(
    config: Optional[Path] = typer.Option(None, "--config", "-c", file_okay=True, dir_okay=False),
) -> None:
    """Start the agent server with all configured channels."""
    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    workspace_dir = project_root / "default_workspace"
    if config:
        workspace_dir = config.parent
    asyncio.run(_run_server(workspace_dir, project_root))


@app.command()
def chat(
    config: Optional[Path] = typer.Option(None, "--config", "-c", file_okay=True, dir_okay=False),
) -> None:
    """Start a CLI-only chat session (no Telegram)."""
    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    workspace_dir = project_root / "default_workspace"
    if config:
        workspace_dir = config.parent
    asyncio.run(_run_server(workspace_dir, project_root, cli_only=True))


async def _run_server(workspace_dir: Path, project_root: Path, cli_only: bool = False) -> None:
    try:
        cfg = Config.load(workspace_dir)
    except Exception as exc:
        console.print(f"[bold red]Config error:[/bold red] {exc}")
        return

    if cfg.llm.api_key in ("", "YOUR_API_KEY_HERE"):
        console.print("[bold red]No API key.[/bold red]  Edit config.user.yaml.")
        return

    skills_dir  = project_root / "default_workspace" / "skills"
    history_dir = project_root / ".history"
    pending_dir = project_root / ".event_store" / "pending"

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

    tool_registry = ToolRegistry(tools_list)
    eventbus      = EventBus(pending_dir=pending_dir)

    context = AppContext(
        config=cfg, eventbus=eventbus, llm=llm,
        history_store=history_store, tool_registry=tool_registry, skill_loader=skill_loader,
    )

    # Build channels
    channels = [CLIChannel(agent_name=cfg.agent.name, console=console)]
    if not cli_only and cfg.channels.telegram.token not in ("", "YOUR_TELEGRAM_BOT_TOKEN"):
        channels.append(TelegramChannel(token=cfg.channels.telegram.token))
        console.print("[dim]Telegram channel: enabled[/dim]")

    agent_worker    = AgentWorker(context=context)
    channel_worker  = ChannelWorker(context=context, channels=channels)
    delivery_worker = DeliveryWorker(
        context=context,
        channels=channels,
        source_map=context.session_source_map,
    )
    config_reloader = ConfigReloader(config=cfg)

    await eventbus.start()
    await agent_worker.start()
    await delivery_worker.start()
    await config_reloader.start()

    console.print(f"[dim]Config hot-reload: enabled[/dim]")
    console.print(f"[dim]Channels: {[ch.platform_name for ch in channels]}[/dim]\n")

    try:
        await channel_worker.run()  # blocks until all channels stop
    finally:
        await config_reloader.stop()
        await delivery_worker.stop()
        await agent_worker.stop()
        await eventbus.stop()


if __name__ == "__main__":
    app()
