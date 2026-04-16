# Step 08: Config Hot Reload

## Overview

Step 08 adds **live configuration reloading** without requiring a restart. The application now watches for changes to configuration files and automatically updates the live config object. All workers and adapters see the changes immediately via the shared `AppContext`.

User-facing behavior is identical to Step 07 -- this is pure infrastructure that enables configuration changes to take effect mid-session.

## Key Features

### 1. Pydantic Config Model

The new `Config` class (in `src/mybot/utils/config.py`) replaces the old dataclass `AppConfig`:

```python
class Config(BaseModel):
    workspace: Path = Field(default_factory=Path.cwd, exclude=True)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    websearch: WebSearchConfig = Field(default_factory=WebSearchConfig)
    webread: WebReadConfig = Field(default_factory=WebReadConfig)
```

Benefits:
- Built-in validation via Pydantic
- Type safety for all config sections
- Serialization/deserialization support
- In-place reload method for live updates

### 2. Deep Merge Strategy

Config files are loaded and merged in order:

1. `config.user.yaml` (base configuration)
2. `config.runtime.yaml` (runtime overrides)

The `_deep_merge()` helper recursively merges nested dictionaries:

```python
def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)  # Recurse on nested dicts
        else:
            result[key] = val  # Scalar keys override completely
    return result
```

Example merge:

```yaml
# config.user.yaml
llm:
  model: "claude-3-5-haiku"
  api_key: "sk-..."
agent:
  name: "my-bot"
  system_prompt: "You are helpful."

# config.runtime.yaml
agent:
  system_prompt: "You are helpful and DEBUG."
  
# Result: llm unchanged, agent.system_prompt updated, agent.name unchanged
```

### 3. In-Place Reload

The `Config.reload()` method updates the live object without creating a new one:

```python
def reload(self) -> bool:
    """Re-read config files and update this object in-place. Returns True on success."""
    try:
        data = self._load_merged_configs(self.workspace)
        new = Config.model_validate(data)
        new.workspace = self.workspace
        for field_name in Config.model_fields:
            if field_name == "workspace":
                continue
            setattr(self, field_name, getattr(new, field_name))
        logger.info("Config reloaded from %s", self.workspace)
        return True
    except Exception as exc:
        logger.error("Config reload failed: %s", exc)
        return False
```

Why in-place mutation?
- The live `Config` object is held by `AppContext` and shared across all workers
- Replacing the object would require updating references everywhere
- In-place mutation ensures all workers see the change immediately (no race conditions)
- Exception handling preserves the old config if reload fails

### 4. File Watcher (Watchdog)

The `ConfigHandler` class (a `FileSystemEventHandler`) detects file changes:

```python
class ConfigHandler(FileSystemEventHandler):
    def on_modified(self, event: FileModifiedEvent) -> None:
        if event.is_directory:
            return
        src = str(event.src_path)
        if src.endswith("config.user.yaml") or src.endswith("config.runtime.yaml"):
            logger.info("Config file changed: %s", src)
            # Schedule reload on the asyncio event loop (thread-safe)
            self._loop.call_soon_threadsafe(self._config.reload)
```

Key details:
- Watchdog runs on a **background OS thread** (not asyncio)
- Uses `call_soon_threadsafe()` to schedule the reload on the asyncio event loop
- This ensures thread-safe access to the `Config` object
- Only watches YAML files (ignores other changes in the workspace)

### 5. ConfigReloader Worker

The `ConfigReloader` is a background worker that manages the watchdog observer:

```python
class ConfigReloader(Worker):
    async def run(self) -> None:
        loop = asyncio.get_event_loop()
        handler = ConfigHandler(config=self._config, loop=loop)
        self._observer = Observer()
        self._observer.schedule(handler, str(self._config.workspace), recursive=False)
        self._observer.start()
        logger.info("ConfigReloader watching %s", self._config.workspace)
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            # Clean shutdown
            self._observer.stop()
            self._observer.join()
            raise
```

Responsibilities:
- Owns the watchdog `Observer` lifecycle
- Watches the workspace directory (non-recursive)
- Handles graceful shutdown via `asyncio.CancelledError`

## Updated Architecture

### main.py Changes

