"""
cli/chat.py — Interactive CLI chat loop.

Responsibilities
────────────────
• Render a welcome banner (rich Panel).
• Read user input from stdin in a thread so the async event loop stays free.
• Forward input to AgentSession.chat() and display the reply.
• Handle quit/exit commands and keyboard interrupts gracefully.

Design notes
────────────
• asyncio.to_thread() is used for the blocking input() call — this keeps
  the event loop unblocked and makes it easy to add background tasks later
  (e.g. the cron heartbeat in step 12).
• rich.Console is injected at construction time, making it easy to swap
  out in tests or pipe output to a file.
"""

from __future__ import annotations

import asyncio

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from mybot.core.agent import AgentSession


class ChatLoop:
    """Drives the interactive CLI session."""

    def __init__(self, session: AgentSession, console: Console | None = None) -> None:
        self.session = session
        self.console = console or Console()

    # ── Public entry point ────────────────────────────────────────────────

    async def run(self) -> None:
        """Start the chat loop.  Runs until the user types quit/exit."""
        self._print_banner()

        try:
            while True:
                user_input = await asyncio.to_thread(self._get_user_input)

                if user_input.lower() in ("quit", "exit", "q"):
                    self.console.print("\n[bold yellow]Goodbye![/bold yellow]")
                    break

                if not user_input.strip():
                    continue

                try:
                    response = await self.session.chat(user_input)
                    self._display_response(response)
                except Exception as exc:  # noqa: BLE001
                    self.console.print(f"\n[bold red]Error:[/bold red] {exc}\n")

        except (KeyboardInterrupt, EOFError):
            self.console.print("\n[bold yellow]Goodbye![/bold yellow]")

    # ── Private helpers ───────────────────────────────────────────────────

    def _print_banner(self) -> None:
        name = self.session.agent.name
        self.console.print(
            Panel(
                Text(f"Welcome to {name}!", style="bold cyan"),
                title="Chat",
                border_style="cyan",
            )
        )
        self.console.print("Type [bold]quit[/bold] or [bold]exit[/bold] to end the session.\n")

    def _get_user_input(self) -> str:
        """Blocking stdin read — called via asyncio.to_thread()."""
        try:
            return input("[bold green]You:[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            return "quit"

    def _display_response(self, response: str) -> None:
        name = self.session.agent.name
        self.console.print(f"\n[bold blue]{name}:[/bold blue] {response}\n")
