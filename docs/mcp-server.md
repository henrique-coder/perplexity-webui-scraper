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
| `pplx_best` | `perplexity/best` | Best | `true` | free | `available` | 2026-09-13T23:12:46.982064Z |
| `pplx_deep_research` | `perplexity/deep-research` | Deep research | `true` | pro | `available` | 2026-09-13T23:12:51.081351Z |
| `pplx_gpt56_terra` | `openai/gpt-5.6-terra` | GPT-5.6 Terra | `true` | pro | `available` | 2026-09-13T23:12:54.800629Z |
| `pplx_gpt56_terra_thinking` | `openai/gpt-5.6-terra-thinking` | GPT-5.6 Terra Thinking | `true` | pro | `available` | 2026-09-13T23:12:59.855822Z |
| `pplx_gpt56_sol` | `openai/gpt-5.6-sol` | GPT-5.6 Sol | `true` | max | `available` | 2026-09-13T23:13:03.654886Z |
| `pplx_gpt56_sol_thinking` | `openai/gpt-5.6-sol-thinking` | GPT-5.6 Sol Thinking | `true` | max | `available` | 2026-09-13T23:13:08.031580Z |
| `pplx_gemini38_flash` | `google/gemini-3.8-flash` | Gemini 3.8 Flash | `true` | pro | `available` | 2026-09-13T23:13:11.992982Z |
| `pplx_gemini38_flash_think` | `google/gemini-3.8-flash-thinking` | Gemini 3.8 Flash Thinking | `true` | pro | `available` | 2026-09-13T23:13:19.382663Z |
| `pplx_claude_s50` | `anthropic/claude-sonnet-5` | Claude Sonnet 5 | `true` | pro | `available` | 2026-09-13T23:13:23.003285Z |
| `pplx_claude_s50_think` | `anthropic/claude-sonnet-5-thinking` | Claude Sonnet 5 Thinking | `true` | pro | `available` | 2026-09-13T23:13:27.466606Z |
| `pplx_claude_o50` | `anthropic/claude-opus-5` | Claude Opus 5 | `true` | max | `available` | 2026-09-13T23:13:31.135570Z |
| `pplx_claude_o50_think` | `anthropic/claude-opus-5-thinking` | Claude Opus 5 Thinking | `true` | max | `available` | 2026-09-13T23:13:34.923562Z |
| `pplx_kimi_k3_thinking` | `moonshot/kimi-k3-thinking` | Kimi K3 Thinking | `true` | pro | `available` | 2026-09-13T23:13:39.295326Z |
| `pplx_glm53` | `z-ai/glm-5.3` | GLM 5.3 Thinking | `true` | pro | `available` | 2026-09-13T23:13:43.154248Z |
| `pplx_grok46` | `x-ai/grok-4.6` | Grok 4.6 | `true` | pro | `available` | 2026-09-13T23:13:47.724677Z |
| `pplx_grok46_think` | `x-ai/grok-4.6-thinking` | Grok 4.6 Thinking | `true` | pro | `available` | 2026-09-13T23:13:51.201091Z |
| `pplx_nemotron3_ultra_think` | `nvidia/nemotron-3-ultra-thinking` | Nemotron 3 Ultra | `true` | pro | `available` | 2026-09-13T23:13:55.789723Z |
| `pplx_gemini37_flash` | `google/gemini-3.7-flash` | Gemini 3.7 Flash | `false` | pro | `available` | 2026-09-13T23:13:59.271156Z |
| `pplx_gemini37_flash_think` | `google/gemini-3.7-flash-thinking` | Gemini 3.7 Flash Thinking | `false` | pro | `available` | 2026-09-13T23:14:03.414284Z |
| `pplx_sonar` | `perplexity/sonar-2` | Sonar 2 | `false` | pro | `available` | 2026-09-13T23:14:07.384667Z |
| `pplx_glm52` | `z-ai/glm-5.2` | GLM 5.2 Thinking | `false` | pro | `available` | 2026-09-13T23:14:11.455015Z |
| `pplx_gemini31_pro_think_high` | `google/gemini-3.1-pro-thinking-high` | Gemini 3.1 Pro Thinking | `false` | pro | `available` | 2026-09-13T23:14:15.526678Z |
| `pplx_grok45` | `x-ai/grok-4.5` | Grok 4.5 | `false` | pro | `available` | 2026-09-13T23:14:19.090362Z |
| `pplx_grok45_think` | `x-ai/grok-4.5-thinking` | Grok 4.5 Thinking | `false` | pro | `available` | 2026-09-13T23:14:23.385082Z |
| `pplx_claude_o48` | `anthropic/claude-opus-4.8` | Claude Opus 4.8 | `false` | max | `available` | 2026-09-13T23:14:27.434038Z |
| `pplx_claude_o48_think` | `anthropic/claude-opus-4.8-thinking` | Claude Opus 4.8 Thinking | `false` | max | `available` | 2026-09-13T23:14:34.434827Z |
| `pplx_gemini31_pro_think_low` | `google/gemini-3.1-pro-thinking-low` | Gemini 3.1 Pro | `false` | pro | `available` | 2026-09-13T23:14:37.828406Z |
| `pplx_kimi_k26_instant` | `moonshot/kimi-k2.6-instant` | Kimi K2.6 | `false` | pro | `available` | 2026-09-13T23:14:42.640538Z |
| `pplx_kimi_k26_thinking` | `moonshot/kimi-k2.6-thinking` | Kimi K2.6 Thinking | `false` | pro | `available` | 2026-09-13T23:14:47.259175Z |
| `pplx_nemotron3_super_think` | `nvidia/nemotron-3-super-thinking` | Nemotron 3 Super | `false` | pro | `available` | 2026-09-13T23:14:51.249396Z |
| `pplx_gpt54` | `openai/gpt-5.4` | GPT-5.4 | `false` | pro | `available` | 2026-09-13T23:14:55.227656Z |
| `pplx_gpt54_thinking` | `openai/gpt-5.4-thinking` | GPT-5.4 Thinking | `false` | pro | `available` | 2026-09-13T23:14:59.198145Z |
| `pplx_gpt55_thinking` | `openai/gpt-5.5-thinking` | GPT-5.5 Thinking | `false` | max | `available` | 2026-09-13T23:15:03.401542Z |
| `pplx_claude_o47` | `anthropic/claude-opus-4.7` | Claude Opus 4.7 | `false` | max | `available` | 2026-09-13T23:15:06.850877Z |
| `pplx_claude_o47_think` | `anthropic/claude-opus-4.7-thinking` | Claude Opus 4.7 Thinking | `false` | max | `available` | 2026-09-13T23:15:10.780893Z |
| `pplx_claude_s46` | `anthropic/claude-sonnet-4.6` | Claude Sonnet 4.6 | `false` | pro | `available` | 2026-09-13T23:15:14.845654Z |
| `pplx_claude_s46_think` | `anthropic/claude-sonnet-4.6-thinking` | Claude Sonnet 4.6 Thinking | `false` | pro | `available` | 2026-09-13T23:15:19.994628Z |
| `pplx_gpt4o` | `openai/gpt4o` | GPT-4o | `false` | unknown | `available` | 2026-09-13T23:15:24.125802Z |
| `pplx_gpt41` | `openai/gpt41` | GPT-4.1 | `false` | unknown | `available` | 2026-09-13T23:15:28.101680Z |
| `pplx_gpt5` | `openai/gpt5` | GPT-5 | `false` | unknown | `available` | 2026-09-13T23:15:32.360214Z |
| `pplx_gpt5_thinking` | `openai/gpt5-thinking` | GPT-5 Thinking | `false` | unknown | `available` | 2026-09-13T23:15:36.452512Z |
| `pplx_gpt51` | `openai/gpt51` | GPT-5.1 | `false` | unknown | `available` | 2026-09-13T23:15:40.309049Z |
| `pplx_gpt51_thinking` | `openai/gpt51-thinking` | GPT-5.1 Thinking | `false` | unknown | `available` | 2026-09-13T23:15:44.360139Z |
| `pplx_gpt51_low_thinking` | `openai/gpt51-low-thinking` | GPT-5.1 Low Thinking | `false` | unknown | `available` | 2026-09-13T23:15:48.287810Z |
| `pplx_gpt5_mini` | `openai/gpt5-mini` | GPT-5 Mini | `false` | unknown | `available` | 2026-09-13T23:15:52.567525Z |
| `pplx_gpt5_nano` | `openai/gpt5-nano` | GPT-5 Nano | `false` | unknown | `available` | 2026-09-13T23:15:56.799784Z |
| `pplx_gpt5_pro` | `openai/gpt5-pro` | GPT-5 Pro | `false` | unknown | `available` | 2026-09-13T23:16:01.068556Z |
| `pplx_gpt52` | `openai/gpt52` | GPT-5.2 | `false` | unknown | `available` | 2026-09-13T23:16:04.887935Z |
| `pplx_gpt52_thinking` | `openai/gpt52-thinking` | GPT-5.2 Thinking | `false` | unknown | `available` | 2026-09-13T23:16:11.737370Z |
| `pplx_gpt52_pro` | `openai/gpt52-pro` | GPT-5.2 Pro | `false` | unknown | `available` | 2026-09-13T23:16:16.305460Z |
| `pplx_gpt55` | `openai/gpt55` | GPT-5.5 | `false` | unknown | `available` | 2026-09-13T23:16:20.110289Z |
| `pplx_claude2` | `anthropic/claude2` | Claude Sonnet 4.0 | `false` | unknown | `available` | 2026-09-13T23:16:23.835408Z |
| `pplx_claude37sonnetthinking` | `anthropic/claude37sonnetthinking` | Claude Sonnet 4.0 Thinking | `false` | unknown | `available` | 2026-09-13T23:16:28.168102Z |
| `pplx_claude40sonnetthinking` | `anthropic/claude40sonnetthinking` | Claude Sonnet 4.0 Thinking | `false` | unknown | `available` | 2026-09-13T23:16:32.348336Z |
| `pplx_gemini25pro` | `google/gemini25pro` | Gemini 2.5 Pro | `false` | unknown | `available` | 2026-09-13T23:16:36.267089Z |
| `pplx_gemini30pro` | `google/gemini30pro` | Gemini 3 Pro | `false` | unknown | `available` | 2026-09-13T23:16:40.189797Z |
| `pplx_gemini30flash` | `google/gemini30flash` | Gemini 3 Flash | `false` | unknown | `available` | 2026-09-13T23:16:44.593098Z |
| `pplx_gemini30flash_high` | `google/gemini30flash-high` | Gemini 3 Flash Thinking | `false` | unknown | `available` | 2026-09-13T23:16:48.598801Z |
| `pplx_gemini35flash` | `google/gemini35flash` | Gemini 3.5 Flash | `false` | unknown | `available` | 2026-09-13T23:16:52.628156Z |
| `pplx_gemini35flash_medium` | `google/gemini35flash-medium` | Gemini 3.5 Flash Medium Thinking | `false` | unknown | `available` | 2026-09-13T23:16:56.700528Z |
| `pplx_gemini35flash_high` | `google/gemini35flash-high` | Gemini 3.5 Flash Thinking | `false` | unknown | `available` | 2026-09-13T23:17:00.687539Z |
| `pplx_grok` | `x-ai/grok` | Grok 3 Beta | `false` | unknown | `available` | 2026-09-13T23:17:04.535073Z |
| `pplx_claude40opus` | `anthropic/claude40opus` | Claude Opus 4.0 | `false` | unknown | `available` | 2026-09-13T23:17:08.771164Z |
| `pplx_claude40opusthinking` | `anthropic/claude40opusthinking` | Claude Opus 4.0 Thinking | `false` | unknown | `available` | 2026-09-13T23:17:12.509100Z |
| `pplx_claude41opus` | `anthropic/claude41opus` | Claude Opus 4.1 | `false` | unknown | `available` | 2026-09-13T23:17:16.178303Z |
| `pplx_claude41opusthinking` | `anthropic/claude41opusthinking` | Claude Opus 4.1 Thinking | `false` | unknown | `available` | 2026-09-13T23:17:20.159256Z |
| `pplx_claude45opus` | `anthropic/claude45opus` | Claude Opus 4.5 | `false` | unknown | `available` | 2026-09-13T23:17:24.494875Z |
| `pplx_claude45opusthinking` | `anthropic/claude45opusthinking` | Claude Opus 4.5 Thinking | `false` | unknown | `available` | 2026-09-13T23:17:28.400043Z |
| `pplx_claude46opus` | `anthropic/claude46opus` | Claude Opus 4.6 | `false` | unknown | `available` | 2026-09-13T23:17:32.157453Z |
| `pplx_claude46opusthinking` | `anthropic/claude46opusthinking` | Claude Opus 4.6 Thinking | `false` | unknown | `available` | 2026-09-13T23:17:36.648850Z |
| `pplx_claude45sonnet` | `anthropic/claude45sonnet` | Claude Sonnet 4.5 | `false` | unknown | `available` | 2026-09-13T23:17:40.515816Z |
| `pplx_claude45sonnetthinking` | `anthropic/claude45sonnetthinking` | Claude Sonnet 4.5 Thinking | `false` | unknown | `available` | 2026-09-13T23:17:44.569185Z |
| `pplx_claude45haiku` | `anthropic/claude45haiku` | Claude Haiku 4.5 | `false` | unknown | `unavailable` | 2026-09-13T23:17:48.684196Z |
| `pplx_claude45haikuthinking` | `anthropic/claude45haikuthinking` | Claude Haiku 4.5 Thinking | `false` | unknown | `unavailable` | 2026-09-13T23:17:51.371840Z |
| `pplx_kimik2thinking` | `moonshot/kimik2thinking` | Kimi K2 | `false` | unknown | `available` | 2026-09-13T23:17:55.379339Z |
| `pplx_kimik25thinking` | `moonshot/kimik25thinking` | Kimi K2.5 Thinking | `false` | unknown | `available` | 2026-09-13T23:18:01.032604Z |
| `pplx_grok4` | `x-ai/grok4` | Grok 4 | `false` | unknown | `available` | 2026-09-13T23:18:05.567750Z |
| `pplx_grok4nonthinking` | `x-ai/grok4nonthinking` | Grok 4 | `false` | unknown | `available` | 2026-09-13T23:18:09.535694Z |
| `pplx_grok41reasoning` | `x-ai/grok41reasoning` | Grok 4.1 | `false` | unknown | `available` | 2026-09-13T23:18:13.434016Z |
| `pplx_grok41nonreasoning` | `x-ai/grok41nonreasoning` | Grok 4.1 | `false` | unknown | `available` | 2026-09-13T23:18:17.917424Z |
| `pplx_o4mini` | `openai/o4mini` | o4-mini | `false` | unknown | `available` | 2026-09-13T23:18:21.843033Z |
| `pplx_o3pro` | `openai/o3pro` | o3-pro | `false` | unknown | `available` | 2026-09-13T23:18:26.139147Z |

### Custom tool

`pplx_custom` accepts an arbitrary `custom:<identifier>` model and requires explicit risky-model acknowledgement.

<!-- END GENERATED MODEL CATALOG -->

**All tools support `source_focus`:** `web`, `academic`, `social`, `finance`, `all`
