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
| `pplx_best` | `perplexity/best` | Best | `true` | free | `available` | 2026-09-03T11:22:43.678013Z |
| `pplx_deep_research` | `perplexity/deep-research` | Deep research | `true` | pro | `available` | 2026-09-03T11:22:48.144988Z |
| `pplx_sonar` | `perplexity/sonar-2` | Sonar 2 | `true` | pro | `available` | 2026-09-03T11:22:53.057021Z |
| `pplx_gpt56_terra` | `openai/gpt-5.6-terra` | GPT-5.6 Terra | `true` | pro | `available` | 2026-09-03T11:23:01.577429Z |
| `pplx_gpt56_terra_thinking` | `openai/gpt-5.6-terra-thinking` | GPT-5.6 Terra Thinking | `true` | pro | `available` | 2026-09-03T11:23:06.785982Z |
| `pplx_gpt56_sol` | `openai/gpt-5.6-sol` | GPT-5.6 Sol | `true` | max | `available` | 2026-09-03T11:23:12.792318Z |
| `pplx_gpt56_sol_thinking` | `openai/gpt-5.6-sol-thinking` | GPT-5.6 Sol Thinking | `true` | max | `available` | 2026-09-03T11:23:22.916886Z |
| `pplx_gemini37_flash` | `google/gemini-3.7-flash` | Gemini 3.7 Flash | `true` | pro | `available` | 2026-09-03T11:23:27.912685Z |
| `pplx_gemini37_flash_think` | `google/gemini-3.7-flash-thinking` | Gemini 3.7 Flash Thinking | `true` | pro | `available` | 2026-09-03T11:23:36.095351Z |
| `pplx_claude_s50` | `anthropic/claude-sonnet-5` | Claude Sonnet 5 | `true` | pro | `available` | 2026-09-03T11:23:43.226216Z |
| `pplx_claude_s50_think` | `anthropic/claude-sonnet-5-thinking` | Claude Sonnet 5 Thinking | `true` | pro | `available` | 2026-09-03T11:23:48.300702Z |
| `pplx_claude_o50` | `anthropic/claude-opus-5` | Claude Opus 5 | `true` | max | `available` | 2026-09-03T11:23:54.080456Z |
| `pplx_claude_o50_think` | `anthropic/claude-opus-5-thinking` | Claude Opus 5 Thinking | `true` | max | `available` | 2026-09-03T11:23:59.927595Z |
| `pplx_kimi_k3_thinking` | `moonshot/kimi-k3-thinking` | Kimi K3 Thinking | `true` | pro | `available` | 2026-09-03T11:24:05.152887Z |
| `pplx_glm53` | `z-ai/glm-5.3` | GLM 5.3 Thinking | `true` | pro | `available` | 2026-09-03T11:24:10.277289Z |
| `pplx_grok46` | `x-ai/grok-4.6` | Grok 4.6 | `true` | pro | `available` | 2026-09-03T11:24:18.025718Z |
| `pplx_grok46_think` | `x-ai/grok-4.6-thinking` | Grok 4.6 Thinking | `true` | pro | `available` | 2026-09-03T11:24:22.485161Z |
| `pplx_nemotron3_ultra_think` | `nvidia/nemotron-3-ultra-thinking` | Nemotron 3 Ultra | `true` | pro | `available` | 2026-09-03T11:24:27.794997Z |
| `pplx_glm52` | `z-ai/glm-5.2` | GLM 5.2 Thinking | `false` | pro | `available` | 2026-09-03T11:24:33.746485Z |
| `pplx_gemini31_pro_think_high` | `google/gemini-3.1-pro-thinking-high` | Gemini 3.1 Pro Thinking | `false` | pro | `available` | 2026-09-03T11:24:38.686210Z |
| `pplx_grok45` | `x-ai/grok-4.5` | Grok 4.5 | `false` | pro | `available` | 2026-09-03T11:24:46.743380Z |
| `pplx_grok45_think` | `x-ai/grok-4.5-thinking` | Grok 4.5 Thinking | `false` | pro | `available` | 2026-09-03T11:24:52.864031Z |
| `pplx_claude_o48` | `anthropic/claude-opus-4.8` | Claude Opus 4.8 | `false` | max | `available` | 2026-09-03T11:24:58.547866Z |
| `pplx_claude_o48_think` | `anthropic/claude-opus-4.8-thinking` | Claude Opus 4.8 Thinking | `false` | max | `available` | 2026-09-03T11:25:05.792719Z |
| `pplx_gemini31_pro_think_low` | `google/gemini-3.1-pro-thinking-low` | Gemini 3.1 Pro | `false` | pro | `available` | 2026-09-03T11:25:09.143634Z |
| `pplx_kimi_k26_instant` | `moonshot/kimi-k2.6-instant` | Kimi K2.6 | `false` | pro | `available` | 2026-09-03T11:25:13.951836Z |
| `pplx_kimi_k26_thinking` | `moonshot/kimi-k2.6-thinking` | Kimi K2.6 Thinking | `false` | pro | `available` | 2026-09-03T11:25:17.239309Z |
| `pplx_nemotron3_super_think` | `nvidia/nemotron-3-super-thinking` | Nemotron 3 Super | `false` | pro | `available` | 2026-09-03T11:25:21.372519Z |
| `pplx_gpt54` | `openai/gpt-5.4` | GPT-5.4 | `false` | pro | `available` | 2026-09-03T11:25:25.350995Z |
| `pplx_gpt54_thinking` | `openai/gpt-5.4-thinking` | GPT-5.4 Thinking | `false` | pro | `available` | 2026-09-03T11:25:29.370161Z |
| `pplx_gpt55_thinking` | `openai/gpt-5.5-thinking` | GPT-5.5 Thinking | `false` | max | `available` | 2026-09-03T11:25:35.124946Z |
| `pplx_claude_o47` | `anthropic/claude-opus-4.7` | Claude Opus 4.7 | `false` | max | `available` | 2026-09-03T11:25:39.603900Z |
| `pplx_claude_o47_think` | `anthropic/claude-opus-4.7-thinking` | Claude Opus 4.7 Thinking | `false` | max | `available` | 2026-09-03T11:25:45.697471Z |
| `pplx_claude_s46` | `anthropic/claude-sonnet-4.6` | Claude Sonnet 4.6 | `false` | pro | `available` | 2026-09-03T11:25:51.982932Z |
| `pplx_claude_s46_think` | `anthropic/claude-sonnet-4.6-thinking` | Claude Sonnet 4.6 Thinking | `false` | pro | `available` | 2026-09-03T11:25:55.342187Z |
| `pplx_gpt4o` | `openai/gpt4o` | GPT-4o | `false` | unknown | `available` | 2026-09-03T11:25:59.837844Z |
| `pplx_gpt41` | `openai/gpt41` | GPT-4.1 | `false` | unknown | `available` | 2026-09-03T11:26:03.279349Z |
| `pplx_gpt5` | `openai/gpt5` | GPT-5 | `false` | unknown | `available` | 2026-09-03T11:26:07.351477Z |
| `pplx_gpt5_thinking` | `openai/gpt5-thinking` | GPT-5 Thinking | `false` | unknown | `available` | 2026-09-03T11:26:11.502969Z |
| `pplx_gpt51` | `openai/gpt51` | GPT-5.1 | `false` | unknown | `available` | 2026-09-03T11:26:15.652342Z |
| `pplx_gpt51_thinking` | `openai/gpt51-thinking` | GPT-5.1 Thinking | `false` | unknown | `available` | 2026-09-03T11:26:19.383352Z |
| `pplx_gpt51_low_thinking` | `openai/gpt51-low-thinking` | GPT-5.1 Low Thinking | `false` | unknown | `available` | 2026-09-03T11:26:23.558056Z |
| `pplx_gpt5_mini` | `openai/gpt5-mini` | GPT-5 Mini | `false` | unknown | `available` | 2026-09-03T11:26:27.310469Z |
| `pplx_gpt5_nano` | `openai/gpt5-nano` | GPT-5 Nano | `false` | unknown | `available` | 2026-09-03T11:26:31.525358Z |
| `pplx_gpt5_pro` | `openai/gpt5-pro` | GPT-5 Pro | `false` | unknown | `available` | 2026-09-03T11:26:37.316463Z |
| `pplx_gpt52` | `openai/gpt52` | GPT-5.2 | `false` | unknown | `available` | 2026-09-03T11:26:40.764900Z |
| `pplx_gpt52_thinking` | `openai/gpt52-thinking` | GPT-5.2 Thinking | `false` | unknown | `available` | 2026-09-03T11:26:45.042526Z |
| `pplx_gpt52_pro` | `openai/gpt52-pro` | GPT-5.2 Pro | `false` | unknown | `available` | 2026-09-03T11:26:52.724936Z |
| `pplx_gpt55` | `openai/gpt55` | GPT-5.5 | `false` | unknown | `available` | 2026-09-03T11:27:00.976672Z |
| `pplx_claude2` | `anthropic/claude2` | Claude Sonnet 4.0 | `false` | unknown | `available` | 2026-09-03T11:27:04.448034Z |
| `pplx_claude37sonnetthinking` | `anthropic/claude37sonnetthinking` | Claude Sonnet 4.0 Thinking | `false` | unknown | `available` | 2026-09-03T11:27:08.523621Z |
| `pplx_claude40sonnetthinking` | `anthropic/claude40sonnetthinking` | Claude Sonnet 4.0 Thinking | `false` | unknown | `available` | 2026-09-03T11:27:12.773211Z |
| `pplx_gemini25pro` | `google/gemini25pro` | Gemini 2.5 Pro | `false` | unknown | `available` | 2026-09-03T11:27:16.685627Z |
| `pplx_gemini30pro` | `google/gemini30pro` | Gemini 3 Pro | `false` | unknown | `available` | 2026-09-03T11:27:20.524726Z |
| `pplx_gemini30flash` | `google/gemini30flash` | Gemini 3 Flash | `false` | unknown | `available` | 2026-09-03T11:27:24.341624Z |
| `pplx_gemini30flash_high` | `google/gemini30flash-high` | Gemini 3 Flash Thinking | `false` | unknown | `available` | 2026-09-03T11:27:28.377231Z |
| `pplx_gemini35flash` | `google/gemini35flash` | Gemini 3.5 Flash | `false` | unknown | `available` | 2026-09-03T11:27:32.510070Z |
| `pplx_gemini35flash_medium` | `google/gemini35flash-medium` | Gemini 3.5 Flash Medium Thinking | `false` | unknown | `available` | 2026-09-03T11:27:36.844582Z |
| `pplx_gemini35flash_high` | `google/gemini35flash-high` | Gemini 3.5 Flash Thinking | `false` | unknown | `available` | 2026-09-03T11:27:40.358426Z |
| `pplx_grok` | `x-ai/grok` | Grok 3 Beta | `false` | unknown | `available` | 2026-09-03T11:27:44.432190Z |
| `pplx_claude40opus` | `anthropic/claude40opus` | Claude Opus 4.0 | `false` | unknown | `available` | 2026-09-03T11:27:48.335559Z |
| `pplx_claude40opusthinking` | `anthropic/claude40opusthinking` | Claude Opus 4.0 Thinking | `false` | unknown | `available` | 2026-09-03T11:27:54.319641Z |
| `pplx_claude41opus` | `anthropic/claude41opus` | Claude Opus 4.1 | `false` | unknown | `available` | 2026-09-03T11:27:59.327141Z |
| `pplx_claude41opusthinking` | `anthropic/claude41opusthinking` | Claude Opus 4.1 Thinking | `false` | unknown | `available` | 2026-09-03T11:28:04.308568Z |
| `pplx_claude45opus` | `anthropic/claude45opus` | Claude Opus 4.5 | `false` | unknown | `available` | 2026-09-03T11:28:11.398179Z |
| `pplx_claude45opusthinking` | `anthropic/claude45opusthinking` | Claude Opus 4.5 Thinking | `false` | unknown | `available` | 2026-09-03T11:28:16.934832Z |
| `pplx_claude46opus` | `anthropic/claude46opus` | Claude Opus 4.6 | `false` | unknown | `available` | 2026-09-03T11:28:22.379165Z |
| `pplx_claude46opusthinking` | `anthropic/claude46opusthinking` | Claude Opus 4.6 Thinking | `false` | unknown | `available` | 2026-09-03T11:28:27.184108Z |
| `pplx_claude45sonnet` | `anthropic/claude45sonnet` | Claude Sonnet 4.5 | `false` | unknown | `available` | 2026-09-03T11:28:30.536377Z |
| `pplx_claude45sonnetthinking` | `anthropic/claude45sonnetthinking` | Claude Sonnet 4.5 Thinking | `false` | unknown | `available` | 2026-09-03T11:28:34.776512Z |
| `pplx_claude45haiku` | `anthropic/claude45haiku` | Claude Haiku 4.5 | `false` | unknown | `unavailable` | 2026-09-03T11:29:42.990929Z |
| `pplx_claude45haikuthinking` | `anthropic/claude45haikuthinking` | Claude Haiku 4.5 Thinking | `false` | unknown | `unavailable` | 2026-09-03T11:29:46.808308Z |
| `pplx_kimik2thinking` | `moonshot/kimik2thinking` | Kimi K2 | `false` | unknown | `available` | 2026-09-03T11:28:46.934524Z |
| `pplx_kimik25thinking` | `moonshot/kimik25thinking` | Kimi K2.5 Thinking | `false` | unknown | `available` | 2026-09-03T11:28:50.952534Z |
| `pplx_grok4` | `x-ai/grok4` | Grok 4 | `false` | unknown | `available` | 2026-09-03T11:28:54.587374Z |
| `pplx_grok4nonthinking` | `x-ai/grok4nonthinking` | Grok 4 | `false` | unknown | `available` | 2026-09-03T11:28:58.503272Z |
| `pplx_grok41reasoning` | `x-ai/grok41reasoning` | Grok 4.1 | `false` | unknown | `available` | 2026-09-03T11:29:02.678239Z |
| `pplx_grok41nonreasoning` | `x-ai/grok41nonreasoning` | Grok 4.1 | `false` | unknown | `available` | 2026-09-03T11:29:07.564332Z |
| `pplx_o4mini` | `openai/o4mini` | o4-mini | `false` | unknown | `available` | 2026-09-03T11:29:10.930610Z |
| `pplx_o3pro` | `openai/o3pro` | o3-pro | `false` | unknown | `available` | 2026-09-03T11:29:16.844157Z |

### Custom tool

`pplx_custom` accepts an arbitrary `custom:<identifier>` model and requires explicit risky-model acknowledgement.

<!-- END GENERATED MODEL CATALOG -->

**All tools support `source_focus`:** `web`, `academic`, `social`, `finance`, `all`
