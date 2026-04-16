# Step 15: Agent Dispatch

**Version:** 0.16.0

This step implements **agent delegation** via the EventBus, allowing one agent to dispatch tasks to specialized subagents and receive their results asynchronously.

---

## Overview

Agent dispatch enables a multi-agent system where:
- A main agent can request help from specialized subagents
- The main agent awaits the subagent's response
- Control flow is decoupled via the EventBus (no direct function calls)
- Multiple agents can coexist and serve different purposes

### Available Agents

- **my-bot**: General-purpose assistant (default)
- **summarizer**: Specializes in condensing documents
- **cookie**: Cheerful assistant for file reading and summaries

---

## How the Dispatch Mechanism Works

The dispatch flow follows these steps:

```
1. Main agent calls subagent_dispatch(agent_id="cookie", task="Read README.md...")
   |
   v
2. Tool creates a new session for the subagent via history_store
   |
   v
3. Tool subscribes a temporary handler to DispatchResultEvent
   (filtered by the new session_id)
   |
   v
4. Tool publishes DispatchEvent(session_id=new_session, parent_session_id=caller)
   |
   v
5. AgentWorker.handle_dispatch() picks up the DispatchEvent
   - Loads the target agent (cookie)
   - Creates/resumes the cookie session
   - Runs session.chat(task)
   |
   v
6. Cookie responds and publishes DispatchResultEvent(session_id=new_session, content=response)
   |
   v
7. Temporary handler resolves the future with the response
   |
   v
8. Tool unsubscribes the handler
   |
   v
9. Tool returns JSON: {"result": "...", "session_id": "..."}
   |
   v
10. Main agent sees the result and responds to user
```

**Key insight:** The EventBus ensures agents remain decoupled. The calling agent does not directly invoke the subagent; it publishes a request and waits for a result event.

---

## Core Components

### 1. `DispatchEvent` (Updated)

**File:** `src/mybot/core/events.py`

```python
@dataclass
class DispatchEvent(Event):
    """Internal event: trigger agent with a prompt (cron/heartbeat/agent-dispatch)."""
    session_id: str = ""
    content: str = ""
    source: "EventSource | None" = None
    parent_session_id: str = ""    # NEW: tracing hint
```

The `parent_session_id` field allows tracing the lineage of agent calls (for debugging and monitoring).

---

### 2. `SubagentDispatchTool` Factory

**File:** `src/mybot/tools/subagent_tool.py`

#### `create_subagent_dispatch_tool()`

```python
def create_subagent_dispatch_tool(
    current_agent_id: str,
    context: AppContext,
) -> "SubagentDispatchTool | None":
```

**Purpose:** Factory function that creates a dispatch tool for an agent.

**Behavior:**
1. Returns `None` if the agent has no peers (only agent in system)
2. Discovers available agents via `context.agent_loader.discover_agents()`
3. Filters out the current agent (an agent cannot dispatch to itself)
4. Embeds available agents in the tool description as XML:
   ```xml
   <available_agents>
     <agent id="summarizer">Specialist for condensing documents and text</agent>
     <agent id="cookie">Cheerful assistant who specializes in reading files</agent>
   </available_agents>
   ```
5. Returns a configured `SubagentDispatchTool` instance

This dynamic description allows the LLM to see which agents are available without hardcoding the list.

---

#### `SubagentDispatchTool.execute()`

**Signature:**
```python
async def execute(
    self,
    session: "AgentSession",
    agent_id: str = "",
    task: str = "",
    context: str = "",
    **_: Any,
) -> str:
```

**Parameters:**
- `agent_id`: ID of the target agent (e.g., "cookie", "summarizer")
- `task`: The task or prompt for the subagent
- `context`: Optional additional context to provide to the subagent

**Step-by-step execution:**

1. **Validate inputs**
   - Return error if `agent_id` or `task` is missing

2. **Create subagent session**
   ```python
   meta = self._context.history_store.create_session(
       agent_id=agent_id,
       agent_name=agent_id,
   )
   sub_session_id = meta.session_id
   ```

3. **Build dispatch content**
   - Combine task and optional context into a single message
   - If context is provided, append it as a separate section

4. **Register event source**
   - Create an `EventSource` with platform="agent" to identify inter-agent communication
   - Register it in `session_source_map` so the subagent session knows it came from another agent

5. **Create a future for the result**
   ```python
   loop = asyncio.get_running_loop()
   result_future: asyncio.Future[str] = loop.create_future()
   ```

