from typing import TYPE_CHECKING

from mybot.core.commands.base import Command

if TYPE_CHECKING:
    from mybot.core.agent import AgentSession


class CommandRegistry:
    """Registry for slash commands."""
    
    def __init__(self):
        """Initialize the command registry."""
        self._commands: dict[str, Command] = {}
    
    def register(self, cmd: Command) -> None:
        """Register a command by name and aliases.
        
        Args:
            cmd: The command to register.
        """
        self._commands[cmd.name.lower()] = cmd
        for alias in cmd.aliases:
            self._commands[alias.lower()] = cmd
    
    async def dispatch(self, input_str: str, session: "AgentSession") -> str | None:
        """Dispatch a command if input starts with '/'.
        
        Args:
            input_str: The user input string.
            session: The current agent session.
            
        Returns:
            The command response, or None if input doesn't start with '/'.
        """
        if not input_str.startswith("/"):
            return None
        
        # Parse command and args
        parts = input_str[1:].split(None, 1)
        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # Look up command
        if cmd_name not in self._commands:
            return f"Unknown command: /{cmd_name}. Type /help for available commands."
        
        # Execute command
        cmd = self._commands[cmd_name]
        return await cmd.execute(args, session)
    
    def get_commands(self) -> dict[str, Command]:
        """Get all registered commands.
        
        Returns:
            Dictionary mapping command names to Command objects.
        """
        seen = set()
        result = {}
        for name, cmd in self._commands.items():
            if cmd.name not in seen:
                result[cmd.name] = cmd
                seen.add(cmd.name)
        return result
