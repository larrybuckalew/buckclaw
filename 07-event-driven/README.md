# Step 07: Event-Driven Architecture

## Overview

This step introduces a major architectural refactor: **decoupling the agent from the CLI via a pub/sub event bus**. Instead of the CLI directly calling the agent, user input becomes an `InboundEvent`, and agent responses become `OutboundEvents`. The CLI is now just one possible adapter -- the infrastructure is ready for future channels like Telegram or WebSocket.

**User-facing behavior is identical to Step 06.** This is pure infrastructure improvement.

## Architecture: The Data Flow

```
stdin -> CLIAdapter -> InboundEvent -> EventBus -> AgentWorker -> AgentSession -> OutboundEvent -> EventBus -> CLIAdapter -> stdout
```

1. **User types message** in stdin
2. **CLIAdapter** reads the input and publishes an `InboundEvent`
3. **EventBus** (central pub/sub worker) receives the event and dispatches it
4. **AgentWorker** (server-side worker) is subscribed to `InboundEvent`
5. AgentWorker creates/retrieves an `AgentSession`, runs `session.chat()`
6. AgentWorker publishes an `OutboundEvent` with the response
7. **EventBus** dispatches the `OutboundEvent`
8. **CLIAdapter** is subscribed to `OutboundEvent` and displays the result

This event-driven design makes it trivial to add new channels later -- Telegram or WebSocket adapters can publish `InboundEvent` and subscribe to `OutboundEvent` independently.

## New Components

### Core Module: `src/mybot/core/`

- **`events.py`**: Event type hierarchy
  - `Event` -- base class with `event_id`, `timestamp`
  - `InboundEvent` -- user message (with `session_id`, `content`, `retry_count`)
  - `OutboundEvent` -- agent response (with `session_id`, `content`, optional `error`)

- **`worker.py`**: Worker ABC (abstract base class)
  - `Worker` -- lifecycle contract for background async tasks
  - `start()` creates and schedules `self.run()` as an `asyncio.Task`
  - `stop()` cancels and awaits the task cleanly
  - Subclasses override `run()` for their main loop

- **`eventbus.py`**: Central pub/sub queue
  - `EventBus(Worker)` -- async queue-based event dispatcher
  - `subscribe(event_class, handler)` -- register handler for event type
  - `publish(event)` -- enqueue an event (non-blocking)
  - `run()` -- drain the queue and dispatch events sequentially
  - **Sequential dispatch prevents concurrency bugs**: only one handler runs at a time

- **`context.py`**: Shared application context
  - `AppContext` -- single object holding `config`, `eventbus`, `llm`, `history_store`, `tool_registry`, `skill_loader`
  - Passed to every Worker and Adapter, eliminating global state

### Server Module: `src/mybot/server/`

- **`__init__.py`**: Package marker

- **`agent_worker.py`**: Server-side event handler
  - `AgentWorker(Worker)` -- listens for `InboundEvent`, publishes `OutboundEvent`
  - Maintains session cache (`_sessions: dict[str, AgentSession]`)
  - `handle_inbound()` -- retrieves or creates session, runs `session.chat()`, publishes response
  - Sessions survive restarts thanks to Step 03 persistence (history is loaded from store)

### CLI Module Update: `src/mybot/cli/`

- **`adapter.py`**: NEW -- CLI driver for event-driven architecture
  - `CLIAdapter(Worker)` -- replaces the old `ChatLoop`
  - Input side: reads stdin, publishes `InboundEvent`
  - Output side: subscribed to `OutboundEvent`, displays replies
  - Uses `asyncio.Future` per session to correlate requests with responses
  - Identical UX to Step 06

- **`main.py`**: REWRITTEN -- event-driven entry point
  - Builds `AppContext` with config, eventbus, llm, history_store, tool_registry, skill_loader
  - Starts `EventBus`, `AgentWorker`, and `CLIAdapter` concurrently
  - Runs `cli_adapter.run()` in foreground (exits on user "quit")
  - Cleanly stops all workers in a finally block

