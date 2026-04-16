# Step 17: Memory

> Remember me\!

Long-term memory across all conversations -- Pickle learns your name, preferences,
and any facts you share, then recalls them the next time you start a chat.

---

## Prerequisites

```bash
cp default_workspace/config.example.yaml default_workspace/config.user.yaml
# Edit config.user.yaml and add your API key
```

---

## How It Works

### Approach: Specialized Memory Agent

A dedicated `memory` agent manages all reads and writes.  Pickle dispatches
to it rather than writing files directly, which keeps concerns separated and
makes the memory store easy to audit or extend.

```
User --> Pickle --> subagent_dispatch("memory", "Save: name is Zane")
                         |
                    Memory Agent
                         |
                   write_memory("topics/identity.md", ...)
```

### Memory Directory Layout

```
default_workspace/memories/
  topics/
    identity.md       # name, age, location, pronouns, etc.
    preferences.md    # likes, dislikes, habits
  projects/
    <project>.md      # per-project notes
  daily-notes/
    YYYY-MM-DD.md     # journal / one-off notes
```

Each file is plain markdown, one fact per bullet point.

---

## What Changed

### `src/mybot/tools/memory_tools.py` (new)

Three scoped tools that operate only inside `memories/`:

| Tool | Purpose |
|------|---------|
| `list_memories` | List all `.md` files recursively -- discover what exists |
| `read_memory`   | Read a single memory file by relative path |
| `write_memory`  | Create or overwrite a memory file (auto-creates dirs) |

Paths are validated to prevent escaping the `memories/` directory.

### `default_workspace/agents/memory/AGENT.md` (new)

The Memory agent knows:
- The directory layout
- The recall workflow: `list_memories` -> `read_memory` -> return facts
- The store workflow: `read_memory` (merge) -> `write_memory` -> confirm
- Rules: never invent facts, keep entries concise, no sensitive data

### `default_workspace/agents/my-bot/AGENT.md` (updated)

Pickle is now named **Pickle** and has explicit memory instructions:
- **Start of conversation**: dispatch to `memory` for a full recall
- **New information from user**: dispatch to `memory` to save it
- **User asks about a fact**: dispatch to `memory` to recall the topic

### `src/mybot/cli/main.py` (updated)

Memory tools are registered in the shared `ToolRegistry` alongside the
existing workspace tools.  Because all agents share the registry, the
Memory agent receives them automatically when dispatched.

---

## Try It Out

```bash
cd 17-memory
uv run my-bot chat

# You: Remember that my name is Zane
# Pickle: Got it\! I've saved that preference.
```

Start a brand-new session:

```bash
uv run my-bot chat

# You: What's my name?
# Pickle: Based on your memory, your name is Zane\! Hi Zane\!
```

Inspect what was stored:

```bash
cat default_workspace/memories/topics/identity.md
```

---

## Alternative Approaches (Reference)

| Approach | Description |
|----------|-------------|
| **Specialized Agent** (this step) | Dedicated memory agent via `subagent_dispatch` |
| Direct Tools | Memory tools injected into every agent directly |
| Skill-Based | CLI tools (grep, cat) wrapped as skills |
| Vector Database | Semantic search over embeddings (pgvector, Chroma, etc.) |

---

## What's Next

You've completed all 17 steps of the BuckClaw tutorial\!

From here you can:
- **Deploy** -- wrap the server in a systemd service or Docker container
- **Extend** -- add a new channel (Discord, email), a new tool, a new agent
- **Customise** -- edit the SOUL.md, BOOTSTRAP.md, or AGENTS.md to reshape behaviour
- **Scale** -- swap LiteLLM for a direct provider, add a vector store, shard sessions
