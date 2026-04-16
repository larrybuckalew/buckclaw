# Step 01 -- Give Your Agent a Tool

> **BuckClaw Tutorial** - Phase 1: Capable Single Agent

Simple tools are more powerful than you think.
Read, Write, and Bash is enough to let your agent inspect files, write code, and run commands.

---

## What We're Building

Extending the Step 00 chat loop with a **tool-calling loop**. The agent can now:

- Read any file in the project workspace
- Create or overwrite files
- Run shell commands and see their output

The LLM decides *when* to call a tool, *which* tool, and *what arguments* to pass.
Our code executes the call and feeds the result back -- then the LLM continues.

---

## Key Components

### Stop Reasons

After every LLM call we inspect the response:

| Stop reason | Meaning |
|---|---|
| `end_turn` | LLM is finished -- return the content to the user |
| `tool_use` | LLM wants to invoke tools -- execute them and loop |

### `BaseTool` -- `src/mybot/tools/base.py`

The contract every tool must satisfy:

```python
class BaseTool(ABC):
    name: str           # unique identifier used in function-call JSON
    description: str    # plain-English explanation shown to the LLM
    parameters: dict    # JSON Schema describing the tool's arguments

    async def execute(self, session, **kwargs) -> str: ...
    def get_tool_schema(self) -> dict: ...  # OpenAI function-call format
```

### `ToolRegistry` -- `src/mybot/tools/registry.py`

Stores tools by name, provides schemas to the LLM, and dispatches calls:

```
registry.get_tool_schemas()              -> list sent to LLM with every request
registry.execute(session, name, args)    -> finds and runs the right tool
```

### Built-in Tools -- `src/mybot/tools/builtin.py`

| Tool | What it does |
|---|---|
| `read_file` | Read a file (relative to workspace) |
| `write_file` | Write or overwrite a file |
| `bash` | Run a shell command, capture stdout + stderr |

All paths are validated to stay inside the workspace directory.
Bash output is capped at 8,000 characters to protect the context window.

### Tool-Calling Loop -- `src/mybot/core/agent.py`

```
chat(message)
  |
  +-- append user message
  |
  +--> LLM call (with tool schemas)
         |
         +-- tool_calls? --Yes--> execute each tool
         |                              |
         |<---------- append results ---+
         |
         +-- No tool calls -> return final reply
```

A `MAX_TOOL_ROUNDS = 10` guard prevents infinite loops.

---

## What Changed from Step 00

| File | Change |
|---|---|
| `types.py` | Added `ToolCall` dataclass; `Message` extended with tool fields |
| `provider/llm/base.py` | `chat()` now returns `(content, tool_calls)` tuple |
| `core/agent.py` | `AgentSession` accepts `ToolRegistry`; `chat()` is now a loop |
| `tools/` | **New** -- `base.py`, `builtin.py`, `registry.py` |
| `cli/main.py` | Wires `ReadFileTool`, `WriteFileTool`, `BashTool` into the session |

---

## Project Layout

```
01-tools/
├── pyproject.toml
├── default_workspace/
│   └── config.example.yaml
└── src/
    └── mybot/
        ├── types.py            # + ToolCall dataclass
        ├── config.py
        ├── core/
        │   ├── state.py
        │   └── agent.py        # <- tool-calling loop added
        ├── provider/llm/
        │   └── base.py         # <- returns (content, tool_calls)
        ├── tools/              # <- NEW
        │   ├── base.py
        │   ├── builtin.py
        │   └── registry.py
        └── cli/
            ├── chat.py
            └── main.py         # <- tools wired in
```

---

## Try It Out

```bash
cd 01-tools
cp default_workspace/config.example.yaml default_workspace/config.user.yaml
# Add your Anthropic API key to config.user.yaml

uv run my-bot chat
```

```
You: Hey, can you read your README.md please?
my-bot: [reads README.md via read_file tool]

# Step 01 -- Give Your Agent a Tool
# ...

You: What Python files are in the src directory?
my-bot: [runs: find src -name "*.py"]
src/mybot/__init__.py
src/mybot/types.py
...

You: Write a hello.py file that prints "Hello from my-bot\!"
my-bot: [creates hello.py via write_file tool]
Done\! I've created hello.py for you.
```

---

## Design Decisions

**Why loop on tool calls instead of a single pass?**
The LLM often needs to chain tools -- e.g. run `bash` to see what files exist,
then `read_file` to inspect one. The loop handles this naturally.

**Why cap bash output at 8,000 chars?**
Unbounded output would flood the context window and waste tokens.
The cap keeps the agent responsive.

**Why validate paths against workspace?**
Safety: without this check the LLM could read `~/.ssh/id_rsa`
or write to system files outside the project.

---

## What's Next

**Step 02: Skills** -- Add dynamic capability loading with `SKILL.md` files
so the agent can pick up new specialised behaviours at runtime.