## What Changed from Step 06

| Component | Step 06 | Step 07 |
|-----------|---------|---------|
| **core/** | No eventbus or worker | NEW: `events.py`, `worker.py`, `eventbus.py`, `context.py` |
| **server/** | Doesn't exist | NEW: `agent_worker.py` (server-side event handler) |
| **cli/chat.py** | `ChatLoop` class | Removed (functionality moved to `adapter.py`) |
| **cli/adapter.py** | Doesn't exist | NEW: `CLIAdapter` (event-driven CLI) |
| **cli/main.py** | Direct `ChatLoop` instantiation | Rewritten to build `AppContext` and orchestrate workers |
| **Architecture** | Monolithic (CLI calls agent directly) | Decoupled via pub/sub (CLI and agent communicate via `EventBus`) |

## Design Notes

### Sequential Event Dispatch

The `EventBus.run()` method processes events one at a time from the queue:

```python
while True:
    event = await self._queue.get()
    await self._dispatch(event)
    self._queue.task_done()
```

This **sequential design avoids concurrency bugs**: you never have two handlers for the same event running simultaneously. If you need parallelism in the future, you can refactor to `asyncio.gather()` the handlers, but for now, simplicity wins.

### Session Cache in AgentWorker

The `AgentWorker._sessions` dict caches `AgentSession` objects by `session_id`:

```python
def _get_or_create_session(self, session_id: str) -> AgentSession:
    if session_id not in self._sessions:
        # ... create and restore from history ...
    return self._sessions[session_id]
```

This means:
- Multiple `InboundEvent`s for the same `session_id` reuse the same session
- Conversation history is preserved in memory
- On process restart, history is reloaded from the `HistoryStore` (Step 03 persistence)

### Why AppContext?

Passing a single `AppContext` object to all workers:
- Eliminates global state and dependency injection boilerplate
- Makes testing easier (mock the context)
- Scales well as you add more workers (Telegram adapter, WebSocket adapter, etc.)

## User-Facing Behavior

**Identical to Step 06.** You run:

```bash
my-bot chat
```

You get an interactive terminal. You type messages, the agent responds. You type "quit" to exit. No visible changes -- this is pure infrastructure.

## What's Next: Step 08

**Config Hot Reload**: The `EventBus` can publish `ConfigUpdated` events, and workers can subscribe to them to reload settings without restarting the entire application. This opens the door to graceful updates in production.

---

## Files Structure

```
src/mybot/
├── core/
│   ├── __init__.py
│   ├── events.py         # NEW
│   ├── worker.py         # NEW
│   ├── eventbus.py       # NEW
│   ├── context.py        # NEW
│   ├── agent.py
│   ├── context_guard.py
│   ├── history.py
│   └── ...
├── server/
│   ├── __init__.py       # NEW
│   └── agent_worker.py   # NEW
├── cli/
│   ├── __init__.py
│   ├── adapter.py        # NEW (replaces chat.py as driver)
│   ├── main.py           # REWRITTEN
│   └── (chat.py removed)
├── tools/
│   ├── ...
├── provider/
│   ├── ...
└── ...
```

---

## Testing the Refactor

The bot works exactly as before:

```bash
# Start the bot
python -m mybot.cli.main chat

# Type a message
You: Hello

# Agent responds via the event bus
my-bot: ...response...

# Exit
You: quit
Goodbye\!
```

Behind the scenes:
1. Your message becomes an `InboundEvent`
2. The `EventBus` dispatches it to `AgentWorker.handle_inbound()`
3. The agent processes it in a session
4. The response becomes an `OutboundEvent`
5. The `EventBus` dispatches it to `CLIAdapter._handle_outbound()`
6. The CLI prints the response

All without the CLI and agent directly knowing about each other.
