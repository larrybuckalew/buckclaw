from typing import TYPE_CHECKING, Optional

from mybot.core.commands.base import Command

if TYPE_CHECKING:
    from mybot.core.agent import AgentSession
    from mybot.skills.loader import SkillLoader


class HelpCommand(Command):
    """Display available commands."""
    
    name = "help"
    aliases = ["?"]
    description = "Show available commands"
    
    async def execute(self, args: str, session: "AgentSession") -> str:
        """Execute help command."""
        if not session.command_registry:
            return "No command registry available."
        
        commands = session.command_registry.get_commands()
        lines = ["Available Commands:"]
        
        for cmd in sorted(commands.values(), key=lambda c: c.name):
            cmd_names = f"/{cmd.name}"
            if cmd.aliases:
                cmd_names += ", " + ", ".join(f"/{alias}" for alias in cmd.aliases)
            description = cmd.description or "No description"
            lines.append(f"{cmd_names} - {description}")
        
        return "\n".join(lines)


class SkillsCommand(Command):
    """List available skills."""
    
    name = "skills"
    aliases = []
    description = "List available skills"
    
    def __init__(self, skill_loader: Optional["SkillLoader"] = None):
        """Initialize with optional skill loader.
        
        Args:
            skill_loader: The skill loader instance.
        """
        self.skill_loader = skill_loader
    
    async def execute(self, args: str, session: "AgentSession") -> str:
        """Execute skills command."""
        if not self.skill_loader:
            return "Skill loader not available."
        
        try:
            skills = self.skill_loader.discover_skills()
            if not skills:
                return "No skills available."
            
            lines = ["Available Skills:"]
            for skill_name in sorted(skills.keys()):
                lines.append(f"- {skill_name}")
            
            return "\n".join(lines)
        except Exception as e:
            return f"Failed to load skills: {e}"


class SessionCommand(Command):
    """Show current session information."""
    
    name = "session"
    aliases = []
    description = "Show current session info"
    
    async def execute(self, args: str, session: "AgentSession") -> str:
        """Execute session command."""
        lines = ["Session Info:"]
        
        if hasattr(session, 'session_meta') and session.session_meta:
            session_id = session.session_meta.get('id', 'N/A')
            agent_name = session.session_meta.get('agent_name', 'N/A')
            created_at = session.session_meta.get('created_at', 'N/A')
            lines.append(f"ID: {session_id}")
            lines.append(f"Agent: {agent_name}")
            lines.append(f"Created: {created_at}")
        else:
            lines.append("ID: N/A")
            lines.append("Agent: N/A")
            lines.append("Created: N/A")
        
        message_count = 0
        if hasattr(session, 'state') and session.state and hasattr(session.state, 'message_count'):
            message_count = session.state.message_count
        lines.append(f"Messages: {message_count}")
        
        return "\n".join(lines)


class ContextCommand(Command):
    """Show current context usage and token estimates."""
    
    name = "context"
    aliases = []
    description = "Show context usage and token count"
    
    async def execute(self, args: str, session: "AgentSession") -> str:
        """Execute context command."""
        if not hasattr(session, 'context_guard') or not session.context_guard:
            return "Context guard not available."
        
        token_count = session.context_guard.estimate_tokens(
            session.state, session.agent.llm.model
        )
        threshold = session.context_guard.token_threshold
        percentage = int((token_count / threshold) * 100)
        message_count = session.state.message_count
        
        lines = [
            "Context Usage:",
            f"Messages: {message_count}",
            f"Tokens: ~{token_count} ({percentage}% of {threshold} threshold)",
        ]
        
        return "\n".join(lines)


class CompactCommand(Command):
    """Manually trigger context compaction."""
    
    name = "compact"
    aliases = []
    description = "Manually compact conversation context"
    
    async def execute(self, args: str, session: "AgentSession") -> str:
        """Execute compact command."""
        if not hasattr(session, 'context_guard') or not session.context_guard:
            return "Context guard not available."
        
        initial_count = session.state.message_count
        new_state = await session.context_guard._compact_messages(
            session.state, session.agent.llm, session.agent.llm.model
        )
        session.state = new_state
        final_count = session.state.message_count
        
        return f"Context compacted. {final_count} message(s) retained (was {initial_count})."


class AgentsCommand(Command):
    """List all available agents."""
    
    name = "agents"
    aliases = []
    description = "List all available agents"
    
    def __init__(self, agent_loader=None, current_agent_id="my-bot"):
        """Initialize with optional agent loader.
        
        Args:
            agent_loader: The agent loader instance.
            current_agent_id: The currently active agent id.
        """
        self._agent_loader = agent_loader
        self._current_agent_id = current_agent_id
    
    async def execute(self, args: str, session: "AgentSession") -> str:
        """Execute agents command."""
        if not self._agent_loader:
            return "Agent loader not available."
        agents = self._agent_loader.discover_agents()
        if not agents:
            return "No agents found in agents directory."
        lines = ["**Agents:**"]
        for a in agents:
            marker = " (current)" if a.id == self._current_agent_id else ""
            lines.append(f"- `{a.id}`: {a.description}{marker}")
        return "\n".join(lines)


class BindingsCommand(Command):
    """Show current routing bindings."""
    
    name = "bindings"
    aliases = []
    description = "Show current routing bindings"
    
    def __init__(self, routing_table=None):
        """Initialize with optional routing table.
        
        Args:
            routing_table: The routing table instance.
        """
        self._routing_table = routing_table
    
    async def execute(self, args: str, session: "AgentSession") -> str:
        """Execute bindings command."""
        if not self._routing_table:
            return "Routing table not configured."
        bindings = self._routing_table.list_bindings()
        if not bindings:
            return "No routing bindings configured."
        lines = ["**Routing Bindings** (most specific first):"]
        for i, b in enumerate(bindings, 1):
            lines.append(f"{i}. `{b.value}` -> `{b.agent}`  [tier: {b.tier}]")
        return "\n".join(lines)


class RouteCommand(Command):
    """Add a routing rule."""
    
    name = "route"
    aliases = []
    description = "Add a routing rule: /route <source_pattern> <agent_id>"
    
    def __init__(self, routing_table=None):
        """Initialize with optional routing table.
        
        Args:
            routing_table: The routing table instance.
        """
        self._routing_table = routing_table
    
    async def execute(self, args: str, session: "AgentSession") -> str:
        """Execute route command."""
        if not self._routing_table:
            return "Routing table not configured."
        parts = args.strip().split(None, 1)
        if len(parts) != 2:
            return "Usage: /route <source_pattern> <agent_id>"
        pattern, agent_id = parts
        self._routing_table.add_binding(pattern, agent_id)
        return f"Route bound: `{pattern}` -> `{agent_id}`"
