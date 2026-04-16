# Available Agents

| Agent ID   | Name       | Description                                    |
|------------|------------|------------------------------------------------|
| my-bot     | my-bot     | General-purpose helpful assistant (default)    |
| summarizer | Summarizer | Specialist for condensing documents and text   |
| cookie     | Cookie     | Cheerful assistant for file reading and summaries |

## Dispatch Patterns

- For summarization tasks: delegate to `summarizer` via `/route` command or routing config.
- For file reading and cheerful summaries: delegate to `cookie`.
- For general tasks: `my-bot` handles everything by default.