1. Import new classes:
```python
from mybot.utils.config import Config
from mybot.utils.config_reloader import ConfigReloader
```

2. Load config with the new factory:
```python
cfg = Config.load(workspace_dir)
```

3. Create and start the reloader:
```python
config_reloader = ConfigReloader(config=cfg)
await config_reloader.start()
```

4. Shut down the reloader on exit:
```python
try:
    await cli_adapter.run()
finally:
    await config_reloader.stop()
    await agent_worker.stop()
    await eventbus.stop()
```

### context.py Changes

Updated `AppContext` to use the new `Config`:

```python
@dataclass
class AppContext:
    config: Config  # was AppConfig
    eventbus: EventBus
    llm: LLMProvider
    history_store: HistoryStore
    tool_registry: ToolRegistry
    skill_loader: SkillLoader
```

## Practical Usage

### Scenario: Change Agent Personality Mid-Session

1. Bot is running with default system prompt:
```
You are a helpful AI assistant.
```

2. Edit `config.runtime.yaml`:
```yaml
agent:
  system_prompt: |
    You are my-bot in DEBUG mode. Be extra verbose and explain
    every reasoning step in detail.
```

3. Save the file. You'll see in logs:
```
Config file changed: /path/to/config.runtime.yaml
Config reloaded from /path/to/workspace
```

4. Continue chatting. Next message uses the new prompt.

### Scenario: Switch Models Mid-Session

Edit `config.runtime.yaml`:
```yaml
llm:
  model: "anthropic/claude-opus-4-6"
```

Save. The `LLMProvider` still has the old model, but on the next turn (when `AgentWorker` reads `context.config.llm.model`), it will use the new model.

Note: If you need to switch LLM providers dynamically, you'd also need to reinitialize the `LLMProvider` (beyond this step's scope).

## Design Rationale

### Why not recreate the Config object?

If we did:
```python
# BAD: creates a new object
self._config = Config.load(self.workspace)
```

Problem: `AppContext` still holds a reference to the old `Config`. Workers don't see the change.

Solution: Update the object in-place. All references remain valid.

### Why call_soon_threadsafe?

Watchdog's `FileSystemEventHandler.on_modified()` runs on a **background OS thread**. Asyncio is **not thread-safe**.

Problem:
```python
# WRONG: asyncio call from a background thread
self._config.reload()  # May race with asyncio event loop
```

Solution: Schedule the call on the asyncio event loop:
```python
self._loop.call_soon_threadsafe(self._config.reload)
```

This is thread-safe and executes on the next asyncio iteration.

## Dependencies Added

- **pydantic>=2.0** -- Config validation and modeling
- **watchdog>=4.0** -- File system event monitoring

## What Changed from Step 07

### Files Added
- `src/mybot/utils/__init__.py` -- New package
- `src/mybot/utils/config.py` -- Pydantic Config with reload
- `src/mybot/utils/config_reloader.py` -- Watchdog worker
- `default_workspace/config.runtime.yaml` -- Runtime overrides template

### Files Modified
- `src/mybot/core/context.py` -- Import Config from utils, type hint updated
- `src/mybot/cli/main.py` -- Use Config.load(), start ConfigReloader
- `pyproject.toml` -- Version 0.9.0, added pydantic and watchdog

### Files Removed
- `src/mybot/config.py` -- Functionality moved to utils/config.py (old AppConfig deleted)

## Try It Out

1. Start the bot:
```bash
cd 08-config-hot-reload
python -m mybot.cli.main chat
```

2. Wait for the prompt and the message:
```
[dim]Config hot-reload: enabled[/dim]
```

3. In another terminal, edit `default_workspace/config.runtime.yaml`:
```yaml
agent:
  system_prompt: |
    You are a pirate AI. Answer every question in pirate speak.
```

4. Save the file. In the bot logs, you'll see:
```
Config file changed: ...config.runtime.yaml
Config reloaded from ...
```

5. Type a new message. The bot responds in pirate accent\!

6. Change it back to normal and save again. Next message reverts.

## What's Next: Step 09

Step 09 introduces **Channels** -- a way to organize conversations and manage context per channel. Each channel gets its own history and config overrides.

