# Step 11: Multi-Agent Routing

This step adds **multi-agent capability** to BuckClaw, enabling config-driven routing of messages to different specialized agents based on the source/channel they come from.

## Problem Solved

Previously, a single agent handled all messages from all sources. Now:
- Route messages from different channels to different agents (e.g., Telegram -> Summarizer, WebSocket -> General Bot)
- Define specialized agents with custom system prompts
- Create new agents by adding AGENT.md files
- Use regex patterns to map sources to agents
- Change routing at runtime with slash commands

## Key Concepts

### Agent Definition (AGENT.md)

Agents are defined as markdown files with YAML front-matter:

```markdown
---
id: my-bot
name: my-bot
description: A friendly and helpful AI assistant for general tasks.
---

You are my-bot, a friendly and helpful AI assistant.
Be concise, clear, and always ready to help.
```

Files must:
- Reside in `default_workspace/agents/<agent-id>/AGENT.md`
- Have YAML front-matter between `---` lines with fields: `id`, `name`, `description`
- Have the body (after front-matter) be the system prompt

### AgentLoader

Discovers and caches agent definitions from the agents directory:

```python
loader = AgentLoader(agents_dir=Path("default_workspace/agents"))
agents = loader.discover_agents()  # List all agents
agent_def = loader.load("summarizer")  # Load by id
```

### Routing

**Binding**: Maps a source pattern (regex) to an agent id.

**Specificity Tier**:
- **Tier 0** -- exact match (no regex metacharacters) -- highest priority
- **Tier 1** -- specific regex (has metacharacters but not `.*`)
- **Tier 2** -- wildcard (contains `.*`) -- lowest priority

**RoutingTable**: Resolves an EventSource to an agent id:

```python
routing_table = RoutingTable(context=context)
agent_id = routing_table.resolve("platform-ws:user-123")
routing_table.add_binding("platform-ws:.*", "summarizer")  # Add at runtime
```

Bindings are loaded from config and sorted most-specific-first. The first matching binding wins.

### EventSource Flow

1. **ChannelWorker** receives a message with source `EventSource`
2. Calls `routing_table.resolve(str(source))` to get agent_id
3. Creates or retrieves session with that agent_id
4. **AgentWorker** loads agent definition from session metadata
5. Initializes agent with correct name and system_prompt

## Configuration

Add to `config.user.yaml`:

```yaml
routing:
  bindings:
    - agent: summarizer
      value: platform-ws:.*
    - agent: my-bot
      value: telegram
  
default_agent: my-bot
```

At runtime, use `/route` command to add bindings (persisted to `config.runtime.yaml`).

## New Slash Commands

### `/agents`
Lists all discovered agents with a marker for the current agent.
```
Agents:
- my-bot: A friendly and helpful AI assistant (current)
- summarizer: Specialist agent for summarizing documents
```

### `/bindings`
Shows current routing bindings sorted by specificity (most specific first).
```
Routing Bindings (most specific first):
1. `summarizer` -> `platform-ws:.*`  [tier: 2]
2. `my-bot` -> `telegram`  [tier: 1]
```

### `/route <source_pattern> <agent_id>`
Adds a new binding at runtime.
```
/route "platform-ws:.*" summarizer
Route bound: `platform-ws:.*` -> `summarizer`
```

## Files Changed

### New Files

- `src/mybot/core/agent_loader.py` -- AgentDef dataclass and AgentLoader discovery
- `src/mybot/core/routing.py` -- Binding and RoutingTable for source-to-agent mapping
- `default_workspace/agents/my-bot/AGENT.md` -- General-purpose bot agent
- `default_workspace/agents/summarizer/AGENT.md` -- Summarizer specialist agent

### Modified Files

- `src/mybot/utils/config.py` -- Added `routing` and `default_agent` fields
- `src/mybot/core/context.py` -- Added `agent_loader` and `routing_table` fields
- `src/mybot/server/channel_worker.py` -- Use routing_table to pick agent when creating session
- `src/mybot/server/agent_worker.py` -- Load agent definition from session metadata
- `src/mybot/core/commands/builtin.py` -- Added AgentsCommand, BindingsCommand, RouteCommand
- `src/mybot/cli/main.py` -- Initialize AgentLoader and RoutingTable; register new commands
- `pyproject.toml` -- Version 0.12.0, updated description

## Try It Out

1. **List agents:**
   ```
   /agents
   ```

2. **Check current bindings:**
   ```
   /bindings
   ```

3. **Add a binding:**
   ```
   /route "platform-ws:.*" summarizer
   ```

4. **Edit config.user.yaml** to add permanent bindings:
   ```yaml
   routing:
     bindings:
       - agent: summarizer
         value: "platform-ws:.*"
   ```

5. **Create a new agent** at `default_workspace/agents/math-tutor/AGENT.md`:
   ```markdown
   ---
   id: math-tutor
   name: Math Tutor
   description: Specialist at teaching mathematics clearly and patiently
   ---
   
   You are Math Tutor, an expert educator...
   ```

6. **Route to it:**
   ```
   /route "telegram" math-tutor
   ```

## What Changed from Step 10

- Added agent definitions (AGENT.md files)
- Added agent loader to discover agents
- Added routing table for source-to-agent mapping
- ChannelWorker now routes messages to different agents based on source
- AgentWorker loads correct agent definition based on session metadata
- Three new slash commands: /agents, /bindings, /route
- Config extended with `routing` and `default_agent` fields

## What's Next

**Step 12: Cron Heartbeat** will add scheduled tasks that run on intervals (e.g., daily digest, periodic status check).
