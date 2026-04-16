# Step 00 — Just a Chat Loop

> **BuckClaw Tutorial** · Phase 1: Capable Single Agent

All agents start with a simple chat loop.  
This step is the foundation that every future step will build upon.

---

## What We're Building

A minimal CLI agent that:
1. Reads a line of text from the user
2. Sends the full conversation history to an LLM
3. Prints the reply
4. Loops until the user types `quit`

That's it. No tools, no memory files, no web access — just the core conversation loop.

---

## Key Components

### `ChatLoop` — `src/mybot/cli/chat.py`

Handles all user-facing I/O.

| Responsibility | Detail |
|---|---|
| Banner | Renders a `rich` Panel on startup |
| Input | `asyncio.to_thread(input())` — non-blocking stdin read |
| Quit | Exits on `quit`, `exit`, `q`, Ctrl-C, or EOF |
| Display | Prints agent replies with colour-coded name prefix |

```
┌─ Chat ─────────────────────────────────────────────────┐
│  Welcome to my-bot!                                     │
└─────────────────────────────────────────────────────────┘
Type quit or exit to end the session.

You: Hello!
my-bot: Hi there! How can I help you today?
```

### `AgentSession` — `src/mybot/core/agent.py`

The stateful conversation engine.

```
chat(message)
  │
  ├─ append user message  →  ConversationState
  ├─ build_messages()     →  [system, ...history]
  ├─ LLMProvider.chat()   →  LLM API call
  └─ append assistant msg →  ConversationState
```

Every call sees the **full history**, so the LLM always has complete context.

### `ConversationState` — `src/mybot/core/state.py`

Stores messages as a plain list of `{"role": ..., "content": ...}` dicts.  
`build_messages()` prepends the system prompt each time, keeping the stored list clean.

> **Why plain dicts?**  
> In step 03 (Persistence) we'll serialise these to JSON.  Plain dicts make that trivial.

### `LLMProvider` — `src/mybot/provider/llm/base.py`

A thin async wrapper around [LiteLLM](https://github.com/BerriAI/litellm).

```python
response = await acompletion(model=..., messages=..., api_key=...)
```

LiteLLM normalises the API across providers, so switching from Claude to GPT-4o
(or a local Ollama model) only requires a config change — no code changes.

---

## Project Layout

```
00-chat-loop/
├── pyproject.toml              # Package config + dependencies
├── default_workspace/
│   └── config.example.yaml     # Copy → config.user.yaml and add your API key
└── src/
    └── mybot/
        ├── types.py            # Shared Message TypedDict
        ├── config.py           # YAML config loader
        ├── core/
        │   ├── state.py        # ConversationState
        │   └── agent.py        # Agent + AgentSession
        ├── provider/
        │   └── llm/
        │       └── base.py     # LLMProvider (LiteLLM wrapper)
        └── cli/
            ├── chat.py         # ChatLoop
            └── main.py         # `my-bot` Typer entry point
```

---

## Design Decisions

**Why `asyncio.to_thread` for `input()`?**  
`input()` is blocking — it freezes the entire event loop while waiting for the user.
Wrapping it in `asyncio.to_thread()` moves the blocking call to a thread pool, keeping
the event loop free.  This becomes important in step 07 (Event-Driven) when we run
background tasks alongside the chat loop.

**Why inject `Console` into `ChatLoop`?**  
Injecting the `Console` dependency makes the class testable — you can pass a
`Console(file=StringIO())` in tests to capture output without printing to the terminal.

**Why `Agent` (blueprint) + `AgentSession` (live conversation)?**  
`Agent` holds static config (LLM provider, name, system prompt) and is never mutated.  
`AgentSession` owns the mutable `ConversationState`.  This separation means one `Agent`
blueprint can spawn multiple independent sessions — important in step 11 (Multi-Agent Routing).

---

## Prerequisites

Install [uv](https://docs.astral.sh/uv/) if you haven't already:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Try It Out

**1. Configure your API key**

```bash
cp default_workspace/config.example.yaml default_workspace/config.user.yaml
# Edit config.user.yaml — set llm.api_key to your Anthropic key
```

**2. Run**

```bash
cd 00-chat-loop
uv run my-bot chat
```

**3. Chat!**

```
┌─ Chat ─────────────────────────────────────────────────┐
│  Welcome to my-bot!                                     │
└─────────────────────────────────────────────────────────┘
Type quit or exit to end the session.

You: Hello, who are you?
my-bot: Hi! I'm my-bot, a helpful AI assistant. How can I help you today?

You: What is 2 + 2?
my-bot: 2 + 2 = 4.

You: quit
Goodbye!
```

**Optional:** Pass a custom config file:

```bash
uv run my-bot chat --config path/to/my-config.yaml
```

---

## What's Next

**[Step 01: Tools →](../01-tools/README.md)**  
Give your agent the ability to *take actions* — search the web, run code,
read files — by adding a tool-calling layer on top of this chat loop.
