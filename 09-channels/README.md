# Step 09: Channels

Step 09 introduces **multi-platform message routing**. The agent can now receive messages from Telegram, CLI, or any other platform and deliver responses back to the originating source.

## Architecture

The full message flow is:

```
User (Telegram/CLI/...)
  |
  v
Channel.run() -- receives platform message, calls on_message callback
  |
  v  
ChannelWorker -- wraps each channel, publishes InboundEvent (with source)
  |
  v
EventBus (queue + disk persistence)
  |
  v
AgentWorker -- processes InboundEvent, publishes OutboundEvent
  |
  v
EventBus (dispatches OutboundEvent, persists to disk)
  |
  v
DeliveryWorker -- looks up source for session, calls channel.reply()
  |
  v
User gets response on their platform
```

## Key Concepts

### EventSource

An `EventSource` uniquely identifies the origin of a message:

- **platform** (string): `"telegram"`, `"cli"`, etc.
- **user_id** (string): platform-specific user identifier
- **chat_id** (string): platform-specific chat/channel identifier
- **source_id** (computed): combined as `"{platform}:{user_id}:{chat_id}"`

Two messages from the same source_id are routed to the same session.

### Channel (ABC)

Abstract base class for messaging platforms. Must implement:

```python
async def run(self, on_message: Callable[[str, EventSource], Awaitable[None]]) -> None:
    """Start receiving messages. Calls on_message for each one. Blocks until stop()."""

async def reply(self, content: str, source: EventSource) -> None:
    """Send a reply back to the originating source."""

async def stop(self) -> None:
    """Stop the channel and clean up resources."""

@property
def platform_name(self) -> str:
    """Unique platform identifier (e.g. 'telegram', 'cli')."""
```

### CLIChannel

Wraps stdin/stdout as a Channel. Reads user input with `input()`, prints responses with rich formatting. Supports exit commands (`quit`, `exit`, `q`).

### TelegramChannel

Uses `python-telegram-bot` to connect to Telegram's Bot API. Handles `/start` command, routes text messages to the agent, and splits long responses (Telegram limit: 4096 chars).

### ChannelWorker

Manages N channels concurrently:

1. Starts all channels in separate asyncio tasks
2. Routes inbound messages to a callback
3. **Maps each EventSource to a session_id** (created on first message, cached in-memory)
4. Publishes an `InboundEvent` with source + session_id to the EventBus
5. Persists the source->session mapping to `config.runtime.yaml` for recovery

### DeliveryWorker

Subscribes to `OutboundEvent`:

1. Looks up the source for the session_id (from `context.session_source_map`)
2. Finds the channel for that platform
3. Calls `channel.reply(content, source)`
4. Calls `eventbus.ack(event)` on success

### EventBus Persistence

The EventBus now supports optional disk persistence for `OutboundEvent`:

- **Atomic writes**: writes to `.tmp` file, fsync, then rename (prevents corruption)
- **Ack flow**: `ack(event)` deletes the persisted JSON file
- **Recovery**: `_recover()` runs at startup, re-dispatches any unacked events (ensures delivery even if the process crashes)

### session_source_map

A shared dictionary in `AppContext` that maps:

```
session_id -> EventSource
```

- **Populated by**: `AgentWorker.handle_inbound()` (when source is present in InboundEvent)
- **Read by**: `DeliveryWorker.handle_outbound()` (to route responses)

In-memory for speed, backed up to `config.runtime.yaml` by `ChannelWorker` for recovery.

## Changes from Step 08

1. **New module**: `src/mybot/channel/` with `base.py`, `cli_channel.py`, `telegram.py`
2. **New workers**: `channel_worker.py` (manages channels), `delivery_worker.py` (delivers responses)
3. **Updated EventBus**: now supports optional `pending_dir` and `ack()` for persistence
4. **Updated events.py**: `InboundEvent` now has optional `source: EventSource | None` field
5. **Updated context.py**: added `session_source_map: dict` field
6. **Updated config.py**: added `ChannelsConfig` with `TelegramConfig`, plus `set_runtime()` method
7. **New main.py commands**: `server` (all channels) and `chat` (CLI-only)

