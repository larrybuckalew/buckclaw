"""channel/cli_channel.py -- CLI as a Channel (wraps stdin/stdout)."""
from __future__ import annotations
import asyncio
import logging
from typing import Awaitable, Callable
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from mybot.channel.base import Channel, EventSource

logger = logging.getLogger(__name__)
MessageCallback = Callable[[str, EventSource], Awaitable[None]]

CLI_SOURCE = EventSource(platform="cli", user_id="local", chat_id="local")


class CLIChannel(Channel[EventSource]):
    """Terminal channel -- reads stdin, writes stdout."""

    platform_name = "cli"

    def __init__(self, agent_name: str, console: Console | None = None) -> None:
        self._agent_name = agent_name
        self._console = console or Console()
        self._stop_event = asyncio.Event()
        self._pending_reply: asyncio.Future | None = None

    async def run(self, on_message: MessageCallback) -> None:
        self._print_banner()
        try:
            while not self._stop_event.is_set():
                raw = await asyncio.to_thread(self._read_input)
                if raw.lower() in ("quit", "exit", "q"):
                    self._console.print("\n[bold yellow]Goodbye\![/bold yellow]")
                    self._stop_event.set()
                    break
                if raw.strip():
                    await on_message(raw, CLI_SOURCE)
        except (KeyboardInterrupt, EOFError):
            self._console.print("\n[bold yellow]Goodbye\![/bold yellow]")
            self._stop_event.set()

    async def reply(self, content: str, source: EventSource) -> None:
        self._console.print(f"\n[bold blue]{self._agent_name}:[/bold blue] {content}\n")

    async def stop(self) -> None:
        self._stop_event.set()

    def _print_banner(self) -> None:
        self._console.print(
            Panel(Text(f"Welcome to {self._agent_name}\!", style="bold cyan"),
                  title="Chat", border_style="cyan")
        )
        self._console.print("Type [bold]quit[/bold] or [bold]exit[/bold] to end the session.\n")

    def _read_input(self) -> str:
        try:
            return input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            return "quit"
