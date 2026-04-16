---
id: skill-creator
name: Skill Creator
description: Guide for writing new SKILL.md files that work well with this agent.
---

# Skill Creator

You help the user design and write new skills for this agent.

## SKILL.md Format

Every skill is a Markdown file with YAML front-matter:

```
---
id: my-skill          # unique kebab-case identifier
name: My Skill        # human-readable display name
description: One sentence about what this skill does.
---

# My Skill

Full instructions the agent should follow when using this skill...
```

## Guidelines

- Keep the `description` to one sentence -- it appears in the skill tool schema.
- The body can be as long as needed; the agent only reads it when it calls the skill.
- Use clear headings so the agent can skim the skill content quickly.
- Include examples where helpful.

## Workflow

1. Ask the user what capability they want to add.
2. Draft the SKILL.md content.
3. Use `write_file` to save it to `default_workspace/skills/<id>.md`.
4. Confirm the skill appears when the agent lists skills.
