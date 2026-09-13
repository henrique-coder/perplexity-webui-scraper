# MCP Server (Model Context Protocol)

The MCP server exposes each registered model as a separate tool. Enable only the tools your MCP client needs.

## Configuration

Add one of the following entries to your MCP client configuration. `uvx` creates an isolated Python environment for the server.

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

Tools marked `[AVAILABLE]` can be called normally. `[UNKNOWN]` and `[UNAVAILABLE]` tools require `allow_risky_model=true`. Official listing is exposed separately as `is_official`; it does not imply that a tool has been tested. The generic `pplx_custom` tool accepts an internal identifier, which always starts with `unknown` status and `is_official=false`.

<!-- BEGIN GENERATED MODEL CATALOG -->
### Status reference

| Status | Meaning | Runtime behavior |
| --- | --- | --- |
| `available` | Confirmed to work normally. | Normal use; the local minimum-tier check applies. |
| `unknown` | Current availability has not been confirmed. | Requires `allow_risky_model`; this is the default for unverified entries. |
| `unavailable` | Confirmed not to work with the current backend. | Requires `allow_risky_model`; retained for history and expected to fail. |

### Model tools

| Tool | Model ID | Name | Official | Min. tier | Status | Last tested (UTC) |
| --- | --- | --- | --- | --- | --- | --- |
| `pplx_best` | `perplexity/best` | Best | `true` | free | `available` | 2026-09-13T19:51:19.057910Z |
| `pplx_deep_research` | `perplexity/deep-research` | Deep research | `true` | pro | `available` | 2026-09-13T19:50:53.931937Z |
| `pplx_gpt56_terra` | `openai/gpt-5.6-terra` | GPT-5.6 Terra | `true` | pro | `available` | 2026-09-13T19:37:29.434502Z |
| `pplx_gpt56_terra_thinking` | `openai/gpt-5.6-terra-thinking` | GPT-5.6 Terra Thinking | `true` | pro | `available` | 2026-09-13T19:37:39.344800Z |
| `pplx_gpt56_sol` | `openai/gpt-5.6-sol` | GPT-5.6 Sol | `true` | max | `available` | 2026-09-13T19:37:49.191163Z |
| `pplx_gpt56_sol_thinking` | `openai/gpt-5.6-sol-thinking` | GPT-5.6 Sol Thinking | `true` | max | `available` | 2026-09-13T19:37:59.368027Z |
| `pplx_gemini38_flash` | `google/gemini-3.8-flash` | Gemini 3.8 Flash | `true` | pro | `available` | 2026-09-13T19:38:09.870735Z |
| `pplx_gemini38_flash_think` | `google/gemini-3.8-flash-thinking` | Gemini 3.8 Flash Thinking | `true` | pro | `available` | 2026-09-13T19:38:14.544356Z |
| `pplx_claude_s50` | `anthropic/claude-sonnet-5` | Claude Sonnet 5 | `true` | pro | `available` | 2026-09-13T19:38:24.302138Z |
| `pplx_claude_s50_think` | `anthropic/claude-sonnet-5-thinking` | Claude Sonnet 5 Thinking | `true` | pro | `available` | 2026-09-13T19:38:34.118565Z |
| `pplx_claude_o50` | `anthropic/claude-opus-5` | Claude Opus 5 | `true` | max | `available` | 2026-09-13T19:38:43.900501Z |
| `pplx_claude_o50_think` | `anthropic/claude-opus-5-thinking` | Claude Opus 5 Thinking | `true` | max | `available` | 2026-09-13T19:38:53.667825Z |
| `pplx_kimi_k3_thinking` | `moonshot/kimi-k3-thinking` | Kimi K3 Thinking | `true` | pro | `available` | 2026-09-13T19:39:03.507218Z |
| `pplx_glm53` | `z-ai/glm-5.3` | GLM 5.3 Thinking | `true` | pro | `available` | 2026-09-13T19:39:13.397094Z |
| `pplx_grok46` | `x-ai/grok-4.6` | Grok 4.6 | `true` | pro | `available` | 2026-09-13T19:39:23.139648Z |
| `pplx_grok46_think` | `x-ai/grok-4.6-thinking` | Grok 4.6 Thinking | `true` | pro | `available` | 2026-09-13T19:39:32.894208Z |
| `pplx_nemotron3_ultra_think` | `nvidia/nemotron-3-ultra-thinking` | Nemotron 3 Ultra | `true` | pro | `available` | 2026-09-13T19:39:42.666584Z |
| `pplx_gemini37_flash` | `google/gemini-3.7-flash` | Gemini 3.7 Flash | `false` | pro | `available` | 2026-09-13T19:39:52.446292Z |
| `pplx_gemini37_flash_think` | `google/gemini-3.7-flash-thinking` | Gemini 3.7 Flash Thinking | `false` | pro | `available` | 2026-09-13T19:40:02.285061Z |
| `pplx_sonar` | `perplexity/sonar-2` | Sonar 2 | `false` | pro | `available` | 2026-09-13T19:40:12.067771Z |
| `pplx_glm52` | `z-ai/glm-5.2` | GLM 5.2 Thinking | `false` | pro | `available` | 2026-09-13T19:40:21.918449Z |
| `pplx_gemini31_pro_think_high` | `google/gemini-3.1-pro-thinking-high` | Gemini 3.1 Pro Thinking | `false` | pro | `available` | 2026-09-13T19:40:33.018069Z |
| `pplx_grok45` | `x-ai/grok-4.5` | Grok 4.5 | `false` | pro | `available` | 2026-09-13T19:40:42.851821Z |
| `pplx_grok45_think` | `x-ai/grok-4.5-thinking` | Grok 4.5 Thinking | `false` | pro | `available` | 2026-09-13T19:40:52.653495Z |
| `pplx_claude_o48` | `anthropic/claude-opus-4.8` | Claude Opus 4.8 | `false` | max | `available` | 2026-09-13T19:41:02.443376Z |
| `pplx_claude_o48_think` | `anthropic/claude-opus-4.8-thinking` | Claude Opus 4.8 Thinking | `false` | max | `available` | 2026-09-13T19:41:12.230861Z |
| `pplx_gemini31_pro_think_low` | `google/gemini-3.1-pro-thinking-low` | Gemini 3.1 Pro | `false` | pro | `available` | 2026-09-13T19:41:21.996001Z |
| `pplx_kimi_k26_instant` | `moonshot/kimi-k2.6-instant` | Kimi K2.6 | `false` | pro | `available` | 2026-09-13T19:41:32.172857Z |
| `pplx_kimi_k26_thinking` | `moonshot/kimi-k2.6-thinking` | Kimi K2.6 Thinking | `false` | pro | `available` | 2026-09-13T19:41:41.981232Z |
| `pplx_nemotron3_super_think` | `nvidia/nemotron-3-super-thinking` | Nemotron 3 Super | `false` | pro | `available` | 2026-09-13T19:41:51.762788Z |
| `pplx_gpt54` | `openai/gpt-5.4` | GPT-5.4 | `false` | pro | `available` | 2026-09-13T19:42:01.558299Z |
| `pplx_gpt54_thinking` | `openai/gpt-5.4-thinking` | GPT-5.4 Thinking | `false` | pro | `available` | 2026-09-13T19:42:11.509710Z |
| `pplx_gpt55_thinking` | `openai/gpt-5.5-thinking` | GPT-5.5 Thinking | `false` | max | `available` | 2026-09-13T19:42:21.276041Z |
| `pplx_claude_o47` | `anthropic/claude-opus-4.7` | Claude Opus 4.7 | `false` | max | `available` | 2026-09-13T19:42:31.150156Z |
| `pplx_claude_o47_think` | `anthropic/claude-opus-4.7-thinking` | Claude Opus 4.7 Thinking | `false` | max | `available` | 2026-09-13T19:42:40.973299Z |
| `pplx_claude_s46` | `anthropic/claude-sonnet-4.6` | Claude Sonnet 4.6 | `false` | pro | `available` | 2026-09-13T19:42:50.705736Z |
| `pplx_claude_s46_think` | `anthropic/claude-sonnet-4.6-thinking` | Claude Sonnet 4.6 Thinking | `false` | pro | `available` | 2026-09-13T19:43:00.501355Z |
| `pplx_gpt4o` | `openai/gpt4o` | GPT-4o | `false` | unknown | `available` | 2026-09-13T19:43:10.313839Z |
| `pplx_gpt41` | `openai/gpt41` | GPT-4.1 | `false` | unknown | `available` | 2026-09-13T19:43:20.087766Z |
| `pplx_gpt5` | `openai/gpt5` | GPT-5 | `false` | unknown | `available` | 2026-09-13T19:43:29.980505Z |
| `pplx_gpt5_thinking` | `openai/gpt5-thinking` | GPT-5 Thinking | `false` | unknown | `available` | 2026-09-13T19:43:39.777875Z |
| `pplx_gpt51` | `openai/gpt51` | GPT-5.1 | `false` | unknown | `available` | 2026-09-13T19:43:49.654946Z |
| `pplx_gpt51_thinking` | `openai/gpt51-thinking` | GPT-5.1 Thinking | `false` | unknown | `available` | 2026-09-13T19:43:59.444670Z |
| `pplx_gpt51_low_thinking` | `openai/gpt51-low-thinking` | GPT-5.1 Low Thinking | `false` | unknown | `available` | 2026-09-13T19:44:09.236517Z |
| `pplx_gpt5_mini` | `openai/gpt5-mini` | GPT-5 Mini | `false` | unknown | `available` | 2026-09-13T19:44:19.057906Z |
| `pplx_gpt5_nano` | `openai/gpt5-nano` | GPT-5 Nano | `false` | unknown | `available` | 2026-09-13T19:44:28.963979Z |
| `pplx_gpt5_pro` | `openai/gpt5-pro` | GPT-5 Pro | `false` | unknown | `available` | 2026-09-13T19:44:38.732226Z |
| `pplx_gpt52` | `openai/gpt52` | GPT-5.2 | `false` | unknown | `available` | 2026-09-13T19:44:48.500963Z |
| `pplx_gpt52_thinking` | `openai/gpt52-thinking` | GPT-5.2 Thinking | `false` | unknown | `available` | 2026-09-13T19:44:58.359725Z |
| `pplx_gpt52_pro` | `openai/gpt52-pro` | GPT-5.2 Pro | `false` | unknown | `available` | 2026-09-13T19:45:08.073759Z |
| `pplx_gpt55` | `openai/gpt55` | GPT-5.5 | `false` | unknown | `available` | 2026-09-13T19:45:18.149763Z |
| `pplx_claude2` | `anthropic/claude2` | Claude Sonnet 4.0 | `false` | unknown | `available` | 2026-09-13T19:45:28.333859Z |
| `pplx_claude37sonnetthinking` | `anthropic/claude37sonnetthinking` | Claude Sonnet 4.0 Thinking | `false` | unknown | `available` | 2026-09-13T19:45:38.151693Z |
| `pplx_claude40sonnetthinking` | `anthropic/claude40sonnetthinking` | Claude Sonnet 4.0 Thinking | `false` | unknown | `available` | 2026-09-13T19:45:47.891928Z |
| `pplx_gemini25pro` | `google/gemini25pro` | Gemini 2.5 Pro | `false` | unknown | `available` | 2026-09-13T19:45:57.709752Z |
| `pplx_gemini30pro` | `google/gemini30pro` | Gemini 3 Pro | `false` | unknown | `available` | 2026-09-13T19:46:07.544899Z |
| `pplx_gemini30flash` | `google/gemini30flash` | Gemini 3 Flash | `false` | unknown | `available` | 2026-09-13T19:46:17.361196Z |
| `pplx_gemini30flash_high` | `google/gemini30flash-high` | Gemini 3 Flash Thinking | `false` | unknown | `available` | 2026-09-13T19:46:27.339685Z |
| `pplx_gemini35flash` | `google/gemini35flash` | Gemini 3.5 Flash | `false` | unknown | `available` | 2026-09-13T19:46:37.129083Z |
| `pplx_gemini35flash_medium` | `google/gemini35flash-medium` | Gemini 3.5 Flash Medium Thinking | `false` | unknown | `available` | 2026-09-13T19:46:47.141748Z |
| `pplx_gemini35flash_high` | `google/gemini35flash-high` | Gemini 3.5 Flash Thinking | `false` | unknown | `available` | 2026-09-13T19:46:57.006982Z |
| `pplx_grok` | `x-ai/grok` | Grok 3 Beta | `false` | unknown | `available` | 2026-09-13T19:47:06.905199Z |
| `pplx_claude40opus` | `anthropic/claude40opus` | Claude Opus 4.0 | `false` | unknown | `available` | 2026-09-13T19:47:16.854493Z |
| `pplx_claude40opusthinking` | `anthropic/claude40opusthinking` | Claude Opus 4.0 Thinking | `false` | unknown | `available` | 2026-09-13T19:47:26.721724Z |
| `pplx_claude41opus` | `anthropic/claude41opus` | Claude Opus 4.1 | `false` | unknown | `available` | 2026-09-13T19:47:37.188095Z |
| `pplx_claude41opusthinking` | `anthropic/claude41opusthinking` | Claude Opus 4.1 Thinking | `false` | unknown | `available` | 2026-09-13T19:47:47.004911Z |
| `pplx_claude45opus` | `anthropic/claude45opus` | Claude Opus 4.5 | `false` | unknown | `available` | 2026-09-13T19:47:56.808023Z |
| `pplx_claude45opusthinking` | `anthropic/claude45opusthinking` | Claude Opus 4.5 Thinking | `false` | unknown | `available` | 2026-09-13T19:48:06.573757Z |
| `pplx_claude46opus` | `anthropic/claude46opus` | Claude Opus 4.6 | `false` | unknown | `available` | 2026-09-13T19:48:16.371324Z |
| `pplx_claude46opusthinking` | `anthropic/claude46opusthinking` | Claude Opus 4.6 Thinking | `false` | unknown | `available` | 2026-09-13T19:48:26.148309Z |
| `pplx_claude45sonnet` | `anthropic/claude45sonnet` | Claude Sonnet 4.5 | `false` | unknown | `available` | 2026-09-13T19:48:35.875010Z |
| `pplx_claude45sonnetthinking` | `anthropic/claude45sonnetthinking` | Claude Sonnet 4.5 Thinking | `false` | unknown | `available` | 2026-09-13T19:48:45.706339Z |
| `pplx_claude45haiku` | `anthropic/claude45haiku` | Claude Haiku 4.5 | `false` | unknown | `unavailable` | 2026-09-13T19:48:55.515118Z |
| `pplx_claude45haikuthinking` | `anthropic/claude45haikuthinking` | Claude Haiku 4.5 Thinking | `false` | unknown | `unavailable` | 2026-09-13T19:48:58.037304Z |
| `pplx_kimik2thinking` | `moonshot/kimik2thinking` | Kimi K2 | `false` | unknown | `available` | 2026-09-13T19:49:02.031019Z |
| `pplx_kimik25thinking` | `moonshot/kimik25thinking` | Kimi K2.5 Thinking | `false` | unknown | `available` | 2026-09-13T19:49:13.362379Z |
| `pplx_grok4` | `x-ai/grok4` | Grok 4 | `false` | unknown | `available` | 2026-09-13T19:49:23.571782Z |
| `pplx_grok4nonthinking` | `x-ai/grok4nonthinking` | Grok 4 | `false` | unknown | `available` | 2026-09-13T19:49:33.430334Z |
| `pplx_grok41reasoning` | `x-ai/grok41reasoning` | Grok 4.1 | `false` | unknown | `available` | 2026-09-13T19:49:43.651497Z |
| `pplx_grok41nonreasoning` | `x-ai/grok41nonreasoning` | Grok 4.1 | `false` | unknown | `available` | 2026-09-13T19:49:53.457459Z |
| `pplx_o4mini` | `openai/o4mini` | o4-mini | `false` | unknown | `available` | 2026-09-13T19:50:09.734470Z |
| `pplx_o3pro` | `openai/o3pro` | o3-pro | `false` | unknown | `available` | 2026-09-13T19:50:19.657101Z |

### Custom tool

`pplx_custom` accepts an arbitrary `custom:<identifier>` model and requires explicit risky-model acknowledgement.

<!-- END GENERATED MODEL CATALOG -->

**All tools support `source_focus`:** `web`, `academic`, `social`, `finance`, `all`
