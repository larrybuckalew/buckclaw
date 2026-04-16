<p align="center">
  <img src="assets/logo.png" alt="BuckClaw Logo" width="600"/>
</p>

# BuckClaw

<p align="center">
  <img src="assets/explainer.png" alt="Building an AI Agent from Scratch with Claude API" width="500"/>
</p>

A progressive 18-step tutorial for building a fully-featured AI agent from
scratch in Python using Anthropic's Claude API (or any provider via OpenRouter).

Each step builds on the previous, adding new capabilities -- from a bare
chat loop all the way to multi-agent dispatch with long-term memory.

## Steps

| # | Directory | What You Build |
|---|-----------|---------------|
| 00 | `00-chat-loop` | Basic REPL chat loop |
| 01 | `01-tools` | Tool calling (function use) |
| 02 | `02-skills` | Skill loading from markdown files |
| 03 | `03-persistence` | JSONL conversation history |
| 04 | `04-slash-commands` | CLI slash commands |
| 05 | `05-compaction` | Context window compaction |
| 06 | `06-web-tools` | Web search + web read tools |
| 07 | `07-event-driven` | Event-driven architecture (EventBus) |
| 08 | `08-config-hot-reload` | Pydantic config with hot reload |
| 09 | `09-channels` | Multi-channel support (CLI + Telegram) |
| 10 | `10-websocket` | WebSocket API server |
| 11 | `11-multi-agent-routing` | Routing table -- right job to right agent |
| 12 | `12-cron-heartbeat` | Cron jobs + heartbeat worker |
| 13 | `13-multi-layer-prompts` | Layered system prompt assembly |
| 14 | `14-post-message-back` | Agent-initiated outbound messages |
| 15 | `15-agent-dispatch` | Subagent dispatch (agent calls agent) |
| 16 | `16-concurrency-control` | Semaphore-based per-agent concurrency limits |
| 17 | `17-memory` | Long-term memory via specialized memory agent |

## Quick Start

```bash
cd 17-memory   # or any step
cp default_workspace/config.example.yaml default_workspace/config.user.yaml
# Add your Anthropic or OpenRouter API key to config.user.yaml
uv run my-bot chat
```

## API Key Options

**Anthropic direct:**
```yaml
llm:
  model: claude-3-5-haiku-20241022
  api_key: sk-ant-...
```

**OpenRouter (200+ models):**
```yaml
llm:
  model: openrouter/anthropic/claude-3-5-haiku
  api_key: sk-or-v1-...
  api_base: https://openrouter.ai/api/v1
```

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- An [Anthropic API key](https://console.anthropic.com) or [OpenRouter key](https://openrouter.ai)
