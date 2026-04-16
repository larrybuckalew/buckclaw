# Step 05: Compaction

## Overview

This step adds **context window management** to the BuckClaw bot. As conversations grow, token usage can exceed Claude's context window limit. The ContextGuard component implements a two-stage strategy to keep the conversation within bounds.

## Why Compaction Matters

Claude's context window (200,000 tokens for Claude 3.5 Sonnet) is large, but extended conversations can exhaust it. Without compaction:

- Long conversations become sluggish (more tokens to process)
- The bot may start dropping older context
- Tool results and debugging output can dominate the token budget
- The LLM has less room for reasoning on each turn

Compaction keeps conversations fresh by summarizing history when needed.

## Two-Stage Compaction Strategy

ContextGuard uses a pragmatic two-phase approach:

### Phase 1: Truncate Large Tool Results

First, it identifies tool result messages (e.g., file reads, command output, API responses) that exceed 2,000 characters and truncates them with a "[truncated]" marker. This removes noise without losing conversation context.

### Phase 2: Summarize Entire Conversation

If truncation alone is insufficient (tokens still exceed the 160,000-token threshold), ContextGuard calls the LLM to summarize the entire conversation in 2-3 paragraphs. The summary captures key decisions, context, and progress, and replaces the full history with a single assistant message.

## ContextGuard Components

### Dataclass Fields

```python
token_threshold: int = 160_000      # 80% of 200k limit
max_tool_result_chars: int = 2_000  # Per tool result
```

### Core Methods

**`estimate_tokens(state, model) -> int`**
- Estimates tokens using litellm.token_counter()
- Falls back to len(str(messages)) // 4 if token_counter fails
- Essential for deciding when compaction is needed

**`_truncate_large_tool_results(messages) -> list[Message]`**
- Finds tool result messages exceeding max_tool_result_chars
- Truncates content and appends "[truncated]" marker
- Preserves conversation flow while reducing size

**`_compact_messages(state, llm, model) -> ConversationState`**
- Builds a summary request and calls the LLM
- Creates a new ConversationState with a single summary message
- Preserves the system prompt and conversation context

**`check_and_compact(state, llm, model) -> tuple[ConversationState, bool]`**
- Main entry point for context management
- Returns (updated_state, did_compact)
- Orchestrates truncation and summarization as needed

## New Slash Commands

### `/context`

Shows current context usage and token estimates.

```
Context Usage:
Messages: 24
Tokens: ~145000 (91% of 160000 threshold)
```

Use this to monitor context pressure during long conversations.

### `/compact`

Manually triggers context compaction (summarization).

```
Context compacted. 1 message(s) retained (was 24).
```

Useful when you want to reset conversation history without losing critical information.

## Integration with AgentSession

The agent's chat() loop now:

1. Stores the user message
2. **Before each LLM call**, calls `check_and_compact()` to manage context size
3. Continues with tool-calling loop as before
4. Stores the final response

This ensures context never exceeds the threshold during active conversation.

## Try It Out

**Scenario 1: Monitor context growth**

```
You: Do a web search for "best Python practices" and save the results.
```

Then check context usage:

```
You: /context
```

Output shows increasing token count as the conversation grows.

**Scenario 2: Trigger manual compaction**

After a long conversation:

```
You: /compact
```

The bot summarizes the entire conversation into 1 concise message and resets the history. Future messages see the summary as context.

**Scenario 3: Automatic compaction**

Run the bot long enough to accumulate 160,000+ tokens. The next time you send a message, ContextGuard automatically triggers Phase 1 (truncate tool results) and Phase 2 (summarize) as needed.

## Design Notes

- **Token counting is approximate**: litellm.token_counter() uses a heuristic; actual token count may vary slightly.
- **Summaries are concise**: The LLM is asked to distill key points into 2-3 paragraphs, not reproduce the full history.
- **Tool results are safe to truncate**: Most tool output (logs, file excerpts, API responses) is verbose; truncation rarely loses critical information.
- **Compaction is opt-in**: Pass `context_guard=None` to AgentSession to disable it.

## What's Next

**Step 06: Web Tools**

Expand the toolset with web-browsing capabilities. Implement:
- Fetch webpage content
- Extract structured data from web pages
- Search the web for information

These web tools will generate large result messages that benefit from the truncation strategy we built here.

## Files Modified

- `src/mybot/core/context_guard.py` -- New ContextGuard implementation
- `src/mybot/core/agent.py` -- Integrated check_and_compact() into chat loop
- `src/mybot/core/commands/builtin.py` -- Added ContextCommand and CompactCommand
- `src/mybot/cli/main.py` -- Registered new commands and created ContextGuard instance
- `pyproject.toml` -- Version 0.6.0, updated description