6. **Define a temporary result handler**
   ```python
   async def handle_result(event: DispatchResultEvent) -> None:
       if event.session_id == sub_session_id:
           if not result_future.done():
               if event.error:
                   result_future.set_exception(Exception(event.error))
               else:
                   result_future.set_result(event.content)
   ```

7. **Subscribe BEFORE publish (critical\!)**
   ```python
   self._context.eventbus.subscribe(DispatchResultEvent, handle_result)
   ```
   This prevents a race condition where the subagent completes before we subscribe.

8. **Publish the dispatch event**
   ```python
   dispatch_event = DispatchEvent(
       session_id=sub_session_id,
       content=content,
       source=agent_source,
       parent_session_id=session.state.system_prompt[:50],  # tracing
   )
   await self._context.eventbus.publish(dispatch_event)
   ```

9. **Await the result with timeout**
   ```python
   response = await asyncio.wait_for(result_future, timeout=DISPATCH_TIMEOUT)
   ```
   Raises `asyncio.TimeoutError` if the subagent doesn't respond in 120 seconds.

10. **Handle errors gracefully**
    - Catch `TimeoutError` and return a timeout message
    - Catch general exceptions and return an error message

11. **Unsubscribe the handler**
    ```python
    self._context.eventbus.unsubscribe(handle_result)
    ```
    Clean up to prevent memory leaks and stale subscriptions.

12. **Return result as JSON**
    ```python
    return json.dumps({"result": response, "session_id": sub_session_id})
    ```
    The LLM can inspect both the result and the session ID for tracing.

---

### 3. AgentWorker Tool Injection

**File:** `src/mybot/server/agent_worker.py`

#### `_get_or_create_session()` updates

In the method that creates or retrieves agent sessions, the dispatch tool is conditionally injected:

```python
# Inject subagent_dispatch if multiple agents available
if self.context.agent_loader:
    from mybot.tools.subagent_tool import create_subagent_dispatch_tool
    from mybot.tools.registry import ToolRegistry
    dispatch_tool = create_subagent_dispatch_tool(
        current_agent_id=current_agent_id,
        context=self.context,
    )
    if dispatch_tool:
        all_tools = list(tools._tools.values())
        all_tools.append(dispatch_tool)
        tools = ToolRegistry(all_tools)
        logger.debug("Injected subagent_dispatch for agent %s", current_agent_id)
```

**When injection happens:**
1. After checking for cron delivery targets (post_message injection)
2. Before creating the final `AgentSession`
3. Only if an `agent_loader` is configured

**Why conditional:**
- If only one agent exists, there's no one to dispatch to, so the tool is unnecessary
- The factory returns `None` if no peers are available

---

## Why Subscribe BEFORE Publish?

A critical detail in Step 6 of `SubagentDispatchTool.execute()`:

```python
# Subscribe BEFORE publishing to avoid race condition
self._context.eventbus.subscribe(DispatchResultEvent, handle_result)

# Then publish
await self._context.eventbus.publish(dispatch_event)
```

**Why this order matters:**

In an async system, between publishing and subscribing, the subagent could complete and emit a `DispatchResultEvent` before we've registered our handler. This would cause the result to be lost.

**Timeline of race condition (if we subscribe after publish):**

```
Publish dispatch_event
  |
  v (subagent starts immediately)
Subagent completes
Subagent publishes DispatchResultEvent
Subscribers are notified (no handler registered yet\!)
  |
  v
Subscribe to DispatchResultEvent (too late\!)
Await the future (will timeout)
```

**Correct order:**

```
Subscribe to DispatchResultEvent (handler registered)
Publish dispatch_event
  |
  v (subagent starts)
Subagent completes and publishes DispatchResultEvent
Handler is notified and resolves the future (success\!)
```

---

## Cookie Agent Definition

### Agent Files

**`default_workspace/agents/cookie/AGENT.md`:**
```markdown
---
id: cookie
name: Cookie
description: A cheerful assistant who specializes in reading files and summarizing content.
---

# Cookie
You are Cookie, a cheerful and efficient assistant...
```

**`default_workspace/agents/cookie/SOUL.md`:**
```markdown
You are cheerful, efficient, and a little bit sweet.
You take pride in giving clear, well-organized summaries.
You occasionally use a gentle exclamation like "Here we go\!" or "Happy to help\!"
```

### Why Cookie?

Cookie demonstrates a specialized subagent that:
- Handles file reading and content summarization
- Has a distinct personality (cheerful, efficient)
- Complements the general-purpose `my-bot` and document-focused `summarizer`

---

## Try It Out

### Test Dispatch in the Chat

