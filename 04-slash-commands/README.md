# Step 04: Slash Commands

Slash commands provide a lightweight way for users to interact with the agent through special commands that begin with `/`. They are dispatched before reaching the LLM, so they do not appear in conversation history or affect the LLM's context.

## Architecture

### Command Structure

The slash command system is built around three core components:

1. **Command (base.py)** -- Abstract base class for all commands
   - `name: str` -- Command name (e.g. "help")
   - `aliases: list[str]` -- Alternative names (e.g. ["?"])
   - `description: str` -- Short description for help text
   - `async execute(args: str, session: AgentSession) -> str` -- Run the command

2. **CommandRegistry (registry.py)** -- Central dispatcher
   - Registers commands by name and aliases
   - Parses input string (splits on first space)
   - Routes commands case-insensitively
   - Returns helpful error for unknown commands

3. **ChatLoop (cli/chat.py)** -- Dispatch integration
   - Before sending user input to the LLM
   - Calls `registry.dispatch(input_str, session)`
   - Returns early if command handled (None)
   - Proceeds to LLM if no command matched

### Flow Diagram

```
User input
    |
    v
ChatLoop.run()
    |
    ├─► /command? ────Yes────► registry.dispatch()
    |                               |
    |                               v
    |                          Command.execute()
    |                               |
    |                               v
    |                          Print response
    |                          Continue loop
    |
    No
    |
    v
AgentSession.chat()
    |
    v
LLM (with tools)
    |
    v
Print response
Continue loop
```

## Built-in Commands

### /help (alias: /?)

Display all available commands with their descriptions.

Example:
```
You: /help
Available Commands:
/help, /? - Show available commands
/skills - List available skills
/session - Show current session info
```

### /skills

List available skills that can be called via the skill tool.

Example:
```
You: /skills
Available Skills:
- skill-creator
- code-reviewer
- pdf
- docx
```

Falls back gracefully if no skill loader is available.

### /session

Show current session metadata and statistics.

Example:
```
You: /session
Session Info:
ID: abc123def456
Agent: MyBot
Created: 2026-04-16T10:30:00Z
Messages: 5
```

## Design Notes

**Commands don't appear in LLM history:** Slash commands are intentionally dispatched before reaching the LLM. The user input never reaches the conversation state, so commands don't influence the LLM's context or appear in saved message history.

**Case-insensitive dispatch:** Commands are matched case-insensitively, so `/Help`, `/HELP`, and `/help` all work.

**Early return for unknown commands:** If input starts with `/` but the command is not found, dispatch returns a helpful error message without reaching the LLM.

**Optional registry:** AgentSession accepts an optional CommandRegistry. If None, a new empty registry is created. This allows CLI integration to work with or without slash commands.

## Try It Out

Start the bot:
```bash
my-bot chat
```

Try the built-in commands:
```
You: /help
Available Commands:
/help, /? - Show available commands
/skills - List available skills
/session - Show current session info

You: /session
Session Info:
ID: abc123def456
Agent: MyBot
Created: 2026-04-16T10:30:00Z
Messages: 0

You: /skills
Available Skills:
- skill-creator
- code-reviewer
(list continues...)

You: Hello, how are you?
(normal LLM response appears)

You: /? 
Available Commands:
(help output)
```

Invalid commands return a helpful message:
```
You: /unknown
Unknown command: /unknown. Type /help for available commands.
```

## Adding Custom Commands

To add a new command, extend the `Command` base class:

```python
from mybot.core.commands.base import Command
from mybot.core.agent import AgentSession

class MyCommand(Command):
    name = "mycommand"
    aliases = ["mc"]
    description = "My custom command"
    
    async def execute(self, args: str, session: AgentSession) -> str:
        return f"You said: {args}"
```

Then register it in main.py:
```python
cmd_registry.register(MyCommand())
```

## Files Modified/Created

### New Files
- `src/mybot/core/commands/__init__.py` -- Module exports
- `src/mybot/core/commands/base.py` -- Command abstract base class
- `src/mybot/core/commands/registry.py` -- CommandRegistry dispatcher
- `src/mybot/core/commands/builtin.py` -- Built-in commands (help, skills, session)

### Updated Files
- `src/mybot/core/agent.py` -- Added command_registry to AgentSession
- `src/mybot/cli/chat.py` -- Dispatch commands before LLM
- `src/mybot/cli/main.py` -- Build and inject command registry
- `pyproject.toml` -- Version bump to 0.5.0

## Version Info

- Step: 04
- Version: 0.5.0
- Focus: Slash Commands / CLI Enhancement
