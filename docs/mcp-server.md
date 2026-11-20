# MCP server

The MCP server exposes each registered model as a separate tool over stdio. Enable only the tools your MCP client needs.

See [Session Token](token.md) for how to generate and protect `PERPLEXITY_SESSION_TOKEN` (both compact `wsk_` tokens and raw `__Secure-pplx.session.<UUIDv4>=<JWE>` cookie pairs are supported).

## Configuration

Add one of the following entries to your MCP client configuration. `uvx` creates an isolated Python environment for the server.

**PyPI installation:**

```json
{
  "mcpServers": {
    "perplexity-webui-scraper": {
      "command": "uvx",
      "args": [
        "--from",
        "perplexity-webui-scraper[mcp]",
        "perplexity-webui-scraper",
        "mcp"
      ],
      "env": {
        "PERPLEXITY_SESSION_TOKEN": "wsk_YOUR_COMPACT_TOKEN"
      }
    }
  }
}
```

**Local checkout:**

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
        "PERPLEXITY_SESSION_TOKEN": "wsk_YOUR_COMPACT_TOKEN"
      }
    }
  }
}
```

## Container deployment with Podman

For containerized stdio setups only. `PERPLEXITY_SESSION_TOKEN` accepts either the raw `__Secure-pplx.session.<UUIDv4>=<JWE>` cookie pair or a compact `wsk_` token from the token CLI. Compact tokens are reversible obfuscation, not encryption or authenticated integrity.

```bash
# Pull published MCP image
podman pull ghcr.io/henrique-coder/perplexity-webui-scraper:mcp

