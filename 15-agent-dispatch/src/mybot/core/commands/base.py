from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mybot.core.agent import AgentSession


class Command(ABC):
    """Abstract base class for slash commands."""
    
    name: str
    aliases: list[str] = []
    description: str = ""
    
    @abstractmethod
    async def execute(self, args: str, session: "AgentSession") -> str:
        """Execute the command and return a response string.
        
        Args:
            args: Arguments passed to the command (everything after the command name).
            session: The current agent session.
            
        Returns:
            A string response to display to the user.
        """
        pass
