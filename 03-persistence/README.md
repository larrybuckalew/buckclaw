# Step 03: Persistence

This step adds conversation persistence using JSONL files. Every message is now saved to disk, allowing you to replay conversations, build analytics, and audit agent behavior.

## What We're Building

A file-based history system that stores each agent session and its messages in JSONL format (one JSON object per line). This provides:

- **Session tracking**: Each conversation gets a unique UUID
- **Message persistence**: Every user, assistant, and tool message is logged
- **Replay capability**: Reconstruct full conversations from files
- **Scalability**: Append-only writes are fast and work in concurrent scenarios

## File Structure

```
.history/
├── index.jsonl              # Session metadata (one line per session)
└── sessions/
    ├── {uuid1}.jsonl        # Messages for session 1
    ├── {uuid2}.jsonl        # Messages for session 2
    └── ...
```

### index.jsonl format
```json
{"session_id": "uuid", "agent_id": "my-bot", "agent_name": "MyBot", "created_at": "2025-04-16T10:30:00Z", "message_count": 12}
```

### sessions/{session_id}.jsonl format
```json
{"role": "user", "content": "Hello", "timestamp": "2025-04-16T10:30:01Z"}
{"role": "assistant", "content": "Hi there\!", "timestamp": "2025-04-16T10:30:02Z"}
{"role": "assistant", "tool_calls": [...], "timestamp": "2025-04-16T10:30:03Z"}
{"role": "tool", "tool_call_id": "call_123", "name": "read_file", "content": "file contents", "timestamp": "2025-04-16T10:30:04Z"}
```

## Key Components

### HistoryMessage
A dataclass representing a single message with:
- `session_id`: UUID of the conversation
- `role`: "user", "assistant", "system", or "tool"
- `content`: The message text
- `timestamp`: ISO 8601 creation time
- Optional: `tool_calls`, `tool_call_id`, `name` for tool results

### SessionMeta
A dataclass with session metadata:
- `session_id`: UUID
- `agent_id`: Identifier for the agent
- `agent_name`: Display name
- `created_at`: ISO 8601 creation time
- `message_count`: Auto-incremented with each message

### HistoryStore
The main class for persistence with methods:
- `create_session(agent_id, agent_name)` -- Returns a new SessionMeta
- `save_message(session_id, message)` -- Appends message to session file
- `get_messages(session_id)` -- Reads all messages from a session
- `list_sessions()` -- Lists all sessions
- `get_session(session_id)` -- Fetches a specific session

## What Changed from Step 02

### src/mybot/core/agent.py
- `AgentSession.__init__` now accepts optional `history_store` and `session_meta` parameters
- New `_save_to_history()` method persists messages if history_store is set
- `chat()` now calls `_save_to_history()` after user and assistant messages

### src/mybot/cli/main.py
- Imports HistoryStore and creates it before starting chat
- Creates a new session and prints the session ID in dim style
- Passes `history_store` and `session_meta` to AgentSession

### src/mybot/core/history.py (NEW)
- Complete JSONL persistence layer with HistoryMessage, SessionMeta, and HistoryStore

## Try It Out

Run the chat and note the session ID printed at startup:

```bash
my-bot chat --config config.user.yaml
```

Output:
```
Session ID: f47ac10b-58cc-4372-a567-0e02b2c3d479
Skills loaded: code-reviewer, skill-creator

> hello
```

Then inspect the `.history/` directory:

```bash
ls -la .history/
cat .history/index.jsonl
cat .history/sessions/f47ac10b-58cc-4372-a567-0e02b2c3d479.jsonl
```

The session file contains a complete transcript of your conversation, including all tool calls and results.

## What's Next

Step 04: Slash Commands will add a `/history` command to list and replay past sessions, and a `/replay {session_id}` command to continue a conversation from any point in its history.
