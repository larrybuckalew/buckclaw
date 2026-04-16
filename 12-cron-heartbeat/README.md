# Step 12: Cron + Heartbeat

This step adds two background scheduling mechanisms to BuckClaw:

-- **CRON**: Multiple named jobs, each with a cron expression. A background worker ticks every minute, finds due jobs, and dispatches them to the agent via the EventBus.

-- **HEARTBEAT**: A single periodic pulse that runs in the main session at a fixed interval, no cron expression. Useful for proactive check-ins (e.g. "remind me of my tasks every 30 minutes").

Both mechanisms use a new internal event type `DispatchEvent` rather than `InboundEvent`, so they don't interfere with user sessions and their messages don't appear in the chat.

## CRON vs HEARTBEAT

| Feature | CRON | HEARTBEAT |
|---------|------|-----------|
| Multiple jobs | Yes | No (single pulse) |
| Scheduling | Cron expressions (time-based) | Fixed interval (e.g., every 30 min) |
| Session | One per job | Main session only |
| Configuration | CRON.md files in workspace | config.yaml heartbeat section |
| Use case | Daily standups, weekly reports, backups | Proactive reminders, status checks |

## CRON.md Format

Each cron job lives in its own directory with a `CRON.md` file:

```
default_workspace/crons/<job-id>/CRON.md
```

The file starts with YAML front-matter:

```yaml
---
id: daily-standup
name: Daily Standup
description: Run standup at 9 AM every weekday
agent: my-bot
schedule: "0 9 * * 1-5"
prompt: "Conduct the daily standup: ask about progress, blockers, and priorities."
one_off: false
---
```

### CRON.md Fields

-- **id** (required): Unique kebab-case identifier (e.g., `daily-standup`)
-- **name** (required): Human-readable name
-- **description**: One-sentence description
-- **agent** (required): Which agent to send this job to (default: `my-bot`)
-- **schedule** (required): Cron expression (see examples below)
-- **prompt** (required): The message sent to the agent when this job fires
-- **one_off** (optional): If true, delete the job after its first run (default: false)

### Cron Expression Examples

```
"0 9 * * *"     -- every day at 9 AM
"0 9 * * 1"     -- every Monday at 9 AM
"0 9 * * 1-5"   -- weekdays (Mon-Fri) at 9 AM
"*/30 * * * *"  -- every 30 minutes
"0 */6 * * *"   -- every 6 hours
"0 0 1 * *"     -- first day of every month at midnight
"0 0 * * 0"     -- every Sunday at midnight
```

For more complex expressions, see the cron standard (man crontab).

## CronWorker

The `CronWorker` is a background task that:

1. Ticks every 60 seconds
2. Loads all CRON.md files from `default_workspace/crons/`
3. Finds jobs whose schedule matches the current minute using `croniter`
4. Publishes a `DispatchEvent` to the EventBus for each due job
5. Creates a separate session for each cron job (one session per job ID)
6. Automatically deletes one-off jobs after they fire

### find_due_jobs()

```python
def find_due_jobs(jobs, now: datetime | None = None):
    """Return jobs whose cron expression matches the current minute."""
```

This function checks if the last scheduled time for a job falls within the past 60 seconds, preventing duplicate fires within the same minute window.

## HeartbeatWorker

The `HeartbeatWorker` is a simpler background task that:

1. Runs a single periodic pulse at a fixed interval (default: 30 minutes)
2. Fires only in the main session (configured in `config.yaml`)
3. Publishes a `DispatchEvent` to the EventBus on each pulse
4. Is disabled by default (set `heartbeat.enabled: true` to activate)

Heartbeat is useful for:
-- Proactive reminders ("summarize pending tasks every 30 minutes")
-- Regular status checks
-- Keeping the agent engaged in long-running scenarios

## DispatchEvent vs InboundEvent

BuckClaw now distinguishes between two event types:

### InboundEvent
-- User-initiated messages
-- Appear in chat history
-- Handled by `AgentWorker.handle_inbound()`
-- Published by channels (CLIChannel, TelegramChannel, etc.)

### DispatchEvent
-- System-initiated messages (cron jobs, heartbeat pulses)
-- Do NOT appear in chat (separate session context)
-- Handled by `AgentWorker.handle_dispatch()`
-- Published by CronWorker and HeartbeatWorker
-- Return results as `DispatchResultEvent` (not OutboundEvent)

Both use the same `AgentSession.chat()` pipeline, so the agent sees no difference in how to process them. The distinction is architectural: DispatchEvents keep scheduled tasks isolated from user conversations.

## cron-ops Skill

