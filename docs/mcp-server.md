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
| `pplx_best` | `perplexity/best` | Best | `true` | free | `available` | 2026-10-05T20:16:12.021045Z |
| `pplx_deep_research` | `perplexity/deep-research` | Deep research | `true` | pro | `available` | 2026-10-05T20:16:18.032678Z |
| `pplx_gpt61_sol` | `openai/gpt-6.1-sol` | GPT-6.1 Sol | `true` | pro | `available` | 2026-10-05T20:16:22.833164Z |
| `pplx_gpt61_sol_think` | `openai/gpt-6.1-sol-thinking` | GPT-6.1 Sol Thinking | `true` | pro | `available` | 2026-10-05T20:16:28.012592Z |
| `pplx_gpt6_astra` | `openai/gpt-6-astra` | GPT-6 Astra | `true` | max | `available` | 2026-10-05T20:16:31.992994Z |
| `pplx_gpt6_astra_think` | `openai/gpt-6-astra-thinking` | GPT-6 Astra Thinking | `true` | max | `available` | 2026-10-05T20:16:35.921714Z |
| `pplx_gemini38_flash` | `google/gemini-3.8-flash` | Gemini 3.8 Flash | `true` | pro | `available` | 2026-10-05T20:16:40.371258Z |
| `pplx_gemini38_flash_think` | `google/gemini-3.8-flash-thinking` | Gemini 3.8 Flash Thinking | `true` | pro | `available` | 2026-10-05T20:16:44.417812Z |
| `pplx_claude_sonnet55` | `anthropic/claude-sonnet-5.5` | Claude Sonnet 5.5 | `true` | pro | `available` | 2026-10-05T20:16:48.109965Z |
| `pplx_claude_sonnet55_think` | `anthropic/claude-sonnet-5.5-thinking` | Claude Sonnet 5.5 Thinking | `true` | pro | `available` | 2026-10-05T20:16:52.166366Z |
| `pplx_claude_opus55` | `anthropic/claude-opus-5.5` | Claude Opus 5.5 | `true` | max | `available` | 2026-10-05T20:16:55.692021Z |
| `pplx_claude_opus55_think` | `anthropic/claude-opus-5.5-thinking` | Claude Opus 5.5 Thinking | `true` | max | `available` | 2026-10-05T20:17:00.347130Z |
| `pplx_claude_fable51` | `anthropic/claude-fable-5.1` | Claude Fable 5.1 | `true` | max | `available` | 2026-10-05T20:17:03.783203Z |
| `pplx_claude_fable51_think` | `anthropic/claude-fable-5.1-thinking` | Claude Fable 5.1 Thinking | `true` | max | `available` | 2026-10-05T20:17:08.318815Z |
| `pplx_kimi_k3_thinking` | `moonshot/kimi-k3-thinking` | Kimi K3 Thinking | `true` | pro | `available` | 2026-10-05T20:17:13.205366Z |
| `pplx_glm53` | `z-ai/glm-5.3` | GLM 5.3 Thinking | `true` | pro | `available` | 2026-10-05T20:17:16.544851Z |
| `pplx_grok47` | `x-ai/grok-4.7` | Grok 4.7 | `true` | pro | `available` | 2026-10-05T20:17:21.160176Z |
| `pplx_grok47_think` | `x-ai/grok-4.7-thinking` | Grok 4.7 Thinking | `true` | pro | `available` | 2026-10-05T20:17:27.797021Z |
| `pplx_nemotron3_ultra_think` | `nvidia/nemotron-3-ultra-thinking` | Nemotron 3 Ultra | `true` | pro | `available` | 2026-10-05T20:17:33.054764Z |
| `pplx_gpt56_terra` | `openai/gpt-5.6-terra` | GPT-5.6 Terra | `false` | pro | `available` | 2026-10-05T20:17:36.892876Z |
| `pplx_gpt56_terra_thinking` | `openai/gpt-5.6-terra-thinking` | GPT-5.6 Terra Thinking | `false` | pro | `available` | 2026-10-05T20:17:41.372437Z |
| `pplx_gpt56_sol` | `openai/gpt-5.6-sol` | GPT-5.6 Sol | `false` | max | `available` | 2026-10-05T20:17:44.686046Z |
| `pplx_gpt56_sol_thinking` | `openai/gpt-5.6-sol-thinking` | GPT-5.6 Sol Thinking | `false` | max | `available` | 2026-10-05T20:17:49.336905Z |
| `pplx_claude_s50` | `anthropic/claude-sonnet-5` | Claude Sonnet 5 | `false` | pro | `available` | 2026-10-05T20:17:52.595578Z |
| `pplx_claude_s50_think` | `anthropic/claude-sonnet-5-thinking` | Claude Sonnet 5 Thinking | `false` | pro | `available` | 2026-10-05T20:17:57.596324Z |
| `pplx_claude_o50` | `anthropic/claude-opus-5` | Claude Opus 5 | `false` | max | `available` | 2026-10-05T20:18:00.987050Z |
| `pplx_claude_o50_think` | `anthropic/claude-opus-5-thinking` | Claude Opus 5 Thinking | `false` | max | `available` | 2026-10-05T20:18:05.096460Z |
| `pplx_grok46` | `x-ai/grok-4.6` | Grok 4.6 | `false` | pro | `available` | 2026-10-05T20:18:09.569313Z |
| `pplx_grok46_think` | `x-ai/grok-4.6-thinking` | Grok 4.6 Thinking | `false` | pro | `available` | 2026-10-05T20:18:13.112017Z |
| `pplx_gemini37_flash` | `google/gemini-3.7-flash` | Gemini 3.7 Flash | `false` | pro | `available` | 2026-10-05T20:18:17.589452Z |
| `pplx_gemini37_flash_think` | `google/gemini-3.7-flash-thinking` | Gemini 3.7 Flash Thinking | `false` | pro | `available` | 2026-10-05T20:18:21.086382Z |
| `pplx_sonar` | `perplexity/sonar-2` | Sonar 2 | `false` | pro | `available` | 2026-10-05T20:18:25.907675Z |
| `pplx_glm52` | `z-ai/glm-5.2` | GLM 5.2 Thinking | `false` | pro | `available` | 2026-10-05T20:18:29.752818Z |
| `pplx_gemini31_pro_think_high` | `google/gemini-3.1-pro-thinking-high` | Gemini 3.1 Pro Thinking | `false` | pro | `available` | 2026-10-05T20:18:33.124771Z |
| `pplx_grok45` | `x-ai/grok-4.5` | Grok 4.5 | `false` | pro | `available` | 2026-10-05T20:18:37.687491Z |
| `pplx_grok45_think` | `x-ai/grok-4.5-thinking` | Grok 4.5 Thinking | `false` | pro | `available` | 2026-10-05T20:18:41.156413Z |
| `pplx_claude_o48` | `anthropic/claude-opus-4.8` | Claude Opus 4.8 | `false` | max | `available` | 2026-10-05T20:18:45.868241Z |
| `pplx_claude_o48_think` | `anthropic/claude-opus-4.8-thinking` | Claude Opus 4.8 Thinking | `false` | max | `available` | 2026-10-05T20:18:49.255021Z |
| `pplx_gemini31_pro_think_low` | `google/gemini-3.1-pro-thinking-low` | Gemini 3.1 Pro | `false` | pro | `available` | 2026-10-05T20:19:03.092759Z |
| `pplx_kimi_k26_instant` | `moonshot/kimi-k2.6-instant` | Kimi K2.6 | `false` | pro | `available` | 2026-10-05T20:19:08.861946Z |
| `pplx_kimi_k26_thinking` | `moonshot/kimi-k2.6-thinking` | Kimi K2.6 Thinking | `false` | pro | `available` | 2026-10-05T20:19:16.641404Z |
| `pplx_nemotron3_super_think` | `nvidia/nemotron-3-super-thinking` | Nemotron 3 Super | `false` | pro | `available` | 2026-10-05T20:19:22.377771Z |
| `pplx_gpt54` | `openai/gpt-5.4` | GPT-5.4 | `false` | pro | `available` | 2026-10-05T20:19:28.268387Z |
| `pplx_gpt54_thinking` | `openai/gpt-5.4-thinking` | GPT-5.4 Thinking | `false` | pro | `available` | 2026-10-05T20:19:35.680421Z |
| `pplx_gpt55_thinking` | `openai/gpt-5.5-thinking` | GPT-5.5 Thinking | `false` | max | `available` | 2026-10-05T20:19:39.220575Z |
| `pplx_claude_o47` | `anthropic/claude-opus-4.7` | Claude Opus 4.7 | `false` | max | `available` | 2026-10-05T20:19:42.950685Z |
| `pplx_claude_o47_think` | `anthropic/claude-opus-4.7-thinking` | Claude Opus 4.7 Thinking | `false` | max | `available` | 2026-10-05T20:19:47.582690Z |
| `pplx_claude_s46` | `anthropic/claude-sonnet-4.6` | Claude Sonnet 4.6 | `false` | pro | `available` | 2026-10-05T20:19:54.658740Z |
| `pplx_claude_s46_think` | `anthropic/claude-sonnet-4.6-thinking` | Claude Sonnet 4.6 Thinking | `false` | pro | `available` | 2026-10-05T20:20:00.946005Z |
| `pplx_gpt4o` | `openai/gpt4o` | GPT-4o | `false` | unknown | `available` | 2026-10-05T20:20:07.311257Z |
| `pplx_gpt41` | `openai/gpt41` | GPT-4.1 | `false` | unknown | `available` | 2026-10-05T20:20:14.175169Z |
| `pplx_gpt5` | `openai/gpt5` | GPT-5 | `false` | unknown | `available` | 2026-10-05T20:20:17.642527Z |
| `pplx_gpt5_thinking` | `openai/gpt5-thinking` | GPT-5 Thinking | `false` | unknown | `available` | 2026-10-05T20:20:24.042030Z |
| `pplx_gpt51` | `openai/gpt51` | GPT-5.1 | `false` | unknown | `available` | 2026-10-05T20:20:29.840354Z |
| `pplx_gpt51_thinking` | `openai/gpt51-thinking` | GPT-5.1 Thinking | `false` | unknown | `available` | 2026-10-05T20:20:35.277267Z |
| `pplx_gpt51_low_thinking` | `openai/gpt51-low-thinking` | GPT-5.1 Low Thinking | `false` | unknown | `available` | 2026-10-05T20:20:40.743367Z |
| `pplx_gpt5_mini` | `openai/gpt5-mini` | GPT-5 Mini | `false` | unknown | `available` | 2026-10-05T20:20:46.442829Z |
| `pplx_gpt5_nano` | `openai/gpt5-nano` | GPT-5 Nano | `false` | unknown | `available` | 2026-10-05T20:20:52.164460Z |
| `pplx_gpt5_pro` | `openai/gpt5-pro` | GPT-5 Pro | `false` | unknown | `available` | 2026-10-05T20:20:55.450519Z |
| `pplx_gpt52` | `openai/gpt52` | GPT-5.2 | `false` | unknown | `available` | 2026-10-05T20:21:02.704078Z |
| `pplx_gpt52_thinking` | `openai/gpt52-thinking` | GPT-5.2 Thinking | `false` | unknown | `available` | 2026-10-05T20:21:10.329201Z |
| `pplx_gpt52_pro` | `openai/gpt52-pro` | GPT-5.2 Pro | `false` | unknown | `available` | 2026-10-05T20:21:14.247814Z |
| `pplx_gpt55` | `openai/gpt55` | GPT-5.5 | `false` | unknown | `available` | 2026-10-05T20:21:18.887829Z |
| `pplx_claude2` | `anthropic/claude2` | Claude Sonnet 4.0 | `false` | unknown | `available` | 2026-10-05T20:21:26.162824Z |
| `pplx_claude37sonnetthinking` | `anthropic/claude37sonnetthinking` | Claude Sonnet 4.0 Thinking | `false` | unknown | `available` | 2026-10-05T20:21:33.770960Z |
| `pplx_claude40sonnetthinking` | `anthropic/claude40sonnetthinking` | Claude Sonnet 4.0 Thinking | `false` | unknown | `available` | 2026-10-05T20:21:39.369405Z |
| `pplx_gemini25pro` | `google/gemini25pro` | Gemini 2.5 Pro | `false` | unknown | `available` | 2026-10-05T20:21:46.256518Z |
| `pplx_gemini30pro` | `google/gemini30pro` | Gemini 3 Pro | `false` | unknown | `available` | 2026-10-05T20:21:51.707249Z |
| `pplx_gemini30flash` | `google/gemini30flash` | Gemini 3 Flash | `false` | unknown | `available` | 2026-10-05T20:21:59.257659Z |
| `pplx_gemini30flash_high` | `google/gemini30flash-high` | Gemini 3 Flash Thinking | `false` | unknown | `available` | 2026-10-05T20:22:05.156413Z |
| `pplx_gemini35flash` | `google/gemini35flash` | Gemini 3.5 Flash | `false` | unknown | `available` | 2026-10-05T20:22:11.637321Z |
| `pplx_gemini35flash_medium` | `google/gemini35flash-medium` | Gemini 3.5 Flash Medium Thinking | `false` | unknown | `available` | 2026-10-05T20:22:21.154462Z |
| `pplx_gemini35flash_high` | `google/gemini35flash-high` | Gemini 3.5 Flash Thinking | `false` | unknown | `available` | 2026-10-05T20:22:26.603273Z |
| `pplx_grok` | `x-ai/grok` | Grok 3 Beta | `false` | unknown | `available` | 2026-10-05T20:22:32.664260Z |
| `pplx_claude40opus` | `anthropic/claude40opus` | Claude Opus 4.0 | `false` | unknown | `available` | 2026-10-05T20:22:36.515050Z |
| `pplx_claude40opusthinking` | `anthropic/claude40opusthinking` | Claude Opus 4.0 Thinking | `false` | unknown | `available` | 2026-10-05T20:22:40.721695Z |
| `pplx_claude41opus` | `anthropic/claude41opus` | Claude Opus 4.1 | `false` | unknown | `available` | 2026-10-05T20:22:44.629881Z |
| `pplx_claude41opusthinking` | `anthropic/claude41opusthinking` | Claude Opus 4.1 Thinking | `false` | unknown | `available` | 2026-10-05T20:22:48.894780Z |
| `pplx_claude45opus` | `anthropic/claude45opus` | Claude Opus 4.5 | `false` | unknown | `available` | 2026-10-05T20:22:52.821427Z |
| `pplx_claude45opusthinking` | `anthropic/claude45opusthinking` | Claude Opus 4.5 Thinking | `false` | unknown | `available` | 2026-10-05T20:22:58.618130Z |
| `pplx_claude46opus` | `anthropic/claude46opus` | Claude Opus 4.6 | `false` | unknown | `available` | 2026-10-05T20:23:02.564382Z |
| `pplx_claude46opusthinking` | `anthropic/claude46opusthinking` | Claude Opus 4.6 Thinking | `false` | unknown | `available` | 2026-10-05T20:23:06.445541Z |
| `pplx_claude45sonnet` | `anthropic/claude45sonnet` | Claude Sonnet 4.5 | `false` | unknown | `available` | 2026-10-05T20:23:12.047553Z |
| `pplx_claude45sonnetthinking` | `anthropic/claude45sonnetthinking` | Claude Sonnet 4.5 Thinking | `false` | unknown | `available` | 2026-10-05T20:23:17.241769Z |
| `pplx_claude45haiku` | `anthropic/claude45haiku` | Claude Haiku 4.5 | `false` | unknown | `unavailable` | 2026-10-05T20:24:36.883274Z |
| `pplx_claude45haikuthinking` | `anthropic/claude45haikuthinking` | Claude Haiku 4.5 Thinking | `false` | unknown | `unavailable` | 2026-10-05T20:24:39.634814Z |
| `pplx_kimik2thinking` | `moonshot/kimik2thinking` | Kimi K2 | `false` | unknown | `available` | 2026-10-05T20:23:31.231503Z |
| `pplx_kimik25thinking` | `moonshot/kimik25thinking` | Kimi K2.5 Thinking | `false` | unknown | `available` | 2026-10-05T20:23:37.113506Z |
| `pplx_grok4` | `x-ai/grok4` | Grok 4 | `false` | unknown | `available` | 2026-10-05T20:23:43.083161Z |
| `pplx_grok4nonthinking` | `x-ai/grok4nonthinking` | Grok 4 | `false` | unknown | `available` | 2026-10-05T20:23:50.768883Z |
| `pplx_grok41reasoning` | `x-ai/grok41reasoning` | Grok 4.1 | `false` | unknown | `available` | 2026-10-05T20:23:57.302914Z |
| `pplx_grok41nonreasoning` | `x-ai/grok41nonreasoning` | Grok 4.1 | `false` | unknown | `available` | 2026-10-05T20:24:03.796888Z |
| `pplx_o4mini` | `openai/o4mini` | o4-mini | `false` | unknown | `available` | 2026-10-05T20:24:09.660058Z |
| `pplx_o3pro` | `openai/o3pro` | o3-pro | `false` | unknown | `available` | 2026-10-05T20:24:13.535048Z |

### Custom tool

`pplx_custom` accepts an arbitrary `custom:<identifier>` model and requires explicit risky-model acknowledgement.

<!-- END GENERATED MODEL CATALOG -->

**All tools support `source_focus`:** `web`, `academic`, `social`, `finance`, `all`
