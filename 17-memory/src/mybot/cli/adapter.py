"""cli/adapter.py -- CLI adapter for the event-driven architecture.

Replaces ChatLoop. Publishes InboundEvents for each user message and
displays OutboundEvents as they arrive. Uses an asyncio.Future per
session to correlate requests with responses.
"""
from __future__ import annotations
import asyncio
import logging

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from mybot.core.context import AppContext
from mybot.core.events import InboundEvent, OutboundEvent
from mybot.core.worker import Worker

logger = logging.getLogger(__name__)


class CLIAdapter(Worker):
    """
    Drives the interactive terminal session using the event bus.

    Input side : reads stdin, publishes InboundEvent.
    Output side: subscribed to OutboundEvent, prints replies.
    """

    def __init__(
        self,
        context: AppContext,
        session_id: str,
        console: Console | None = None,
    ) -> None:
        super().__init__()
        self.context = context
        self.session_id = session_id
        self.console = console or Console()
        self._pending: asyncio.Future | None = None

        context.eventbus.subscribe(OutboundEvent, self._handle_outbound)

    async def _handle_outbound(self, event: OutboundEvent) -> None:
        if event.session_id == self.session_id:
            if self._pending and not self._pending.done():
                self._pending.set_result(event)

    async def run(self) -> None:
        """Main chat loop -- identical UX to the old ChatLoop."""
        agent_name = self.context.config.agent.name
        self._print_banner(agent_name)

        try:
            while True:
                user_input = await asyncio.to_thread(self._read_input)

                if user_input.lower() in ("quit", "exit", "q"):
                    self.console.print("\n[bold yellow]Goodbye\![/bold yellow]")
                    break

                if not user_input.strip():
                    continue

                # Handle slash commands locally (no event bus round-trip needed).
                if hasattr(self, "_command_registry") and self._command_registry:
                    pass  # command dispatch is handled in main.py before this

                # Publish the message and wait for the response.
                loop = asyncio.get_event_loop()
                self._pending = loop.create_future()

                await self.context.eventbus.publish(
                    InboundEvent(session_id=self.session_id, content=user_input)
                )

                try:
                    result: OutboundEvent = await asyncio.wait_for(self._pending, timeout=120)
                    if result.error:
                        self.console.print(f"\n[bold red]Error:[/bold red] {result.error}\n")
                    else:
                        self.console.print(f"\n[bold blue]{agent_name}:[/bold blue] {result.content}\n")
                except asyncio.TimeoutError:
                    self.console.print("\n[bold red]Timeout waiting for response.[/bold red]\n")

        except (KeyboardInterrupt, EOFError):
            self.console.print("\n[bold yellow]Goodbye\![/bold yellow]")

    def _print_banner(self, agent_name: str) -> None:
        self.console.print(
            Panel(Text(f"Welcome to {agent_name}\!", style="bold cyan"),
                  title="Chat", border_style="cyan")
        )
        self.console.print("Type [bold]quit[/bold] or [bold]exit[/bold] to end the session.\n")

    def _read_input(self) -> str:
        try:
            return input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            return "quit"