1. Start the server:
   ```bash
   python -m mybot.server
   ```

2. In a chat session, ask the main agent to delegate:
   ```
   User: Ask Cookie to read our README.md and summarize what this step does
   ```

3. The agent will:
   - Recognize that Cookie is better suited for file reading
   - Call `subagent_dispatch(agent_id="cookie", task="Read README.md...")`
   - Wait for Cookie's response via EventBus
   - Present Cookie's summary to the user

4. Check the logs:
   ```
   Injected subagent_dispatch for agent my-bot
   Cookie session created: <session-id>
   DispatchEvent published for session <session-id>
   DispatchResultEvent published from Cookie
   Result: {"result": "...", "session_id": "<session-id>"}
   ```

---

## Alternative Multi-Agent Patterns

While EventBus dispatch (this step) is flexible and decoupled, other patterns exist:

1. **Shared task lists / queues**: Agents read from a common queue and post results to a shared result bucket
2. **tmux / process spawning**: Each agent runs in its own terminal/process, agents communicate via files or sockets
3. **Router / load balancer**: A central router receives all requests and forwards to the appropriate agent
4. **Direct instantiation**: Import and call agent objects directly (tightly coupled, not recommended for scale)

The EventBus approach is chosen here because:
- Agents remain independent and loosely coupled
- Easy to add/remove agents without changing code
- Naturally supports async/await patterns
- Enables future patterns like request queuing, retries, and load balancing

---

## What Changed from Step 14

| Aspect | Step 14 | Step 15 |
|--------|---------|---------|
| Events | `DispatchEvent`, `DispatchResultEvent` | Added `parent_session_id` field |
| Tool Injection | `post_message` only | `post_message` + `subagent_dispatch` |
| Agent Sessions | Single primary agent | Multiple agents can coexist |
| Dispatch Targets | Cron delivery targets only | Any other agent in the system |
| Result Handling | Posted back to another session | Returned directly to the caller |

---

## Design Decisions

### Q: Why EventBus and not direct function calls?

**A:** The EventBus keeps agents decoupled:
- No import dependencies between agents
- Easy to add/remove agents at runtime
- Agents don't need to know about each other's implementations
- Enables future patterns like request queuing, rate limiting, and routing
- Supports distributed architectures (agents on different servers)

### Q: Why subscribe BEFORE publish?

**A:** Race condition prevention. In async systems, the subagent might complete before we register a handler, causing us to miss the result.

### Q: Why JSON response instead of returning the raw response?

**A:** The JSON envelope allows including metadata (session_id) for tracing and debugging. The LLM can inspect the entire result object.

### Q: Why does parent_session_id contain system_prompt[:50]?

**A:** It's a quick tracing hint. A proper implementation might use the session's actual ID or a correlation ID. This simplified version lets us connect parent and child sessions in logs.

---

## What's Next: Step 16 (Concurrency Control)

With multiple agents potentially running at the same time, we need to manage:
- **Rate limiting**: Prevent one agent from overwhelming the system
- **Queuing**: Handle more dispatch requests than available workers
- **Timeouts**: Already handled (120s default)
- **Error recovery**: Retry failed dispatches
- **Load balancing**: Distribute work across available agents

Step 16 will add a dispatch queue and worker pool to handle these concerns.

---

## Files Modified/Created

**Modified:**
- `pyproject.toml` (version, description)
- `src/mybot/core/events.py` (added `parent_session_id`)
- `src/mybot/server/agent_worker.py` (injected dispatch tool)
- `default_workspace/AGENTS.md` (added Cookie)

**Created:**
- `src/mybot/tools/subagent_tool.py` (dispatch factory and tool)
- `default_workspace/agents/cookie/AGENT.md` (agent definition)
- `default_workspace/agents/cookie/SOUL.md` (personality)

---

## Syntax & Import Check

All files pass Python syntax validation:
```
src/mybot/core/events.py ✓
src/mybot/tools/subagent_tool.py ✓
src/mybot/server/agent_worker.py ✓
```

---

## Summary

Step 15 introduces **agent-to-agent delegation** via the EventBus:

1. An agent calls `subagent_dispatch(agent_id="...", task="...")`
2. The tool creates a new session, subscribes to the result event, publishes a dispatch event
3. AgentWorker picks up the dispatch event and runs the subagent
4. Subagent completes and publishes a result event
5. The tool's handler receives the result and returns it to the caller
6. The original agent sees the result and responds

This enables a flexible, decoupled multi-agent architecture where specialized agents can delegate work to each other.
