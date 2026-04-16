# Step 02: Skills as Lazy-Loaded Capabilities

## What We're Building

In this step, we transform your bot from a simple chat interface into a skill-aware agent that can discover and load capabilities on demand. Rather than embedding everything in the system prompt, we're implementing **skills as lazy-loaded, discoverable modules** that the LLM can reason about and request at runtime.

Skills are the foundation of an extensible AI system. By decoupling skill definitions from the main bot logic, we enable:

- Dynamic capability discovery without modifying core code
- User-friendly skill management and organization
- Clear separation of concerns between the bot framework and skill implementations
- A path toward persistent skill state and user-specific skill sets (later steps)

## SKILL.md Format

Each skill is defined in a simple, self-contained file: `SKILL.md`

The format combines YAML front-matter with markdown documentation:

```yaml
---
id: weather
name: Weather Lookup
description: Get current weather for a city
---

# Weather Lookup

Fetches current weather conditions for any city worldwide.

## Usage

Call this skill with a city name and get temperature, conditions, and forecast info.

## Implementation Details

Uses the OpenWeatherMap API to fetch real-time weather data.
```

**Front-matter fields:**
- `id`: Unique identifier (used internally and in function names)
- `name`: Human-readable display name
- `description`: One-line summary of what the skill does

**Markdown body:** Full documentation visible to users and developers

## Two Approaches to Skills

### 1. Tool Approach (This Step)

What we implement here. Skills are exposed as **tools that the LLM can call**. The bot:

1. Discovers all SKILL.md files in the `skills/` directory
2. Creates tool definitions for each skill
3. Sends the tool descriptions to Claude with available skill names and descriptions in XML
4. When Claude requests a skill, the bot loads and executes it

**Advantages:**
- LLM has full control over when and how skills execute
- Natural integration with Claude's tool-calling capability
- Can chain skills together in creative ways
- Skills can have complex parameters

### 2. System Prompt Approach (Step 13)

An alternative covered later in the tutorial. Skills are embedded directly in the system prompt rather than exposed as tools.

**When to use which:**
- Use **Tool Approach** when you want LLM agency and flexibility
- Use **System Prompt Approach** when you want simpler, more predictable behavior

## Key Components

### SkillDef (dataclass)

```python
@dataclass
class SkillDef:
    id: str
    name: str
    description: str
```

Simple data class representing a skill's metadata. Loaded from SKILL.md front-matter.

### SkillLoader

Handles skill discovery and loading:

- `discover_skills(directory: Path) -> list[SkillDef]`: Scans `skills/` directory, parses all SKILL.md files, returns skill definitions
- `load_skill(skill_id: str) -> dict`: Loads the full SKILL.md content, returns both front-matter and body

### create_skill_tool (factory function)

Creates tool definitions that Claude can invoke:

```python
def create_skill_tool(skill: SkillDef) -> dict:
    return {
        "type": "function",
        "function": {
            "name": f"load_skill_{skill.id}",
            "description": f"Load the {skill.name} skill",
            "parameters": {...}
        }
    }
```

### SkillTool

The actual tool handler. When Claude requests a skill:

1. Receives the skill_id parameter
2. Calls `SkillLoader.load_skill(skill_id)`
3. Returns the full SKILL.md content to Claude (formatted in XML)

## Tool Description with Embedded Skill Metadata

The critical piece is how we communicate available skills to Claude. The tool description includes all discovered skills in structured XML:

```
Load a skill capability by name. Available skills:
<skills>
<skill>
  <id>weather</id>
  <name>Weather Lookup</name>
  <description>Get current weather for a city</description>
</skill>
<skill>
  <id>calculator</id>
  <name>Calculator</name>
  <description>Perform math operations</description>
</skill>
</skills>
```

This gives Claude visibility into what skills exist and what they do, so it can make informed decisions about loading them.

## What Changed from Step 01

### New Files and Modules

- `skills/` directory: Holds all SKILL.md files
- `my_bot/skills/` module: 
  - `__init__.py`: Exports main components
  - `skill_loader.py`: Implements SkillLoader and SkillDef
  - `skill_tool.py`: Implements create_skill_tool and SkillTool

### Updated main.py

- Imports SkillLoader and skill tool utilities
- Calls `SkillLoader.discover_skills()` at startup
- Dynamically creates tools for each discovered skill
- Includes skill tools in the tools list sent to Claude

### Project Layout

```
buckclaw/02-skills/
├── README.md                          (this file)
├── my_bot/
│   ├── __init__.py
│   ├── main.py                        (updated with skill integration)
│   └── skills/
│       ├── __init__.py
│       ├── skill_loader.py            (new: SkillDef, SkillLoader)
│       └── skill_tool.py              (new: create_skill_tool, SkillTool)
├── skills/
│   └── example.skill.md               (sample skill)
└── pyproject.toml
```

## Try It Out

### Start a Chat Session

```bash
uv run my-bot chat
```

### Ask About Available Skills

```
user> What skills do you have available?
```

The bot will list all discovered skills from the `skills/` directory, showing their names and descriptions.

### Request a Skill

```
user> Can you create a weather skill for me?
```

Claude will recognize that no weather skill exists yet and can provide you with the SKILL.md template. You can then:

1. Create a new file: `skills/weather.skill.md`
2. Fill in the front-matter and documentation
3. Implement the actual weather lookup logic
4. Restart the bot to discover the new skill

On the next chat session, the weather skill will be available.

## What's Next: Step 03

In Step 03 (Persistence), we'll add:

- Persistent skill storage across sessions
- User-specific skill sets
- Skill versioning and updates
- Database integration to remember skills between restarts

For now, skills are discovered at startup but not persisted. Each bot restart reloads from disk.

---

**Key Insight:** By separating skill definitions (SKILL.md) from skill execution, we've created a system where capabilities are discovered, managed, and extended without touching the core bot code. This is the foundation for truly extensible AI agents.
