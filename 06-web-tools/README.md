# BuckClaw Step 06: Web Tools

This step adds `websearch` and `webread` tools to the agent, enabling it to query the web and fetch full page content. These tools are backed by abstract provider classes, making it easy to swap implementations (Brave Search, DuckDuckGo, plain httpx, etc.) via configuration.

## Why Web Tools Matter

LLMs have a training cutoff and lack access to real-time information. Web tools let your agent:

- Find current information (news, prices, API docs)
- Access documentation beyond training data
- Verify claims with live sources
- Explore emerging topics

The agent workflow is simple: **search first for discovery, then read for details**.

## Architecture: Provider Abstraction

Two abstract base classes isolate the implementation from the tools:

### WebSearchProvider

```python
class WebSearchProvider(ABC):
    async def search(self, query: str, num_results: int = 5) -> list[SearchResult]:
        ...
```

Concrete implementation: `BraveSearchProvider` (uses Brave Search API + httpx)

### WebReadProvider

```python
class WebReadProvider(ABC):
    async def read(self, url: str) -> ReadResult:
        ...
```

Concrete implementation: `HttpxReadProvider` (fetches URLs, strips HTML tags, returns plain text)

This design lets you:
- Swap providers by configuration without touching tool code
- Add new providers (DuckDuckGo, Bing, Serp API, etc.) without modifying existing tools
- Test with mock providers in development

## The Two Tools

### websearch

Returns a ranked list of search results with title, URL, and snippet.

**Parameters:**
- `query` (required): The search query
- `num_results` (optional, default=5, max=10): How many results to return

**Returns:** Numbered list of results with title, URL, and snippet

**Example output:**
```
1. **Pickle Bot Docs**
   https://picklbot.io/
   The official Pickle Bot documentation site...

2. **Pickle Bot GitHub**
   https://github.com/myorg/picklebot
   An open-source bot framework...
```

### webread

Fetches the content of a web page and returns it as readable text.

**Parameters:**
- `url` (required): The URL to fetch

**Returns:** Page title and plain-text content (max 8000 characters)

**Example output:**
```
**Pickle Bot Docs**

Pickle Bot is a lightweight framework for building conversational agents...
[rest of page content]
```

## The Search -> Read Workflow

A typical agent interaction:

1. **User**: "What is pickle bot? Search online please."
2. **Agent** calls `websearch(query="pickle bot")` → gets 5 results
3. **Agent** calls `webread(url=first_result_url)` → fetches full content
4. **Agent** synthesizes and responds to user

This two-step pattern avoids:
- Fetching all results (wasteful)
- Missing important details in snippets (search-only)
- Blind URL fetching (read-only)

## Getting a Brave Search API Key

1. Go to [https://api.search.brave.com/](https://api.search.brave.com/)
2. Sign up for a free account
3. Copy your API key from the dashboard
4. Add it to `config.user.yaml` under `websearch.api_key`

The free tier includes a generous monthly quota suitable for development and testing.

## What Changed from Step 05

### New Files
- `src/mybot/provider/web_search/__init__.py` — Module exports
- `src/mybot/provider/web_search/base.py` — Abstract SearchResult and WebSearchProvider
- `src/mybot/provider/web_search/brave.py` — BraveSearchProvider implementation
- `src/mybot/provider/web_read/__init__.py` — Module exports
- `src/mybot/provider/web_read/base.py` — Abstract ReadResult and WebReadProvider
- `src/mybot/provider/web_read/httpx_provider.py` — HttpxReadProvider implementation
- `src/mybot/tools/websearch_tool.py` — WebSearchTool (agent-callable)
- `src/mybot/tools/webread_tool.py` — WebReadTool (agent-callable)

### Updated Files
- `src/mybot/config.py` — Added WebSearchConfig and WebReadConfig dataclasses
- `src/mybot/cli/main.py` — Conditionally wire up web tools based on config
- `pyproject.toml` — Added httpx>=0.27.0 dependency, bumped version to 0.7.0
- `default_workspace/config.example.yaml` — Added websearch and webread sections with instructions

### Behavior
- Web tools are optional: if `websearch.api_key` is empty or "YOUR_BRAVE_SEARCH_API_KEY", they are not loaded
- On startup, the CLI prints which tools are active

## Try It Out

Copy the config and add your Brave API key:

```bash
cp default_workspace/config.example.yaml default_workspace/config.user.yaml
# Edit config.user.yaml and add your api_key
```

Run the bot:

```bash
my-bot chat
```

Try the example query:

```
> What is pickle bot? Search online please.
```

The agent will:
1. Call websearch("pickle bot") → get results
2. Call webread(url) on a promising result → fetch full content
3. Synthesize an answer from the content

## Design Notes

### Why Separate Search and Read?

- **Search**: Fast discovery of relevant URLs (via snippet matching)
- **Read**: Full context when a specific URL is needed

Combining them wastes time fetching every result. This design mirrors how humans browse: scan for promising links, then deep-dive into selected ones.

### Why httpx with Tag Stripping?

- **Lightweight**: No heavy HTML parsing library needed
- **Simple**: Regex-based tag removal is straightforward and predictable
- **Extensible**: Easy to add HTML → Markdown conversion or smarter content extraction later
- **Async-first**: httpx supports async/await natively

For production, consider using `html2text` or `trafilatura` for richer content extraction.

### Error Handling

- **websearch**: Returns empty list on network errors or API failures (agent sees "No results found")
- **webread**: Returns error message in the result (agent sees "Error reading URL: [reason]")

Both gracefully degrade rather than crashing, letting the agent handle the situation.

## What's Next: Step 07 Event-Driven

Step 07 will add event subscriptions so the agent can react to external triggers (incoming messages, file changes, timers) rather than only responding to user input. This enables:

- Proactive notifications
- Background monitoring
- Integration with external systems
- Always-on behaviors

---

**File tree:**

```
06-web-tools/
├── src/mybot/
│   ├── provider/
│   │   ├── web_search/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   └── brave.py
│   │   ├── web_read/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   └── httpx_provider.py
│   ├── tools/
│   │   ├── websearch_tool.py
│   │   ├── webread_tool.py
│   ├── config.py (updated)
│   ├── cli/main.py (updated)
├── pyproject.toml (updated)
├── default_workspace/config.example.yaml (updated)
└── README.md (this file)
```
