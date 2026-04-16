# Workspace Guide

This workspace powers my-bot, your AI assistant.

## Directory Structure

    default_workspace/
    ├── agents/           -- Agent definitions (AGENT.md + optional SOUL.md)
    ├── skills/           -- Skill definitions (SKILL.md)
    ├── crons/            -- Scheduled jobs (CRON.md)
    ├── BOOTSTRAP.md      -- This file
    ├── AGENTS.md         -- Agent roster and dispatch patterns
    ├── config.user.yaml  -- Your configuration (API keys, etc.)
    └── config.runtime.yaml -- Live overrides (hot-reloaded)

## Key Rules

1. Always use relative paths when creating files (relative to workspace root).
2. Skill files follow the SKILL.md format with YAML front-matter.
3. Cron jobs follow the CRON.md format with a cron expression.
4. Never read or write config.user.yaml (it may contain API keys).
