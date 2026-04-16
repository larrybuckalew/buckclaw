# Available Agents

| Agent ID | Name      | Description                                                              |
|----------|-----------|--------------------------------------------------------------------------|
| my-bot   | BuckClaw  | General-purpose assistant with long-term memory (default)                |
| memory   | Memory    | Long-term memory manager -- stores and retrieves user facts              |
| summarizer | Summarizer | Specialist for condensing documents and text                          |
| cookie   | Cookie    | Cheerful assistant for file reading and summaries (max_concurrency: 1)   |

## Dispatch Patterns

- **Store/recall user facts**: delegate to `memory` via `subagent_dispatch`.
- **Summarisation tasks**: delegate to `summarizer`.
- **File reading with cheerful summaries**: delegate to `cookie`.
- **General tasks**: `my-bot` (BuckClaw) handles everything by default.

## Memory Agent Protocol

When BuckClaw (my-bot) needs to remember or recall something, it dispatches
to `memory` with a plain-English instruction:

```
# Save
subagent_dispatch(agent_id="memory", task="Save the following fact about the user: their name is Zane")

# Recall
subagent_dispatch(agent_id="memory", task="Recall all memories about the user")
```

The memory agent reads/writes markdown files under `default_workspace/memories/`.
