# MCP Server (Model Context Protocol)

The library includes an MCP server that exposes every model as a separate tool for AI assistants like Claude Desktop and Antigravity. Enable only the models you need to keep agent context size small.

## Configuration

Add to your MCP config file (no installation required via npm, handled by python `uvx` native tools):

**Claude Desktop** (`~/.config/claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "perplexity-webui-scraper": {
      "command": "uvx",
      "args": [
        "--from",
        "perplexity-webui-scraper[mcp]@latest",
        "perplexity-webui-scraper",
        "mcp"
      ],
      "env": {
        "PERPLEXITY_SESSION_TOKEN": "your_token_here"
      }
    }
  }
}
```

**From GitHub prod branch:**

```json
{
  "mcpServers": {
    "perplexity-webui-scraper": {
      "command": "uvx",
      "args": [
        "--from",
        "perplexity-webui-scraper[mcp]@git+https://github.com/henrique-coder/perplexity-webui-scraper.git@prod",
        "perplexity-webui-scraper",
        "mcp"
      ],
      "env": {
        "PERPLEXITY_SESSION_TOKEN": "your_token_here"
      }
    }
  }
}
```

**From local directory (for development):**

```json
{
  "mcpServers": {
    "perplexity-webui-scraper": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/perplexity-webui-scraper",
        "run",
        "perplexity-webui-scraper",
        "mcp"
      ],
      "env": {
        "PERPLEXITY_SESSION_TOKEN": "your_token_here"
      }
    }
  }
}
```

## Optional Podman Image

For containerized stdio setups only:

```bash
# Pull published MCP image
podman pull ghcr.io/henrique-coder/perplexity-webui-scraper:mcp

# Run MCP server (requires token)
podman run --rm -it -e PERPLEXITY_SESSION_TOKEN=your_token ghcr.io/henrique-coder/perplexity-webui-scraper:mcp
```

This is niche. Prefer `uvx` for normal MCP client setups.

## Available Tools

Each tool uses a specific AI model. Enable only the ones you need:

Tools marked `[AVAILABLE]` can be called normally. `[UNSTABLE]`, `[UNKNOWN]`, and `[UNAVAILABLE]` tools require `allow_risky_model=true`. The generic `pplx_custom` tool accepts an internal identifier, which always starts with `unknown` status.

<!-- BEGIN GENERATED MODEL CATALOG -->
### Status reference

| Status | Meaning | Runtime behavior |
| --- | --- | --- |
| `available` | Confirmed to work normally. | Normal use; the local minimum-tier check applies. |
| `unstable` | Confirmed to work, but not guaranteed to remain available. | Requires `allow_risky_model`; Perplexity makes the final access decision. |
| `unknown` | Current availability has not been confirmed. | Requires `allow_risky_model`; this is the default for unverified entries. |
| `unavailable` | Confirmed not to work with the current backend. | Requires `allow_risky_model`; retained for history and expected to fail. |

### Model tools

| Tool | Model ID | Name | Min. tier | Status | Last tested (UTC) |
| --- | --- | --- | --- | --- | --- |
| `pplx_best` | `perplexity/best` | Best | free | `available` | — |
| `pplx_deep_research` | `perplexity/deep-research` | Deep research | pro | `available` | — |
| `pplx_sonar` | `perplexity/sonar-2` | Sonar 2 | pro | `available` | — |
| `pplx_gpt56_terra` | `openai/gpt-5.6-terra` | GPT-5.6 Terra | pro | `available` | — |
| `pplx_gpt56_terra_thinking` | `openai/gpt-5.6-terra-thinking` | GPT-5.6 Terra Thinking | pro | `available` | — |
| `pplx_gpt56_sol` | `openai/gpt-5.6-sol` | GPT-5.6 Sol | max | `available` | — |
| `pplx_gpt56_sol_thinking` | `openai/gpt-5.6-sol-thinking` | GPT-5.6 Sol Thinking | max | `available` | — |
| `pplx_claude_s50` | `anthropic/claude-sonnet-5` | Claude Sonnet 5 | pro | `available` | — |
| `pplx_claude_s50_think` | `anthropic/claude-sonnet-5-thinking` | Claude Sonnet 5 Thinking | pro | `available` | — |
| `pplx_claude_o48` | `anthropic/claude-opus-4.8` | Claude Opus 4.8 | max | `available` | — |
| `pplx_claude_o48_think` | `anthropic/claude-opus-4.8-thinking` | Claude Opus 4.8 Thinking | max | `available` | — |
| `pplx_glm52` | `z-ai/glm-5.2` | GLM-5.2 | pro | `available` | — |
| `pplx_gemini31_pro_think_low` | `google/gemini-3.1-pro-thinking-low` | Gemini 3.1 Pro | pro | `available` | — |
| `pplx_gemini31_pro_think_high` | `google/gemini-3.1-pro-thinking-high` | Gemini 3.1 Pro Thinking | pro | `available` | — |
| `pplx_kimi_k26_instant` | `moonshot/kimi-k2.6-instant` | Kimi K2.6 | pro | `available` | — |
| `pplx_kimi_k26_thinking` | `moonshot/kimi-k2.6-thinking` | Kimi K2.6 Thinking | pro | `available` | — |
| `pplx_grok45` | `x-ai/grok-4.5` | Grok 4.5 | pro | `available` | 2026-07-20T23:34:21.320430Z |
| `pplx_grok45_think` | `x-ai/grok-4.5-thinking` | Grok 4.5 Thinking | pro | `available` | 2026-07-20T23:34:25.402265Z |
| `pplx_nemotron3_super_think` | `nvidia/nemotron-3-super-thinking` | Nemotron 3 Super | pro | `available` | — |
| `pplx_nemotron3_ultra_think` | `nvidia/nemotron-3-ultra-thinking` | Nemotron 3 Ultra | pro | `available` | — |
| `pplx_gpt54` | `openai/gpt-5.4` | GPT-5.4 | pro | `unstable` | — |
| `pplx_gpt54_thinking` | `openai/gpt-5.4-thinking` | GPT-5.4 Thinking | pro | `unstable` | — |
| `pplx_gpt55_thinking` | `openai/gpt-5.5-thinking` | GPT-5.5 Thinking | max | `unstable` | — |
| `pplx_claude_o47` | `anthropic/claude-opus-4.7` | Claude Opus 4.7 | max | `unstable` | — |
| `pplx_claude_o47_think` | `anthropic/claude-opus-4.7-thinking` | Claude Opus 4.7 Thinking | max | `unstable` | — |
| `pplx_claude_s46` | `anthropic/claude-sonnet-4.6` | Claude Sonnet 4.6 | pro | `unstable` | — |
| `pplx_claude_s46_think` | `anthropic/claude-sonnet-4.6-thinking` | Claude Sonnet 4.6 Thinking | pro | `unstable` | — |
| `pplx_gpt4o` | `openai/gpt4o` | GPT-4o | unknown | `unknown` | — |
| `pplx_gpt41` | `openai/gpt41` | GPT-4.1 | unknown | `unknown` | — |
| `pplx_gpt5` | `openai/gpt5` | GPT-5 | unknown | `unknown` | — |
| `pplx_gpt5_thinking` | `openai/gpt5-thinking` | GPT-5 Thinking | unknown | `unknown` | — |
| `pplx_gpt51` | `openai/gpt51` | GPT-5.1 | unknown | `unknown` | — |
| `pplx_gpt51_thinking` | `openai/gpt51-thinking` | GPT-5.1 Thinking | unknown | `unknown` | — |
| `pplx_gpt51_low_thinking` | `openai/gpt51-low-thinking` | GPT-5.1 Low Thinking | unknown | `unknown` | — |
| `pplx_gpt5_mini` | `openai/gpt5-mini` | GPT-5 Mini | unknown | `unknown` | — |
| `pplx_gpt5_nano` | `openai/gpt5-nano` | GPT-5 Nano | unknown | `unknown` | — |
| `pplx_gpt5_pro` | `openai/gpt5-pro` | GPT-5 Pro | unknown | `unknown` | — |
| `pplx_gpt52` | `openai/gpt52` | GPT-5.2 | unknown | `unknown` | — |
| `pplx_gpt52_thinking` | `openai/gpt52-thinking` | GPT-5.2 Thinking | unknown | `unknown` | — |
| `pplx_gpt52_pro` | `openai/gpt52-pro` | GPT-5.2 Pro | unknown | `unknown` | — |
| `pplx_gpt55` | `openai/gpt55` | GPT-5.5 | unknown | `unknown` | — |
| `pplx_claude2` | `anthropic/claude2` | Claude Sonnet 4.0 | unknown | `unknown` | — |
| `pplx_claude37sonnetthinking` | `anthropic/claude37sonnetthinking` | Claude Sonnet 4.0 Thinking | unknown | `unknown` | — |
| `pplx_claude40sonnetthinking` | `anthropic/claude40sonnetthinking` | Claude Sonnet 4.0 Thinking | unknown | `unknown` | — |
| `pplx_gemini25pro` | `google/gemini25pro` | Gemini 2.5 Pro | unknown | `unknown` | — |
| `pplx_gemini30pro` | `google/gemini30pro` | Gemini 3 Pro | unknown | `unknown` | — |
| `pplx_gemini30flash` | `google/gemini30flash` | Gemini 3 Flash | unknown | `unknown` | — |
| `pplx_gemini30flash_high` | `google/gemini30flash-high` | Gemini 3 Flash Thinking | unknown | `unknown` | — |
| `pplx_gemini35flash` | `google/gemini35flash` | Gemini 3.5 Flash | unknown | `unknown` | — |
| `pplx_gemini35flash_medium` | `google/gemini35flash-medium` | Gemini 3.5 Flash Medium Thinking | unknown | `unknown` | — |
| `pplx_gemini35flash_high` | `google/gemini35flash-high` | Gemini 3.5 Flash Thinking | unknown | `unknown` | — |
| `pplx_grok` | `x-ai/grok` | Grok 3 Beta | unknown | `unknown` | — |
| `pplx_claude40opus` | `anthropic/claude40opus` | Claude Opus 4.0 | unknown | `unknown` | — |
| `pplx_claude40opusthinking` | `anthropic/claude40opusthinking` | Claude Opus 4.0 Thinking | unknown | `unknown` | — |
| `pplx_claude41opus` | `anthropic/claude41opus` | Claude Opus 4.1 | unknown | `unknown` | — |
| `pplx_claude41opusthinking` | `anthropic/claude41opusthinking` | Claude Opus 4.1 Thinking | unknown | `unknown` | — |
| `pplx_claude45opus` | `anthropic/claude45opus` | Claude Opus 4.5 | unknown | `unknown` | — |
| `pplx_claude45opusthinking` | `anthropic/claude45opusthinking` | Claude Opus 4.5 Thinking | unknown | `unknown` | — |
| `pplx_claude46opus` | `anthropic/claude46opus` | Claude Opus 4.6 | unknown | `unknown` | — |
| `pplx_claude46opusthinking` | `anthropic/claude46opusthinking` | Claude Opus 4.6 Thinking | unknown | `unknown` | — |
| `pplx_claude45sonnet` | `anthropic/claude45sonnet` | Claude Sonnet 4.5 | unknown | `unknown` | — |
| `pplx_claude45sonnetthinking` | `anthropic/claude45sonnetthinking` | Claude Sonnet 4.5 Thinking | unknown | `unknown` | — |
| `pplx_claude45haiku` | `anthropic/claude45haiku` | Claude Haiku 4.5 | unknown | `unknown` | — |
| `pplx_claude45haikuthinking` | `anthropic/claude45haikuthinking` | Claude Haiku 4.5 Thinking | unknown | `unknown` | — |
| `pplx_kimik2thinking` | `moonshot/kimik2thinking` | Kimi K2 | unknown | `unknown` | — |
| `pplx_kimik25thinking` | `moonshot/kimik25thinking` | Kimi K2.5 Thinking | unknown | `unknown` | — |
| `pplx_grok4` | `x-ai/grok4` | Grok 4 | unknown | `unknown` | — |
| `pplx_grok4nonthinking` | `x-ai/grok4nonthinking` | Grok 4 | unknown | `unknown` | — |
| `pplx_grok41reasoning` | `x-ai/grok41reasoning` | Grok 4.1 | unknown | `unknown` | — |
| `pplx_grok41nonreasoning` | `x-ai/grok41nonreasoning` | Grok 4.1 | unknown | `unknown` | — |
| `pplx_o4mini` | `openai/o4mini` | o4-mini | unknown | `unknown` | — |
| `pplx_o3pro` | `openai/o3pro` | o3-pro | unknown | `unknown` | — |
| `pplx_claude_o50` | `anthropic/claude-opus-5` | Claude Opus 5 | max | `unknown` | — |
| `pplx_claude_o50_think` | `anthropic/claude-opus-5-thinking` | Claude Opus 5 Thinking | max | `unknown` | — |

### Custom tool

`pplx_custom` accepts an arbitrary `custom:<identifier>` model and requires explicit risky-model acknowledgement.

<!-- END GENERATED MODEL CATALOG -->

**All tools support `source_focus`:** `web`, `academic`, `social`, `finance`, `all`
