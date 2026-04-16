"""cli/main.py -- Entry point for Step 13: Multi-Layer Prompts."""
from __future__ import annotations
import asyncio
import logging
from pathlib import Path
from typing import Optional
import typer
import uvicorn
from rich.console import Console
from mybot.channel.cli_channel import CLIChannel
from mybot.channel.telegram import TelegramChannel
from mybot.core.agent_loader import AgentLoader
from mybot.core.context import AppContext
from mybot.core.cron_loader import CronLoader
from mybot.core.eventbus import EventBus
from mybot.core.history import HistoryStore
from mybot.core.prompt_builder import PromptBuilder
from mybot.core.routing import RoutingTable
from mybot.provider.llm.base import LLMProvider
from mybot.provider.web_read.httpx_provider import HttpxReadProvider
from mybot.provider.web_search.brave import BraveSearchProvider
from mybot.server.agent_worker import AgentWorker
from mybot.server.app import create_app
from mybot.server.channel_worker import ChannelWorker
from mybot.server.cron_worker import CronWorker
from mybot.server.delivery_worker import DeliveryWorker
from mybot.server.heartbeat_worker import HeartbeatWorker
from mybot.server.websocket_worker import WebSocketWorker
from mybot.skills.loader import SkillLoader
from mybot.tools.builtin import BashTool, ReadFileTool, WriteFileTool
from mybot.tools.registry import ToolRegistry
from mybot.tools.skill_tool import create_skill_tool
from mybot.tools.websearch_tool import WebSearchTool
from mybot.tools.webread_tool import WebReadTool
from mybot.utils.config import Config
from mybot.utils.config_reloader import ConfigReloader

app = typer.Typer(name="my-bot", help="BuckClaw -- Step 13: Multi-Layer Prompts", add_completion=False)
console = Console()


@app.command()
def server(
    config: Optional[Path] = typer.Option(None, "--config", "-c", file_okay=True, dir_okay=False),
) -> None:
    """Start the full server."""
    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    workspace_dir = project_root / "default_workspace"
    if config:
        workspace_dir = config.parent
    asyncio.run(_run_server(workspace_dir, project_root, with_websocket=True))


@app.command()
def chat(
    config: Optional[Path] = typer.Option(None, "--config", "-c", file_okay=True, dir_okay=False),
) -> None:
    """Start a CLI-only chat session."""
    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    workspace_dir = project_root / "default_workspace"
    if config:
        workspace_dir = config.parent
    asyncio.run(_run_server(workspace_dir, project_root, with_websocket=False, cli_only=True))


async def _run_server(
    workspace_dir: Path,
    project_root: Path,
    with_websocket: bool = True,
    cli_only: bool = False,
) -> None:
    try:
        cfg = Config.load(workspace_dir)
    except Exception as exc:
        console.print(f"[bold red]Config error:[/bold red] {exc}")
        return

    if cfg.llm.api_key in ("", "YOUR_API_KEY_HERE"):
        console.print("[bold red]No API key.[/bold red]  Edit config.user.yaml.")
        return

    skills_dir   = project_root / "default_workspace" / "skills"
    history_dir  = project_root / ".history"
    pending_dir  = project_root / ".event_store" / "pending"
    crons_dir    = project_root / "default_workspace" / "crons"
    agents_dir   = project_root / "default_workspace" / "agents"

    llm           = LLMProvider(model=cfg.llm.model, api_key=cfg.llm.api_key, api_base=cfg.llm.api_base)
    history_store = HistoryStore(base_dir=history_dir)
    skill_loader  = SkillLoader(skills_dir=skills_dir)
    skill_tool    = create_skill_tool(skill_loader)
    cron_loader   = CronLoader(crons_dir=crons_dir)
    agent_loader  = AgentLoader(agents_dir=agents_dir)

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
        agent_loader=agent_loader, cron_loader=cron_loader,
    )
    context.routing_table = RoutingTable(context=context)

    # Create PromptBuilder
    prompt_builder = PromptBuilder(
        workspace_dir=project_root / "default_workspace",
        cron_loader=cron_loader,
    )
    context.prompt_builder = prompt_builder

    # Build workers
    agent_worker    = AgentWorker(context=context)
    config_reloader = ConfigReloader(config=cfg)
    cron_worker     = CronWorker(context=context)

    channels = [CLIChannel(agent_name=cfg.agent.name, console=console)]
    if not cli_only and cfg.channels.telegram.token not in ("", "YOUR_TELEGRAM_BOT_TOKEN"):
        channels.append(TelegramChannel(token=cfg.channels.telegram.token))

    channel_worker  = ChannelWorker(context=context, channels=channels)
    delivery_worker = DeliveryWorker(context=context, channels=channels, source_map=context.session_source_map)

    ws_worker: WebSocketWorker | None = None
    uvicorn_task = None
    if with_websocket and cfg.api.enabled:
        ws_worker = WebSocketWorker(context=context)
        context.websocket_worker = ws_worker
        fastapi_app = create_app(context)
        uv_config = uvicorn.Config(fastapi_app, host=cfg.api.host, port=cfg.api.port, log_level="warning")
        uv_server = uvicorn.Server(uv_config)
        uvicorn_task = asyncio.create_task(uv_server.serve(), name="uvicorn")
        console.print(f"[dim]WebSocket: ws://{cfg.api.host}:{cfg.api.port}/ws[/dim]")

    # Heartbeat
    heartbeat_worker: HeartbeatWorker | None = None
    if cfg.heartbeat.enabled:
        hb_meta = history_store.create_session(agent_id="heartbeat", agent_name="Heartbeat")
        context.heartbeat_session_id = hb_meta.session_id
        heartbeat_worker = HeartbeatWorker(
            context=context,
            session_id=hb_meta.session_id,
            prompt=cfg.heartbeat.prompt,
            interval_seconds=cfg.heartbeat.interval_seconds,
        )

    await eventbus.start()
    await agent_worker.start()
    await delivery_worker.start()
    if ws_worker:
        await ws_worker.start()
    await cron_worker.start()
    if heartbeat_worker:
        await heartbeat_worker.start()
    await config_reloader.start()

    cron_count = len(cron_loader.discover_crons())
    console.print(f"[dim]Cron: enabled ({cron_count} job(s) found)[/dim]")
    if cfg.heartbeat.enabled:
        console.print(f"[dim]Heartbeat: every {cfg.heartbeat.interval_seconds}s[/dim]")
    console.print()

    try:
        await channel_worker.run()
    finally:
        if uvicorn_task:
            uvicorn_task.cancel()
            try:
                await uvicorn_task
            except (asyncio.CancelledError, Exception):
                pass
        await config_reloader.stop()
        if heartbeat_worker:
            await heartbeat_worker.stop()
        await cron_worker.stop()
        if ws_worker:
            await ws_worker.stop()
        await delivery_worker.stop()
        await agent_worker.stop()
        await eventbus.stop()


if __name__ == "__main__":
    app()