## Setup

### Prerequisites

```bash
pip install python-telegram-bot>=21.0
```

Or via uv:

```bash
uv pip install python-telegram-bot>=21.0
```

### Telegram Bot Setup

1. **Open Telegram** and search for `@BotFather`
2. **Send** `/newbot` and follow the prompts
   - Choose a name and username
   - Copy the token (looks like: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)
3. **Copy `config.example.yaml` to `config.user.yaml`** and add your token:

```yaml
channels:
  telegram:
    token: "YOUR_TOKEN_HERE"
    allowed_user_ids: []  # empty = allow all users
```

4. **Start the server**:

```bash
uv run my-bot server
```

5. **In Telegram**: search for your bot username and click `/start`
6. **Send messages** and receive responses

### CLI Mode

To test without Telegram:

```bash
uv run my-bot chat
```

This starts CLI-only (ignores `channels.telegram.token` in config).

## Try It Out

### Start the Server

```bash
uv run my-bot server
```

You'll see:

```
Config hot-reload: enabled
Telegram channel: enabled
Channels: ['cli', 'telegram']

Welcome to my-bot\!
Chat
Type quit or exit to end the session.

You:
```

### Send a Message from CLI

```
You: Hello\!

my-bot: Hello\! I'm happy to help. What can I do for you?

You: What's 2+2?

my-bot: 2 + 2 = 4
```

### Send a Message from Telegram

In your Telegram chat with the bot:

```
You: Hey there
Bot: Hi\! How can I assist you?

You: Do you know Python?
Bot: Yes, I'm familiar with Python...
```

### Multiple Simultaneous Channels

You can chat from **both CLI and Telegram at the same time**. Each creates a separate session. Messages from the same source (same user + chat) go to the same session.

## Design Decisions

### One Session per EventSource (Not Per User)

Each unique `(platform, user_id, chat_id)` gets its own session. This allows:

- A Telegram user to have separate conversations in different groups
- The same CLI user (always "local:local") to have one session per run
- Proper isolation and history management

### In-Memory session_source_map + Runtime Config Backup

**Why in-memory?**
- Fast O(1) lookup during delivery
- Simple, no database needed

**Why backup to config.runtime.yaml?**
- If the process crashes, we can recover the mapping on restart
- ChannelWorker persists the mapping whenever a new source appears
- `_recover()` in EventBus handles undelivered OutboundEvents

### Atomic EventBus Persistence

Each OutboundEvent is written atomically:

1. Write to `.json.tmp`
2. Call `fsync()` to ensure it's on disk
3. Rename to `.json` (atomic on most filesystems)

This prevents corruption if the process crashes mid-write.

## Files

- `src/mybot/channel/base.py` - Abstract Channel and EventSource
- `src/mybot/channel/cli_channel.py` - CLI channel implementation
- `src/mybot/channel/telegram.py` - Telegram channel implementation
- `src/mybot/server/channel_worker.py` - Manages all channels
- `src/mybot/server/delivery_worker.py` - Delivers responses
- `src/mybot/core/events.py` - Updated with source field
- `src/mybot/core/eventbus.py` - Updated with persistence
- `src/mybot/core/context.py` - Updated with session_source_map
- `src/mybot/utils/config.py` - Updated with TelegramConfig
- `src/mybot/server/agent_worker.py` - Updated to populate session_source_map
- `src/mybot/cli/main.py` - New server and chat commands
- `default_workspace/config.example.yaml` - Updated with channels section
- `pyproject.toml` - Updated to v0.10.0, added python-telegram-bot dependency

## What's Next

Step 10 will introduce **WebSocket** for real-time browser-based chat without polling.
