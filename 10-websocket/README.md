# Step 10: WebSocket

Programmatic access to your BuckClaw agent via WebSocket. The server runs uvicorn (FastAPI) and broadcasts all events to connected clients.

## Why WebSocket?

- **Programmatic Access**: Control your agent from custom applications, bots, or CLIs
- **Real-Time Feedback**: Receive every InboundEvent and OutboundEvent as it happens
- **UI Integration**: Build web dashboards, monitoring tools, or custom frontends
- **Testing**: Automated testing frameworks can send messages and verify responses
- **Multi-Client**: Multiple clients can connect simultaneously and see the same event stream

## Architecture

The WebSocket system has two roles:

1. **Inbound Role**: Client sends JSON → WebSocketWorker creates InboundEvent → Published to eventbus
2. **Outbound Role**: WebSocketWorker listens to all events (InboundEvent + OutboundEvent) → Broadcasts to all connected clients

This means clients see a complete picture of what the agent is doing, not just replies.

## Message Protocol

### Client → Server (Inbound)

Send a JSON message with a source name and content:

```json
{
  "source": "my-app",
  "content": "Hello, agent\!"
}
```

The server creates an InboundEvent with:
- `session_id`: Unique session for this source (created on first message)
- `source`: EventSource with platform="ws", user_id and chat_id set from the message
- `content`: The message text
- `timestamp`: Server timestamp
- `retry_count`: Always 0 for new messages

### Server → Client (Broadcast)

Every event published to the eventbus is broadcast as JSON to all connected clients:

```json
{
  "type": "InboundEvent",
  "session_id": "sess-123",
  "source": {"platform": "ws", "user_id": "my-app", "chat_id": "my-app"},
  "content": "Hello, agent\!",
  "timestamp": "2024-04-16T10:30:00.000Z",
  "retry_count": 0
}
```

```json
{
  "type": "OutboundEvent",
  "session_id": "sess-123",
  "content": "Hi there\! How can I help?",
  "timestamp": "2024-04-16T10:30:01.000Z",
  "error": null
}
```

## session_source_map

When a WebSocket client connects and sends a message, WebSocketWorker:
1. Creates an InboundEvent with a new or existing session_id
2. Maps that session_id to an EventSource in `context.session_source_map`
3. DeliveryWorker reads this map to route OutboundEvent replies back to the correct WebSocket client

This bridges WebSocket clients into the same session/delivery system as CLI and Telegram channels.

## FastAPI Endpoints

### GET /health

Health check endpoint. Returns:

```json
{
  "status": "ok",
  "agent": "my-bot",
  "ws_clients": 2
}
```

Useful for monitoring and readiness checks.

### WebSocket /ws

The main WebSocket endpoint. Clients connect here.

```bash
wscat -c ws://localhost:8000/ws
> {"source": "test", "content": "Hello\!"}
< {"type":"InboundEvent","session_id":"...","source":"...","content":"Hello\!","timestamp":"...","retry_count":0}
< {"type":"OutboundEvent","session_id":"...","content":"Hi there\!","timestamp":"...","error":null}
```

## Running the Server

### Full Server (with WebSocket API)

```bash
uv run my-bot server
```

Output:
```
[dim]WebSocket: ws://127.0.0.1:8000/ws[/dim]
[dim]Telegram: enabled[/dim]
[dim]Config hot-reload: enabled[/dim]

```

The uvicorn server starts automatically alongside all workers. Open another terminal and test:

```bash
wscat -c ws://localhost:8000/ws
```

### CLI-Only Mode (no WebSocket)

```bash
uv run my-bot chat
```

Starts only the CLIChannel (useful for development without the API server).

## Configuration

Edit `default_workspace/config.user.yaml`:

```yaml
api:
  host: "127.0.0.1"
  port: 8000
  enabled: true
```

- `host`: Bind address (127.0.0.1 = localhost only, 0.0.0.0 = all interfaces)
- `port`: Listen port
- `enabled`: Toggle the API server on/off without restarting

## What Changed from Step 09

**New Files:**
- `src/mybot/server/websocket_worker.py`: Manages WebSocket connections and event broadcasting
- `src/mybot/server/app.py`: FastAPI application factory

**Modified Files:**
- `src/mybot/utils/config.py`: Added ApiConfig dataclass
- `src/mybot/core/context.py`: Added optional websocket_worker field
- `src/mybot/cli/main.py`: Wired up WebSocketWorker, FastAPI, and uvicorn
- `pyproject.toml`: Added fastapi>=0.110.0 and uvicorn[standard]>=0.29.0
- `default_workspace/config.example.yaml`: Added api section

## Design Notes

### Why Broadcast ALL Events?

WebSocketWorker broadcasts both InboundEvent and OutboundEvent to all clients. This might seem wasteful, but it's intentional:

1. **Transparency**: Clients see exactly what the agent sees
2. **Debugging**: Monitor agent reasoning, tool calls, and delays
3. **Sync**: Multiple clients stay in sync without polling
4. **Testing**: Automated tests can verify intermediate events, not just final replies

A client can filter for `type: "OutboundEvent"` if it only cares about agent replies.

### Session Management

Each unique EventSource (keyed by `platform:user_id:chat_id`) gets one session_id. Reconnecting with the same source reuses the existing session and conversation history.

### Error Handling

- If a client disconnects, it's automatically removed from the broadcast list
- If broadcast fails for one client, others are unaffected
- WebSocket errors are logged but don't crash the server

## Next Steps

Step 11 will add **Multi-Agent Routing**: multiple agents, dynamic dispatch, and agent-to-agent communication.

---

**Version**: 0.11.0  
**Platform**: FastAPI + uvicorn  
**Protocol**: WebSocket JSON
