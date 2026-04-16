# Available Agents

| Agent ID   | Name       | Description                                    |
|------------|------------|------------------------------------------------|
| my-bot     | my-bot     | General-purpose helpful assistant (default)    |
| summarizer | Summarizer | Specialist for condensing documents and text   |

## Dispatch Patterns

- For summarization tasks: delegate to `summarizer` via `/route` command or routing config.
- For general tasks: `my-bot` handles everything by default.