The `cron-ops` skill teaches the agent how to create, list, and delete cron jobs. It's entirely built on existing tools:

-- `write_file`: Create the CRON.md
-- `bash`: Find and delete jobs
-- `read_file`: Show job details

### How the Agent Creates a Cron Job

User: "Send me a cat meme every morning at 8 AM"

Agent:
1. Decides on id: `daily-cat-meme`
2. Decides on schedule: `"0 8 * * *"`
3. Decides on prompt: `"Find a funny cat meme and share it with a brief description."`
4. Uses `write_file` to create `default_workspace/crons/daily-cat-meme/CRON.md`
5. Confirms with the user

On the next minute tick, CronWorker picks it up and starts firing it.

### How the Agent Lists Cron Jobs

```bash
find default_workspace/crons -name "CRON.md"
```

Then read each file to show details.

### How the Agent Deletes a Cron Job

```bash
rm -rf default_workspace/crons/daily-standup
```

Always ask the user before deleting.

## Configuration

Add to `default_workspace/config.user.yaml`:

```yaml
heartbeat:
  enabled: true
  interval_seconds: 1800
  prompt: "Check in: any pending tasks or reminders I should know about?"
```

-- **enabled**: Set to true to activate the heartbeat worker
-- **interval_seconds**: Pulse frequency in seconds (default: 1800 = 30 minutes)
-- **prompt**: The message sent on each heartbeat pulse

## What Changed from Step 11

### New Files
-- `src/mybot/core/cron_loader.py`: Discovers and loads CRON.md files
-- `src/mybot/server/cron_worker.py`: Background worker for cron jobs
-- `src/mybot/server/heartbeat_worker.py`: Background worker for heartbeat pulses
-- `default_workspace/crons/hello-world/CRON.md`: Example cron job
-- `default_workspace/skills/cron-ops.md`: Skill for managing cron jobs

### Modified Files
-- `src/mybot/core/events.py`: Added `DispatchEvent` and `DispatchResultEvent`
-- `src/mybot/core/context.py`: Added `cron_loader` and `heartbeat_session_id` fields
-- `src/mybot/utils/config.py`: Added `HeartbeatConfig` class
-- `src/mybot/server/agent_worker.py`: Added `handle_dispatch()` method and subscription
-- `src/mybot/cli/main.py`: Initialize and start CronWorker and HeartbeatWorker
-- `pyproject.toml`: Added `croniter>=2.0` dependency
-- `default_workspace/config.example.yaml`: Added heartbeat section

## Design Notes

### Why DispatchEvent Instead of InboundEvent?

Using a separate event type keeps scheduled tasks isolated from user conversations:

-- Cron job responses don't clutter the user's chat history
-- Each cron job has its own session (one session per job ID)
-- Heartbeat runs in a dedicated main session
-- The agent can still see full context within each session, but not across user/cron/heartbeat sessions

### Why cron-ops as a Skill Rather Than Dedicated Tools?

Cron job management uses only existing tools (`write_file`, `bash`, `read_file`). By teaching the agent the pattern in a skill, we:

-- Avoid adding new tool registrations
-- Let the agent explore and improve the workflow
-- Keep the tool registry lean and focused
-- Show how skills can be "protocols" that compose existing tools

## Try-It-Out: Create Your First Cron Job

1. Start the server:
   ```bash
   cd /path/to/step12
   python -m mybot.cli.main server
   ```

2. In the chat, ask the agent:
   ```
   Create a cron job that sends me a motivational quote every morning at 7 AM.
   ```

3. The agent will:
   - Propose a job ID (e.g., `morning-quote`)
   - Use `write_file` to create the CRON.md
   - Confirm the schedule

4. On the next minute, the cron fires and the agent sends a motivational quote.

5. List all jobs:
   ```
   Show me all my scheduled cron jobs.
   ```

6. Delete a job:
   ```
   Delete the morning-quote job.
   ```

## Running with Heartbeat

Enable the heartbeat in `config.user.yaml`:

```yaml
heartbeat:
  enabled: true
  interval_seconds: 300
  prompt: "Give me a 2-sentence status update: what are the most important things I should know right now?"
```

Start the server and let it run. Every 5 minutes (300 seconds), the agent will provide a status update in the main session.

## What's Next: Step 13 -- Multi-Layer Prompts

Step 13 will introduce system prompt layering:

-- **Agent-level prompts**: Default behavior for all agent instances
-- **Session-level prompts**: Custom instructions per session
-- **Tool-level prompts**: Contextual guidance for tool use

This allows fine-tuned agent behavior without hardcoding business logic.
