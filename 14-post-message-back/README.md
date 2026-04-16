# Step 14: Post Message Back

## Overview

Step 14 adds the `post_message` tool, which lets the agent (specifically a cron job session) proactively send a message to a user's channel without waiting for user input. This is how cron jobs deliver their output back to the user.

## The Problem

When a cron job runs on a schedule, it fires in its own isolated session. There's no user at a terminal waiting for a response. Without a mechanism to send messages back, the cron agent's response has nowhere to go -- it just disappears.

## The Solution

`post_message` is a tool that publishes an `OutboundEvent` targeted at a specific user session, allowing the cron agent to reach out proactively:

1. The user asks: "Message me in 5 minutes" (via Telegram/CLI).
2. The agent writes a one-off CRON.md job that includes the user's `session_id` as `target_session_id`.
3. When the cron fires 5 minutes later, `CronWorker` creates a `DispatchEvent` and calls `_ensure_cron_tools()` to register the delivery target.
4. `AgentWorker` reads `cron_delivery_map[session_id]` and injects a `PostMessageTool` pre-configured with the user's session_id.
5. The cron agent calls `post_message("Hi there\!")`.
6. `PostMessageTool.execute()` publishes `OutboundEvent(session_id=user_session, content="Hi there\!")`.
7. `DeliveryWorker` finds the user's channel source from `session_source_map[user_session]` and delivers the message.
8. User receives the message on their platform (Telegram, CLI, etc.).

## End-to-End Flow

```
User: "Message me in 5 minutes"
  |
  v
Agent reads session_id from runtime context layer (Layer 4)
  |
  v
Agent writes CRON.md with target_session_id=<user_session> + one_off=true
  |
  v
CronWorker (5 mins later) -> DispatchEvent -> AgentWorker
  |
  v
AgentWorker injects PostMessageTool (because target_session_id is set)
  |
  v
Cron agent calls post_message("Hi there\!")
  |
  v
OutboundEvent(session_id=user_session) -> DeliveryWorker -> User's channel
```

## Key Changes from Step 13

### 1. CronDef (cron_loader.py)

Added `target_session_id` field to `CronDef`:

```python
class CronDef(BaseModel):
    ...
    target_session_id: str = ""   # where to deliver post_message results
```

### 2. PostMessageTool (tools/post_message_tool.py)

New tool factory and class:

- `create_post_message_tool(context, delivery_session_id)` -- factory that builds a pre-configured tool
- `PostMessageTool.execute(session, content)` -- publishes an `OutboundEvent` to the delivery session
- Only available in cron sessions (not user-facing sessions)

The tool accepts:
- `content` (str): the message to send

### 3. CronWorker (server/cron_worker.py)

Added `_ensure_cron_tools()` method:

- Called from `_dispatch_job()` after creating the session
- If `job.target_session_id` is set, stores it in `context.cron_delivery_map[session_id]`
- This allows AgentWorker to look up and inject the delivery target

### 4. AppContext (core/context.py)

Added `cron_delivery_map` field:

```python
@dataclass
class AppContext:
    ...
    cron_delivery_map: dict = field(default_factory=dict)
```

Maps cron `session_id` -> user `delivery_session_id`. Populated by `CronWorker._ensure_cron_tools()`, read by `AgentWorker._get_or_create_session()`.

### 5. AgentWorker (server/agent_worker.py)

Updated `_get_or_create_session()` to check `context.cron_delivery_map`:

- If the session_id is in `cron_delivery_map`, get the delivery target
- Create a `PostMessageTool` via `create_post_message_tool()`
- Add it to the session's tool registry
- Log when injection happens

### 6. Cron-Ops Skill (default_workspace/skills/cron-ops.md)

Added documentation:

- New `target_session_id` field in CRON.md format section
- New "Delivering Messages Back to Users" section explaining how to use it
- Emphasis that `post_message` is only available when `target_session_id` is set

## How the Agent Knows the User's Session ID

The user's `session_id` is injected into cron job prompts via the **runtime context layer** (Layer 4 from Step 13). The `PromptBuilder` embeds it in the system prompt, e.g.:

```
Session ID: 550e8400-e29b-41d4-a716-446655440000
Timestamp: 2025-04-16 14:30:00 UTC
...
```

When the agent reads this context, it extracts the session_id and includes it in the CRON.md file's `target_session_id` field.

## Design Notes

### Why `post_message` is Only in Cron Sessions

- User-facing sessions have the user waiting at a terminal/channel; they don't need to post messages back.
- Cron sessions are headless; without `post_message`, they have no way to communicate.
- This keeps the tool surface clean and intention-clear: only cron agents get this capability.

### Why One-Off Crons Are the Right Primitive

Instead of a timer/sleep mechanism, BuckClaw uses one-off cron jobs because:

- **Persistence**: The job survives application restarts.
- **Scalability**: Thousands of scheduled jobs can be managed via a single CronWorker tick loop.
- **Flexibility**: The same cron system handles both recurring and one-time tasks.
- **Discoverability**: All scheduled work is visible via `CRON.md` files on disk.

### Why Deliver via OutboundEvent/DeliveryWorker

- **Consistent pipeline**: Uses the same delivery mechanism as user-facing agent responses.
- **Platform agnostic**: DeliveryWorker handles Telegram, CLI, WebSocket, etc. all the same way.
- **Testability**: Easy to mock or intercept OutboundEvent for testing.

## Try It Out

1. Start the app in normal mode (CLI session).
2. Ask the agent: "Message me in 1 minute saying 'Hello from the future\!'"
3. The agent should:
   - Read your session_id from the runtime context
   - Write a one-off CRON.md job with `target_session_id=<your_session_id>`
   - Return a confirmation message
4. Wait 60+ seconds.
5. You should receive the message "Hello from the future\!" in your original session.

Behind the scenes:
- CronWorker detects the job is due
- Creates a DispatchEvent, calls _ensure_cron_tools()
- AgentWorker injects PostMessageTool
- Cron agent calls post_message()
- DeliveryWorker delivers to your session

## What's Next

**Step 15: Agent Dispatch** will add the ability for one agent to delegate work to another agent, creating a multi-agent orchestration layer on top of the cron and tool infrastructure.

---

### Files Modified

- `pyproject.toml` -- version 0.15.0, description updated
- `src/mybot/core/cron_loader.py` -- added `target_session_id` field to `CronDef`
- `src/mybot/tools/post_message_tool.py` -- **NEW** PostMessageTool implementation
- `src/mybot/core/context.py` -- added `cron_delivery_map` field
- `src/mybot/server/cron_worker.py` -- added `_ensure_cron_tools()` method
- `src/mybot/server/agent_worker.py` -- updated `_get_or_create_session()` to inject post_message
- `default_workspace/skills/cron-ops.md` -- documented `target_session_id` and post_message usage

### Architecture Summary

```
┌─────────────────────────────────────────────────────────┐
│                    AppContext                            │
├─────────────────────────────────────────────────────────┤
│ cron_delivery_map: {                                     │
│   "<cron_session_id>": "<user_session_id>",             │
│   ...                                                    │
│ }                                                        │
└─────────────────────────────────────────────────────────┘
         ^                          ^
         |                          |
         |                          |
    CronWorker              AgentWorker
   _ensure_cron_tools()    _get_or_create_session()
    (populates map)         (reads map, injects tool)
         |
         v
    [cron_delivery_map lookup]
         |
         v
    PostMessageTool
   (uses delivery_session_id)
         |
         v
    OutboundEvent
   (routed to user's channel)
```
