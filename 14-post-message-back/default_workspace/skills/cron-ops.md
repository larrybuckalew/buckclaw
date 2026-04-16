---
id: cron-ops
name: Cron Ops
description: Create, list, and delete scheduled cron jobs for the agent.
---

# Cron Ops

You can manage scheduled cron jobs for this agent.
Cron jobs are defined as CRON.md files in default_workspace/crons/<id>/CRON.md.

## CRON.md Format

Each cron job is a directory with a CRON.md file:

    default_workspace/crons/<id>/CRON.md

The file must start with YAML front-matter:

    ---
    id: <unique-kebab-case-id>
    name: <Human Readable Name>
    description: <One sentence description>
    agent: my-bot
    schedule: "<cron expression>"
    prompt: "<Message sent to the agent when this job fires>"
    one_off: false
    target_session_id: ""     # set to the user's session_id to enable post_message delivery
    ---

## Cron Expression Examples

    "0 9 * * *"     -- every day at 9 AM
    "0 9 * * 1"     -- every Monday at 9 AM
    "*/30 * * * *"  -- every 30 minutes
    "0 8 * * 1-5"   -- weekdays at 8 AM

## How to Create a Cron Job

1. Decide on an id (e.g. `daily-standup`).
2. Decide on a cron schedule and prompt.
3. Use `write_file` to create the CRON.md:

   path: default_workspace/crons/daily-standup/CRON.md

4. Confirm with the user.

## How to List Cron Jobs

Use `bash` to find all CRON.md files:
    find default_workspace/crons -name "CRON.md"

Then use `read_file` to show each one.

## How to Delete a Cron Job

Use `bash` to remove the directory:
    rm -rf default_workspace/crons/<id>

Always confirm with the user before deleting.

## Delivering Messages Back to Users

When a user asks you to "message me later" or "remind me of X in Y minutes/hours":

1. Get the user's session_id: it is available in the runtime context as "Session ID: <id>".
2. Create a one-off cron job (one_off: true) with:
   - `target_session_id` set to the user's session_id
   - A `prompt` that instructs the cron agent to call post_message with the desired content
3. The prompt should be specific, e.g.:
   "Call post_message with content: 'Hi\! Your reminder: [X]'"

The `post_message` tool will only be available in the cron session when `target_session_id` is set.

## Important Notes

- The CronWorker ticks every 60 seconds. New jobs are picked up automatically.
- One-off jobs (one_off: true) are automatically deleted after firing once.
- Jobs run in their own session, separate from the current chat session.
- When a cron job has target_session_id set, the post_message tool is injected.
