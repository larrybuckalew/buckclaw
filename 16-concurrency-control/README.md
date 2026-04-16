# Step 16: Concurrency Control

> Too many Pickles are running at the same time?

Prevent resource exhaustion by limiting how many instances of an agent can
run simultaneously.  A semaphore per agent type blocks new requests when the
cap is reached, releasing them in FIFO order as slots free up -- no request
is ever silently dropped.

---

## Prerequisites

```bash
cp default_workspace/config.example.yaml default_workspace/config.user.yaml
# Edit config.user.yaml and add your API key
```

---

## What Changed

### `AgentDef.max_concurrency` (agent_loader.py)

A new optional field in every `AGENT.md` frontmatter:

```yaml
---
id: cookie
name: Cookie
max_concurrency: 1   # at most 1 concurrent execution
---
```

`0` (the default) means unlimited -- existing agents are unaffected.

### `AgentWorker` (server/agent_worker.py)

Three new methods manage a per-agent `asyncio.Semaphore` dictionary:

| Method | Purpose |
|--------|---------|
| `_get_or_create_semaphore(agent_id, max_concurrency)` | Lazy-init semaphore; returns `None` when limit is 0 |
| `_exec_session(session_id, content, agent_id, max_concurrency)` | Acquires semaphore before chat, releases after |
| `_maybe_cleanup_semaphore(agent_id)` | Removes semaphore when no waiters remain (keeps dict clean on hot-reload) |
| `_resolve_agent_concurrency(session_id)` | Looks up the `AgentDef` for a session and returns `(agent_id, max_concurrency)` |

Both `handle_inbound` and `handle_dispatch` now go through `_exec_session`,
so the limit applies equally to user messages and to cron / subagent dispatch.

When a request blocks, a `WARNING` is logged so you can observe back-pressure:

```
WARNING - Agent 'cookie' at concurrency limit (1).
          Session 'abc123' is waiting for a free slot.
```

---

## Try It Out

### 1. Start the server

```bash
cd 16-concurrency-control
uv run python -m mybot
```

### 2. Dispatch Cookie from two sources at once

Open two terminals (or two WebSocket clients) and fire a request to Cookie
simultaneously.  The second request will log the warning above and resume
once the first finishes.

Using the WebSocket API:

```bash
# Terminal 1
websocat ws://localhost:8765 <<< '{"session_id":"ws-1","agent_id":"cookie","content":"Summarise BOOTSTRAP.md please"}'

# Terminal 2 (at the same time)
websocat ws://localhost:8765 <<< '{"session_id":"ws-2","agent_id":"cookie","content":"Summarise AGENTS.md please"}'
```

Terminal 1 will answer immediately.  Terminal 2 will answer only after
Terminal 1 finishes -- you will see the back-pressure warning in the server
logs.

### 3. Verify Cookie is capped

```bash
grep "concurrency limit" <your-log-output>
```

---

## Concurrency Granularities (Reference)

| Granularity | Config location | Typical use case |
|-------------|-----------------|-----------------|
| **By agent** (this step) | `max_concurrency` in `AGENT.md` | Rate-limited or resource-heavy agents |
| **By source** | `max_concurrency` in channel config | Per-user fairness / abuse prevention |
| **By priority** | Custom semaphore pools | Reserved capacity for high-priority work |

---

## What's Next

**Step 17: Memory** -- Long-term knowledge system.
