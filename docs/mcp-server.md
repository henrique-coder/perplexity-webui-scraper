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

Tools marked `[UNSTABLE]` require `allow_unstable_model=true`. Tools marked `[DISABLED]` require `allow_disabled_model=true`. The generic `pplx_custom` tool accepts an internal identifier and is always treated as unstable.

<!-- BEGIN GENERATED MODEL CATALOG -->
### Stable tools

| Tool | Model ID | Name | Min. tier | Warning |
| --- | --- | --- | --- | --- |
| `pplx_best` | `perplexity/best` | Best | free | — |
| `pplx_deep_research` | `perplexity/deep-research` | Deep research | pro | — |
| `pplx_sonar` | `perplexity/sonar-2` | Sonar 2 | pro | — |
| `pplx_gpt56_terra` | `openai/gpt-5.6-terra` | GPT-5.6 Terra | pro | — |
| `pplx_gpt56_terra_thinking` | `openai/gpt-5.6-terra-thinking` | GPT-5.6 Terra Thinking | pro | — |
| `pplx_gpt56_sol` | `openai/gpt-5.6-sol` | GPT-5.6 Sol | max | — |
| `pplx_gpt56_sol_thinking` | `openai/gpt-5.6-sol-thinking` | GPT-5.6 Sol Thinking | max | — |
| `pplx_claude_s50` | `anthropic/claude-sonnet-5` | Claude Sonnet 5 | pro | — |
| `pplx_claude_s50_think` | `anthropic/claude-sonnet-5-thinking` | Claude Sonnet 5 Thinking | pro | — |
| `pplx_claude_o48` | `anthropic/claude-opus-4.8` | Claude Opus 4.8 | max | — |
| `pplx_claude_o48_think` | `anthropic/claude-opus-4.8-thinking` | Claude Opus 4.8 Thinking | max | — |
| `pplx_glm52` | `z-ai/glm-5.2` | GLM 5.2 | pro | — |
| `pplx_gemini31_pro_think_low` | `google/gemini-3.1-pro-thinking-low` | Gemini 3.1 Pro | pro | — |
| `pplx_gemini31_pro_think_high` | `google/gemini-3.1-pro-thinking-high` | Gemini 3.1 Pro Thinking | pro | — |
| `pplx_kimi_k26_instant` | `moonshot/kimi-k2.6-instant` | Kimi K2.6 | pro | — |
| `pplx_kimi_k26_thinking` | `moonshot/kimi-k2.6-thinking` | Kimi K2.6 Thinking | pro | — |
| `pplx_nemotron3_super_think` | `nvidia/nemotron-3-super-thinking` | Nemotron 3 Super | pro | — |
| `pplx_nemotron3_ultra_think` | `nvidia/nemotron-3-ultra-thinking` | Nemotron 3 Ultra | pro | — |

### Unstable tools

| Tool | Model ID | Name | Min. tier | Warning |
| --- | --- | --- | --- | --- |
| `pplx_gpt54` | `openai/gpt-5.4` | GPT-5.4 | pro | Unverified model from Perplexity's config endpoint; availability and behavior may change or stop without notice. |
| `pplx_gpt54_thinking` | `openai/gpt-5.4-thinking` | GPT-5.4 Thinking | pro | Unverified model from Perplexity's config endpoint; availability and behavior may change or stop without notice. |
| `pplx_gpt55_thinking` | `openai/gpt-5.5-thinking` | GPT-5.5 Thinking | max | Unverified model from Perplexity's config endpoint; availability and behavior may change or stop without notice. |
| `pplx_claude_o47` | `anthropic/claude-opus-4.7` | Claude Opus 4.7 | max | Unverified model from Perplexity's config endpoint; availability and behavior may change or stop without notice. |
| `pplx_claude_o47_think` | `anthropic/claude-opus-4.7-thinking` | Claude Opus 4.7 Thinking | max | Unverified model from Perplexity's config endpoint; availability and behavior may change or stop without notice. |
| `pplx_claude_s46` | `anthropic/claude-sonnet-4.6` | Claude Sonnet 4.6 | pro | Unverified model from Perplexity's config endpoint; availability and behavior may change or stop without notice. |
| `pplx_claude_s46_think` | `anthropic/claude-sonnet-4.6-thinking` | Claude Sonnet 4.6 Thinking | pro | Unverified model from Perplexity's config endpoint; availability and behavior may change or stop without notice. |

### Disabled tools