# Run the published image over stdio with your session token
podman run --rm -i -e PERPLEXITY_SESSION_TOKEN="wsk_YOUR_COMPACT_TOKEN" ghcr.io/henrique-coder/perplexity-webui-scraper:mcp
```

The MCP server accepts raw and compact credentials. The token CLI retrieves the account cookie through email OTP/magic-link and optional TOTP, then emits compact form. Use `perplexity-webui-scraper token convert` to convert or validate an existing credential offline, or `perplexity-webui-scraper token deconvert` to restore the raw cookie pair.

Use `uvx` for standard MCP client configurations. The container image runs the server over stdio and does not expose an HTTP endpoint.

## Available Tools

Each tool maps to a registered model. Enable only the tools required by the MCP client:

Tools for models with `available` status can be called without acknowledgement. Models with `unknown` or `unavailable` status require `allow_risky_model=true`. `is_official` reports whether a model appears in Perplexity's picker; it does not indicate test status. `pplx_custom` accepts a custom identifier; custom models default to `unknown` and `is_official=false`.

<!-- BEGIN GENERATED MODEL CATALOG -->
### Model status reference

| Status | Meaning | Runtime behavior |
| --- | --- | --- |
| `available` | Confirmed to work normally. | Normal use; the local minimum-tier check applies. |
| `unknown` | Current availability has not been confirmed. | Requires `allow_risky_model`; this is the default for unverified entries. |
| `unavailable` | Confirmed not to work with the current backend. | Requires `allow_risky_model`; retained for history and expected to fail. |

### Model tools

| Tool | Model ID | Name | Official | Min. tier | Status | Last tested (UTC) |
| --- | --- | --- | --- | --- | --- | --- |
| `pplx_best` | `perplexity/best` | Best | `true` | free | `available` | 2026-11-19T21:11:38Z |
| `pplx_deep_research` | `perplexity/deep-research` | Deep research | `true` | pro | `available` | 2026-11-19T21:11:46Z |
| `pplx_gpt62_sol` | `openai/gpt-6.2-sol` | GPT-6.2 Sol | `true` | pro | `available` | 2026-11-19T21:11:53Z |
| `pplx_gpt62_sol_think` | `openai/gpt-6.2-sol-thinking` | GPT-6.2 Sol Thinking | `true` | pro | `available` | 2026-11-19T21:11:59Z |
| `pplx_gpt62_astra` | `openai/gpt-6.2-astra` | GPT-6.2 Astra | `true` | max | `unknown` | — |
| `pplx_gpt62_astra_think` | `openai/gpt-6.2-astra-thinking` | GPT-6.2 Astra Thinking | `true` | max | `unknown` | — |
| `pplx_gemini4_carbon` | `google/gemini-4-carbon` | Gemini 4 Carbon | `true` | max | `unknown` | — |
| `pplx_gemini4_carbon_think` | `google/gemini-4-carbon-thinking` | Gemini 4 Carbon Thinking | `true` | max | `unknown` | — |
| `pplx_gemini_neon` | `google/gemini-neon` | Gemini Neon | `true` | pro | `available` | 2026-11-19T21:12:06Z |
| `pplx_gemini_neon_think` | `google/gemini-neon-thinking` | Gemini Neon Thinking | `true` | pro | `available` | 2026-11-19T21:12:12Z |
| `pplx_claude_sonnet55` | `anthropic/claude-sonnet-5.5` | Claude Sonnet 5.5 | `true` | pro | `available` | 2026-11-19T21:12:18Z |
| `pplx_claude_sonnet55_think` | `anthropic/claude-sonnet-5.5-thinking` | Claude Sonnet 5.5 Thinking | `true` | pro | `available` | 2026-11-19T21:12:25Z |
| `pplx_claude_opus55` | `anthropic/claude-opus-5.5` | Claude Opus 5.5 | `true` | max | `available` | 2026-10-05T20:16:55.692021Z |
| `pplx_claude_opus55_think` | `anthropic/claude-opus-5.5-thinking` | Claude Opus 5.5 Thinking | `true` | max | `available` | 2026-10-05T20:17:00.347130Z |
| `pplx_claude_fable52` | `anthropic/claude-fable-5.2` | Claude Fable 5.2 | `true` | max | `unknown` | — |
| `pplx_claude_fable52_think` | `anthropic/claude-fable-5.2-thinking` | Claude Fable 5.2 Thinking | `true` | max | `unknown` | — |
| `pplx_kimi_k3_thinking` | `moonshot/kimi-k3-thinking` | Kimi K3 Thinking | `true` | pro | `available` | 2026-11-19T21:12:31Z |
| `pplx_glm53` | `z-ai/glm-5.3` | GLM 5.3 Thinking | `true` | pro | `available` | 2026-11-19T21:12:37Z |
| `pplx_grok47` | `x-ai/grok-4.7` | Grok 4.7 | `true` | pro | `available` | 2026-11-19T21:12:43Z |
| `pplx_grok47_think` | `x-ai/grok-4.7-thinking` | Grok 4.7 Thinking | `true` | pro | `available` | 2026-11-19T21:12:50Z |
| `pplx_nemotron35_super_vl_think` | `nvidia/nemotron-3.5-super-vl-thinking` | Nemotron 3.5 Super VL Thinking | `true` | pro | `available` | 2026-11-19T21:12:56Z |
| `pplx_gemini4_hydrogen` | `google/gemini-4-hydrogen` | Gemini 4 Hydrogen | `false` | pro | `available` | 2026-11-19T21:13:02Z |
| `pplx_gemini4_hydrogen_think` | `google/gemini-4-hydrogen-thinking` | Gemini 4 Hydrogen Thinking | `false` | pro | `available` | 2026-11-19T21:13:08Z |
| `pplx_gpt61_sol` | `openai/gpt-6.1-sol` | GPT-6.1 Sol | `false` | pro | `available` | 2026-11-19T21:13:15Z |
| `pplx_gpt61_sol_think` | `openai/gpt-6.1-sol-thinking` | GPT-6.1 Sol Thinking | `false` | pro | `available` | 2026-11-19T21:13:21Z |
| `pplx_gpt6_astra` | `openai/gpt-6-astra` | GPT-6 Astra | `false` | max | `available` | 2026-10-05T20:16:31.992994Z |
| `pplx_gpt6_astra_think` | `openai/gpt-6-astra-thinking` | GPT-6 Astra Thinking | `false` | max | `available` | 2026-10-05T20:16:35.921714Z |
| `pplx_gemini38_flash` | `google/gemini-3.8-flash` | Gemini 3.8 Flash | `false` | pro | `available` | 2026-11-19T21:13:27Z |
| `pplx_gemini38_flash_think` | `google/gemini-3.8-flash-thinking` | Gemini 3.8 Flash Thinking | `false` | pro | `available` | 2026-11-19T21:13:33Z |
| `pplx_gemini4_argon` | `google/gemini-4-argon` | Gemini 4 Argon | `false` | max | `unknown` | — |
| `pplx_gemini4_argon_think` | `google/gemini-4-argon-thinking` | Gemini 4 Argon Thinking | `false` | max | `unknown` | — |
| `pplx_claude_fable51` | `anthropic/claude-fable-5.1` | Claude Fable 5.1 | `false` | max | `available` | 2026-10-05T20:17:03.783203Z |
| `pplx_claude_fable51_think` | `anthropic/claude-fable-5.1-thinking` | Claude Fable 5.1 Thinking | `false` | max | `available` | 2026-10-05T20:17:08.318815Z |
| `pplx_nemotron3_ultra_think` | `nvidia/nemotron-3-ultra-thinking` | Nemotron 3 Ultra | `false` | pro | `available` | 2026-11-19T21:13:40Z |
| `pplx_claude_haiku55` | `anthropic/claude-haiku-5.5` | Claude Haiku 5.5 | `false` | pro | `available` | 2026-11-19T21:13:46Z |
| `pplx_claude_haiku55_think` | `anthropic/claude-haiku-5.5-thinking` | Claude Haiku 5.5 Thinking | `false` | pro | `available` | 2026-11-19T21:13:52Z |
| `pplx_gpt56_terra` | `openai/gpt-5.6-terra` | GPT-5.6 Terra | `false` | pro | `available` | 2026-11-19T21:13:58Z |
| `pplx_gpt56_terra_thinking` | `openai/gpt-5.6-terra-thinking` | GPT-5.6 Terra Thinking | `false` | pro | `available` | 2026-11-19T21:14:04Z |
| `pplx_gpt56_sol` | `openai/gpt-5.6-sol` | GPT-5.6 Sol | `false` | max | `available` | 2026-10-05T20:17:44.686046Z |
| `pplx_gpt56_sol_thinking` | `openai/gpt-5.6-sol-thinking` | GPT-5.6 Sol Thinking | `false` | max | `available` | 2026-10-05T20:17:49.336905Z |
| `pplx_claude_s50` | `anthropic/claude-sonnet-5` | Claude Sonnet 5 | `false` | pro | `available` | 2026-11-19T21:14:10Z |
| `pplx_claude_s50_think` | `anthropic/claude-sonnet-5-thinking` | Claude Sonnet 5 Thinking | `false` | pro | `available` | 2026-11-19T21:14:16Z |
| `pplx_claude_o50` | `anthropic/claude-opus-5` | Claude Opus 5 | `false` | max | `available` | 2026-10-05T20:18:00.987050Z |
| `pplx_claude_o50_think` | `anthropic/claude-opus-5-thinking` | Claude Opus 5 Thinking | `false` | max | `available` | 2026-10-05T20:18:05.096460Z |
| `pplx_grok46` | `x-ai/grok-4.6` | Grok 4.6 | `false` | pro | `available` | 2026-11-19T21:14:22Z |
| `pplx_grok46_think` | `x-ai/grok-4.6-thinking` | Grok 4.6 Thinking | `false` | pro | `available` | 2026-11-19T21:14:28Z |
| `pplx_gemini37_flash` | `google/gemini-3.7-flash` | Gemini 3.7 Flash | `false` | pro | `available` | 2026-11-19T21:14:34Z |
| `pplx_gemini37_flash_think` | `google/gemini-3.7-flash-thinking` | Gemini 3.7 Flash Thinking | `false` | pro | `available` | 2026-11-19T21:14:41Z |
| `pplx_sonar` | `perplexity/sonar-2` | Sonar 2 | `false` | pro | `available` | 2026-11-19T21:14:47Z |
| `pplx_glm52` | `z-ai/glm-5.2` | GLM 5.2 Thinking | `false` | pro | `available` | 2026-11-19T21:14:53Z |
| `pplx_gemini31_pro_think_high` | `google/gemini-3.1-pro-thinking-high` | Gemini 3.1 Pro Thinking | `false` | pro | `available` | 2026-11-19T21:14:59Z |
| `pplx_grok45` | `x-ai/grok-4.5` | Grok 4.5 | `false` | pro | `available` | 2026-11-19T21:15:05Z |
| `pplx_grok45_think` | `x-ai/grok-4.5-thinking` | Grok 4.5 Thinking | `false` | pro | `available` | 2026-11-19T21:15:11Z |
| `pplx_claude_o48` | `anthropic/claude-opus-4.8` | Claude Opus 4.8 | `false` | max | `available` | 2026-10-05T20:18:45.868241Z |
| `pplx_claude_o48_think` | `anthropic/claude-opus-4.8-thinking` | Claude Opus 4.8 Thinking | `false` | max | `available` | 2026-10-05T20:18:49.255021Z |
| `pplx_gemini31_pro_think_low` | `google/gemini-3.1-pro-thinking-low` | Gemini 3.1 Pro | `false` | pro | `available` | 2026-11-19T21:15:17Z |
| `pplx_kimi_k26_instant` | `moonshot/kimi-k2.6-instant` | Kimi K2.6 | `false` | pro | `available` | 2026-11-19T21:15:23Z |
| `pplx_kimi_k26_thinking` | `moonshot/kimi-k2.6-thinking` | Kimi K2.6 Thinking | `false` | pro | `available` | 2026-11-19T21:15:30Z |
| `pplx_nemotron3_super_think` | `nvidia/nemotron-3-super-thinking` | Nemotron 3 Super | `false` | pro | `available` | 2026-11-19T21:15:36Z |
| `pplx_gpt54` | `openai/gpt-5.4` | GPT-5.4 | `false` | pro | `available` | 2026-11-19T21:15:42Z |
| `pplx_gpt54_thinking` | `openai/gpt-5.4-thinking` | GPT-5.4 Thinking | `false` | pro | `available` | 2026-11-19T21:15:48Z |
| `pplx_gpt55_thinking` | `openai/gpt-5.5-thinking` | GPT-5.5 Thinking | `false` | max | `available` | 2026-10-05T20:19:39.220575Z |
| `pplx_claude_o47` | `anthropic/claude-opus-4.7` | Claude Opus 4.7 | `false` | max | `available` | 2026-10-05T20:19:42.950685Z |
| `pplx_claude_o47_think` | `anthropic/claude-opus-4.7-thinking` | Claude Opus 4.7 Thinking | `false` | max | `available` | 2026-10-05T20:19:47.582690Z |
| `pplx_claude_s46` | `anthropic/claude-sonnet-4.6` | Claude Sonnet 4.6 | `false` | pro | `available` | 2026-11-19T21:15:54Z |
| `pplx_claude_s46_think` | `anthropic/claude-sonnet-4.6-thinking` | Claude Sonnet 4.6 Thinking | `false` | pro | `available` | 2026-11-19T21:16:00Z |
| `pplx_gpt4o` | `openai/gpt4o` | GPT-4o | `false` | unknown | `available` | 2026-11-19T21:16:06Z |
| `pplx_gpt41` | `openai/gpt41` | GPT-4.1 | `false` | unknown | `available` | 2026-11-19T21:16:12Z |
| `pplx_gpt5` | `openai/gpt5` | GPT-5 | `false` | unknown | `available` | 2026-11-19T21:16:18Z |
| `pplx_gpt5_thinking` | `openai/gpt5-thinking` | GPT-5 Thinking | `false` | unknown | `available` | 2026-11-19T21:16:25Z |
| `pplx_gpt51` | `openai/gpt51` | GPT-5.1 | `false` | unknown | `available` | 2026-11-19T21:16:31Z |
| `pplx_gpt51_thinking` | `openai/gpt51-thinking` | GPT-5.1 Thinking | `false` | unknown | `available` | 2026-11-19T21:16:37Z |
| `pplx_gpt51_low_thinking` | `openai/gpt51-low-thinking` | GPT-5.1 Low Thinking | `false` | unknown | `available` | 2026-11-19T21:16:43Z |
| `pplx_gpt5_mini` | `openai/gpt5-mini` | GPT-5 Mini | `false` | unknown | `available` | 2026-11-19T21:16:50Z |
| `pplx_gpt5_nano` | `openai/gpt5-nano` | GPT-5 Nano | `false` | unknown | `available` | 2026-11-19T21:16:56Z |
| `pplx_gpt5_pro` | `openai/gpt5-pro` | GPT-5 Pro | `false` | unknown | `available` | 2026-11-19T21:17:02Z |
| `pplx_gpt52` | `openai/gpt52` | GPT-5.2 | `false` | unknown | `available` | 2026-11-19T21:17:09Z |
| `pplx_gpt52_thinking` | `openai/gpt52-thinking` | GPT-5.2 Thinking | `false` | unknown | `available` | 2026-11-19T21:17:15Z |
| `pplx_gpt52_pro` | `openai/gpt52-pro` | GPT-5.2 Pro | `false` | unknown | `available` | 2026-11-19T21:17:21Z |
| `pplx_gpt55` | `openai/gpt55` | GPT-5.5 | `false` | unknown | `available` | 2026-11-19T21:17:27Z |
| `pplx_claude2` | `anthropic/claude2` | Claude Sonnet 4.0 | `false` | unknown | `available` | 2026-11-19T21:17:34Z |
| `pplx_claude37sonnetthinking` | `anthropic/claude37sonnetthinking` | Claude Sonnet 4.0 Thinking | `false` | unknown | `available` | 2026-11-19T21:17:40Z |
| `pplx_claude40sonnetthinking` | `anthropic/claude40sonnetthinking` | Claude Sonnet 4.0 Thinking | `false` | unknown | `available` | 2026-11-19T21:17:46Z |
| `pplx_gemini25pro` | `google/gemini25pro` | Gemini 2.5 Pro | `false` | unknown | `available` | 2026-11-19T21:17:52Z |
| `pplx_gemini30pro` | `google/gemini30pro` | Gemini 3 Pro | `false` | unknown | `available` | 2026-11-19T21:17:59Z |
| `pplx_gemini30flash` | `google/gemini30flash` | Gemini 3 Flash | `false` | unknown | `available` | 2026-11-19T21:18:05Z |
| `pplx_gemini30flash_high` | `google/gemini30flash-high` | Gemini 3 Flash Thinking | `false` | unknown | `available` | 2026-11-19T21:18:11Z |
| `pplx_gemini35flash` | `google/gemini35flash` | Gemini 3.5 Flash | `false` | unknown | `available` | 2026-11-19T21:18:17Z |
| `pplx_gemini35flash_medium` | `google/gemini35flash-medium` | Gemini 3.5 Flash Medium Thinking | `false` | unknown | `available` | 2026-11-19T21:18:23Z |
| `pplx_gemini35flash_high` | `google/gemini35flash-high` | Gemini 3.5 Flash Thinking | `false` | unknown | `available` | 2026-11-19T21:18:30Z |
| `pplx_grok` | `x-ai/grok` | Grok 3 Beta | `false` | unknown | `available` | 2026-11-19T21:18:36Z |
| `pplx_claude40opus` | `anthropic/claude40opus` | Claude Opus 4.0 | `false` | unknown | `available` | 2026-11-19T21:18:42Z |
| `pplx_claude40opusthinking` | `anthropic/claude40opusthinking` | Claude Opus 4.0 Thinking | `false` | unknown | `available` | 2026-11-19T21:18:49Z |
| `pplx_claude41opus` | `anthropic/claude41opus` | Claude Opus 4.1 | `false` | unknown | `available` | 2026-11-19T21:18:55Z |
| `pplx_claude41opusthinking` | `anthropic/claude41opusthinking` | Claude Opus 4.1 Thinking | `false` | unknown | `available` | 2026-11-19T21:19:01Z |
| `pplx_claude45opus` | `anthropic/claude45opus` | Claude Opus 4.5 | `false` | unknown | `available` | 2026-11-19T21:19:07Z |
| `pplx_claude45opusthinking` | `anthropic/claude45opusthinking` | Claude Opus 4.5 Thinking | `false` | unknown | `available` | 2026-11-19T21:19:13Z |
| `pplx_claude46opus` | `anthropic/claude46opus` | Claude Opus 4.6 | `false` | unknown | `available` | 2026-11-19T21:19:19Z |
| `pplx_claude46opusthinking` | `anthropic/claude46opusthinking` | Claude Opus 4.6 Thinking | `false` | unknown | `available` | 2026-11-19T21:19:26Z |
| `pplx_claude45sonnet` | `anthropic/claude45sonnet` | Claude Sonnet 4.5 | `false` | unknown | `available` | 2026-11-19T21:19:33Z |
| `pplx_claude45sonnetthinking` | `anthropic/claude45sonnetthinking` | Claude Sonnet 4.5 Thinking | `false` | unknown | `available` | 2026-11-19T21:19:39Z |
| `pplx_claude45haiku` | `anthropic/claude45haiku` | Claude Haiku 4.5 | `false` | unknown | `unavailable` | 2026-11-19T21:19:44Z |
| `pplx_claude45haikuthinking` | `anthropic/claude45haikuthinking` | Claude Haiku 4.5 Thinking | `false` | unknown | `unavailable` | 2026-11-19T21:19:50Z |
| `pplx_kimik2thinking` | `moonshot/kimik2thinking` | Kimi K2 | `false` | unknown | `available` | 2026-11-19T21:19:56Z |
| `pplx_kimik25thinking` | `moonshot/kimik25thinking` | Kimi K2.5 Thinking | `false` | unknown | `available` | 2026-11-19T21:20:02Z |
| `pplx_grok4` | `x-ai/grok4` | Grok 4 | `false` | unknown | `available` | 2026-11-19T21:20:08Z |
| `pplx_grok4nonthinking` | `x-ai/grok4nonthinking` | Grok 4 | `false` | unknown | `available` | 2026-11-19T21:20:14Z |
| `pplx_grok41reasoning` | `x-ai/grok41reasoning` | Grok 4.1 | `false` | unknown | `available` | 2026-11-19T21:20:20Z |
| `pplx_grok41nonreasoning` | `x-ai/grok41nonreasoning` | Grok 4.1 | `false` | unknown | `available` | 2026-11-19T21:20:26Z |
| `pplx_o4mini` | `openai/o4mini` | o4-mini | `false` | unknown | `available` | 2026-11-19T21:20:32Z |
| `pplx_o3pro` | `openai/o3pro` | o3-pro | `false` | unknown | `available` | 2026-11-19T21:20:39Z |

### Custom tool

`pplx_custom` accepts an arbitrary `custom:<identifier>` model and requires explicit risky-model acknowledgement.

<!-- END GENERATED MODEL CATALOG -->

### Tool parameters and response

Every registered model tool accepts the following parameters (`pplx_custom` also requires `model` and accepts `model_mode`: `"copilot"`, `"search"`, or `"research"`):

| Parameter              | Type      | Default   | Description                                                                 |
| ---------------------- | --------- | --------- | --------------------------------------------------------------------------- |
| `query`                | `str`     | required  | Search query or question                                                    |
| `search_focus`         | `str`     | `"web"`   | `"web"` (with sources) or `"writing"` (pure generation)                     |
| `source_focus`         | `str`     | `"web"`   | `"web"`, `"academic"`, `"social"`, `"finance"`, or `"all"`                  |
| `time_range`           | `str`     | `"all"`   | `"all"`, `"day"`, `"week"`, `"month"`, or `"year"`                          |
| `language`             | `str`     | `"en-US"` | BCP-47 response language tag                                                |
| `latitude`             | `float?`  | `None`    | Latitude (-90 to 90), required together with `longitude`                    |
| `longitude`            | `float?`  | `None`    | Longitude (-180 to 180), required together with `latitude`                  |
| `allow_risky_model`    | `bool`    | `False`   | Explicitly acknowledge `unknown` or `unavailable` model status              |
| `research_interaction` | `str`     | `"auto"`  | Deep Research clarification handling (`"auto"` or `"manual"`)               |

Each tool returns a dictionary with `answer`, `search_results` (`title`, `url`, `snippet`), and `conversation_uuid` (or a structured `error` / `error_type` object when access or model status confirmation fails).