| Tool | Model ID | Name | Min. tier | Warning |
| --- | --- | --- | --- | --- |
| `pplx_gpt4o` | `openai/gpt4o` | GPT-4o | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_gpt41` | `openai/gpt41` | GPT-4.1 | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_gpt5` | `openai/gpt5` | GPT-5 | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_gpt5_thinking` | `openai/gpt5-thinking` | GPT-5 Thinking | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_gpt51` | `openai/gpt51` | GPT-5.1 | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_gpt51_thinking` | `openai/gpt51-thinking` | GPT-5.1 Thinking | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_gpt51_low_thinking` | `openai/gpt51-low-thinking` | GPT-5.1 Low Thinking | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_gpt5_mini` | `openai/gpt5-mini` | GPT-5 Mini | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_gpt5_nano` | `openai/gpt5-nano` | GPT-5 Nano | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_gpt5_pro` | `openai/gpt5-pro` | GPT-5 Pro | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_gpt52` | `openai/gpt52` | GPT-5.2 | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_gpt52_thinking` | `openai/gpt52-thinking` | GPT-5.2 Thinking | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_gpt52_pro` | `openai/gpt52-pro` | GPT-5.2 Pro | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_gpt55` | `openai/gpt55` | GPT-5.5 | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_claude2` | `anthropic/claude2` | Claude Sonnet 4.0 | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_claude37sonnetthinking` | `anthropic/claude37sonnetthinking` | Claude Sonnet 4.0 Thinking | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_claude40sonnetthinking` | `anthropic/claude40sonnetthinking` | Claude Sonnet 4.0 Thinking | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_gemini25pro` | `google/gemini25pro` | Gemini 2.5 Pro | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_gemini30pro` | `google/gemini30pro` | Gemini 3 Pro | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_gemini30flash` | `google/gemini30flash` | Gemini 3 Flash | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_gemini30flash_high` | `google/gemini30flash-high` | Gemini 3 Flash Thinking | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_gemini35flash` | `google/gemini35flash` | Gemini 3.5 Flash | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_gemini35flash_medium` | `google/gemini35flash-medium` | Gemini 3.5 Flash Medium Thinking | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_gemini35flash_high` | `google/gemini35flash-high` | Gemini 3.5 Flash Thinking | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_grok` | `x-ai/grok` | Grok 3 Beta | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_claude40opus` | `anthropic/claude40opus` | Claude Opus 4.0 | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_claude40opusthinking` | `anthropic/claude40opusthinking` | Claude Opus 4.0 Thinking | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_claude41opus` | `anthropic/claude41opus` | Claude Opus 4.1 | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_claude41opusthinking` | `anthropic/claude41opusthinking` | Claude Opus 4.1 Thinking | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_claude45opus` | `anthropic/claude45opus` | Claude Opus 4.5 | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_claude45opusthinking` | `anthropic/claude45opusthinking` | Claude Opus 4.5 Thinking | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_claude46opus` | `anthropic/claude46opus` | Claude Opus 4.6 | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_claude46opusthinking` | `anthropic/claude46opusthinking` | Claude Opus 4.6 Thinking | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_claude45sonnet` | `anthropic/claude45sonnet` | Claude Sonnet 4.5 | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_claude45sonnetthinking` | `anthropic/claude45sonnetthinking` | Claude Sonnet 4.5 Thinking | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_claude45haiku` | `anthropic/claude45haiku` | Claude Haiku 4.5 | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_claude45haikuthinking` | `anthropic/claude45haikuthinking` | Claude Haiku 4.5 Thinking | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_kimik2thinking` | `moonshot/kimik2thinking` | Kimi K2 | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_kimik25thinking` | `moonshot/kimik25thinking` | Kimi K2.5 Thinking | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_grok4` | `x-ai/grok4` | Grok 4 | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_grok4nonthinking` | `x-ai/grok4nonthinking` | Grok 4 | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_grok41reasoning` | `x-ai/grok41reasoning` | Grok 4.1 | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_grok41nonreasoning` | `x-ai/grok41nonreasoning` | Grok 4.1 | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_o4mini` | `openai/o4mini` | o4-mini | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |
| `pplx_o3pro` | `openai/o3pro` | o3-pro | unknown | Disabled pending compatibility testing; the backend identifier is retained for historical reference and may fail even with explicit override. |

### Custom tool

`pplx_custom` accepts an arbitrary `custom:<identifier>` model and requires explicit unstable-model acknowledgement.

<!-- END GENERATED MODEL CATALOG -->

**All tools support `source_focus`:** `web`, `academic`, `social`, `finance`, `all`
