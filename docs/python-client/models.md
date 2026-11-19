# Models & Catalog

`ModelRegistry` loads the bundled `_static/models.json` catalog and resolves model IDs, operational status, and account-tier metadata. Import the singleton `MODELS` registry directly from `perplexity_webui_scraper`.

```python
from perplexity_webui_scraper import MODELS

for model in MODELS.list_all():
    print(f"{model.id!r:40} → {model.name} [min_tier={model.min_tier}, status={model.status}]")
```

## Risky and custom models

Models with `"unknown"` or `"unavailable"` status require explicit `allow_risky_model=True` acknowledgement (or raise `ModelStatusError`). Custom internal identifiers use `custom:<identifier>`, default to `status="unknown"`, `min_tier="unknown"`, and `is_official=False`.

```python
from perplexity_webui_scraper import ConversationConfig

# Explicitly test a historical or unverified model
config = ConversationConfig(model="openai/gpt-5.4", allow_risky_model=True)

# Or target a raw upstream identifier directly
custom = ConversationConfig(
    model="custom:gpt57",
    allow_risky_model=True,
    custom_model_mode="copilot",
)
```

`perplexity/best` selects `turbo` (`copilot`) for free accounts and `pplx_pro_upgraded` (`copilot`) for paid accounts automatically.

## `Model`

Frozen metadata entry describing a registered or custom Perplexity model.

| Field                | Type                              | Default     | Description                                                                            |
| -------------------- | --------------------------------- | ----------- | -------------------------------------------------------------------------------------- |
| `id`                 | `str`                             | —           | Canonical model ID (e.g. `"perplexity/best"`).                                         |
| `name`               | `str`                             | —           | Human-readable display name.                                                           |
| `description`        | `str`                             | —           | Short summary of the model's characteristics.                                          |
| `identifier`         | `str`                             | —           | Default internal Perplexity model identifier sent in the request payload.              |
| `identifier_by_tier` | `dict[ModelTier, str]`            | `{}`        | Optional tier-specific internal identifier overrides (e.g. `"free"` vs. `"pro"`).      |
| `tool_name`          | `str`                             | —           | MCP tool name registered for this model (e.g. `"pplx_best"`).                          |
| `provider`           | `str`                             | —           | Provider slug (`"perplexity"`, `"openai"`, `"anthropic"`, `"google"`, `"x-ai"`, etc.). |
| `min_tier`           | `ModelMinTier`                    | `"unknown"` | Minimum required Perplexity tier (`"free"`, `"pro"`, `"max"`, or `"unknown"`).         |
| `is_official`        | `bool`                            | `False`     | Whether Perplexity currently lists the model in the official WebUI picker.             |
| `mode`               | `ModelMode`                       | `"copilot"` | Default internal request mode (`"copilot"`, `"search"`, or `"research"`).              |
| `mode_by_tier`       | `dict[ModelTier, ModelMode]`      | `{}`        | Optional tier-specific mode overrides.                                                 |
| `status`             | `ModelStatus`                     | `"unknown"` | Operational status: `"available"`, `"unknown"`, or `"unavailable"`.                    |
| `last_tested_at`     | <code>datetime &#124; None</code> | `None`      | UTC timestamp of the last conclusive test, or `None` when untested.                    |

## `ModelRegistry`

| Method                                                                               | Returns       | Description                                                                                                       |
| ------------------------------------------------------------------------------------ | ------------- | ----------------------------------------------------------------------------------------------------------------- |
| `resolve(model_id)`                                                                  | `Model`       | Look up a registered model by ID or raise `ValueError`.                                                           |
| `list_all()`                                                                         | `list[Model]` | Return all catalog models in definition order.                                                                    |
| `resolve_for_use(model_id, *, allow_risky_model=False, custom_model_mode="copilot")` | `Model`       | Resolve a catalog or `custom:<identifier>` model, raising `ModelStatusError` if non-available and unacknowledged. |

<!-- BEGIN GENERATED MODEL CATALOG -->
### Model status reference

| Status | Meaning | Runtime behavior |
| --- | --- | --- |
| `available` | Confirmed to work normally. | Normal use; the local minimum-tier check applies. |
| `unknown` | Current availability has not been confirmed. | Requires `allow_risky_model`; this is the default for unverified entries. |
| `unavailable` | Confirmed not to work with the current backend. | Requires `allow_risky_model`; retained for history and expected to fail. |

### Model catalog

| Model ID | Internal identifier | Provider | Official | Min. tier | Status | Last tested (UTC) |
| --- | --- | --- | --- | --- | --- | --- |
| `perplexity/best` | `turbo` | perplexity | `true` | free | `available` | 2026-11-19T21:11:38Z |
| `perplexity/deep-research` | `pplx_alpha` | perplexity | `true` | pro | `available` | 2026-11-19T21:11:46Z |
| `openai/gpt-6.2-sol` | `gpt6_2_sol` | openai | `true` | pro | `available` | 2026-11-19T21:11:53Z |
| `openai/gpt-6.2-sol-thinking` | `gpt6_2_sol_thinking` | openai | `true` | pro | `available` | 2026-11-19T21:11:59Z |
| `openai/gpt-6.2-astra` | `gpt6_2_astra` | openai | `true` | max | `unknown` | — |
| `openai/gpt-6.2-astra-thinking` | `gpt6_2_astra_thinking` | openai | `true` | max | `unknown` | — |
| `google/gemini-4-carbon` | `gemini4carbon` | google | `true` | max | `unknown` | — |
| `google/gemini-4-carbon-thinking` | `gemini4carbonthinking` | google | `true` | max | `unknown` | — |
| `google/gemini-neon` | `geminineon` | google | `true` | pro | `available` | 2026-11-19T21:12:06Z |
| `google/gemini-neon-thinking` | `geminineonthinking` | google | `true` | pro | `available` | 2026-11-19T21:12:12Z |
| `anthropic/claude-sonnet-5.5` | `claude55sonnet` | anthropic | `true` | pro | `available` | 2026-11-19T21:12:18Z |
| `anthropic/claude-sonnet-5.5-thinking` | `claude55sonnetthinking` | anthropic | `true` | pro | `available` | 2026-11-19T21:12:25Z |
| `anthropic/claude-opus-5.5` | `claude55opus` | anthropic | `true` | max | `available` | 2026-10-05T20:16:55.692021Z |
| `anthropic/claude-opus-5.5-thinking` | `claude55opusthinking` | anthropic | `true` | max | `available` | 2026-10-05T20:17:00.347130Z |
| `anthropic/claude-fable-5.2` | `claudefable52` | anthropic | `true` | max | `unknown` | — |
| `anthropic/claude-fable-5.2-thinking` | `claudefable52thinking` | anthropic | `true` | max | `unknown` | — |
| `moonshot/kimi-k3-thinking` | `kimik3thinking` | moonshot | `true` | pro | `available` | 2026-11-19T21:12:31Z |
| `z-ai/glm-5.3` | `glm_5_3_thinking` | z-ai | `true` | pro | `available` | 2026-11-19T21:12:37Z |
| `x-ai/grok-4.7` | `grok47` | x-ai | `true` | pro | `available` | 2026-11-19T21:12:43Z |
| `x-ai/grok-4.7-thinking` | `grok47thinking` | x-ai | `true` | pro | `available` | 2026-11-19T21:12:50Z |
| `nvidia/nemotron-3.5-super-vl-thinking` | `nv_nemotron_3_5_super` | nvidia | `true` | pro | `available` | 2026-11-19T21:12:56Z |
| `google/gemini-4-hydrogen` | `gemini4hydrogen` | google | `false` | pro | `available` | 2026-11-19T21:13:02Z |
| `google/gemini-4-hydrogen-thinking` | `gemini4hydrogenthinking` | google | `false` | pro | `available` | 2026-11-19T21:13:08Z |
| `openai/gpt-6.1-sol` | `gpt6_1_sol` | openai | `false` | pro | `available` | 2026-11-19T21:13:15Z |
| `openai/gpt-6.1-sol-thinking` | `gpt6_1_sol_thinking` | openai | `false` | pro | `available` | 2026-11-19T21:13:21Z |
| `openai/gpt-6-astra` | `gpt6_astra` | openai | `false` | max | `available` | 2026-10-05T20:16:31.992994Z |
| `openai/gpt-6-astra-thinking` | `gpt6_astra_thinking` | openai | `false` | max | `available` | 2026-10-05T20:16:35.921714Z |
| `google/gemini-3.8-flash` | `gemini38flash` | google | `false` | pro | `available` | 2026-11-19T21:13:27Z |
| `google/gemini-3.8-flash-thinking` | `gemini38flashthinking` | google | `false` | pro | `available` | 2026-11-19T21:13:33Z |
| `google/gemini-4-argon` | `gemini4argon` | google | `false` | max | `unknown` | — |
| `google/gemini-4-argon-thinking` | `gemini4argonthinking` | google | `false` | max | `unknown` | — |
| `anthropic/claude-fable-5.1` | `claudefable51` | anthropic | `false` | max | `available` | 2026-10-05T20:17:03.783203Z |
| `anthropic/claude-fable-5.1-thinking` | `claudefable51thinking` | anthropic | `false` | max | `available` | 2026-10-05T20:17:08.318815Z |
| `nvidia/nemotron-3-ultra-thinking` | `nv_nemotron_3_ultra` | nvidia | `false` | pro | `available` | 2026-11-19T21:13:40Z |
| `anthropic/claude-haiku-5.5` | `claude55haiku` | anthropic | `false` | pro | `available` | 2026-11-19T21:13:46Z |
| `anthropic/claude-haiku-5.5-thinking` | `claude55haikuthinking` | anthropic | `false` | pro | `available` | 2026-11-19T21:13:52Z |
| `openai/gpt-5.6-terra` | `gpt56_terra` | openai | `false` | pro | `available` | 2026-11-19T21:13:58Z |
| `openai/gpt-5.6-terra-thinking` | `gpt56_terra_thinking` | openai | `false` | pro | `available` | 2026-11-19T21:14:04Z |
| `openai/gpt-5.6-sol` | `gpt56_sol` | openai | `false` | max | `available` | 2026-10-05T20:17:44.686046Z |
| `openai/gpt-5.6-sol-thinking` | `gpt56_sol_thinking` | openai | `false` | max | `available` | 2026-10-05T20:17:49.336905Z |
| `anthropic/claude-sonnet-5` | `claude50sonnet` | anthropic | `false` | pro | `available` | 2026-11-19T21:14:10Z |
| `anthropic/claude-sonnet-5-thinking` | `claude50sonnetthinking` | anthropic | `false` | pro | `available` | 2026-11-19T21:14:16Z |
| `anthropic/claude-opus-5` | `claude50opus` | anthropic | `false` | max | `available` | 2026-10-05T20:18:00.987050Z |
| `anthropic/claude-opus-5-thinking` | `claude50opusthinking` | anthropic | `false` | max | `available` | 2026-10-05T20:18:05.096460Z |
| `x-ai/grok-4.6` | `grok46low` | x-ai | `false` | pro | `available` | 2026-11-19T21:14:22Z |
| `x-ai/grok-4.6-thinking` | `grok46medium` | x-ai | `false` | pro | `available` | 2026-11-19T21:14:28Z |
| `google/gemini-3.7-flash` | `gemini37flash` | google | `false` | pro | `available` | 2026-11-19T21:14:34Z |
| `google/gemini-3.7-flash-thinking` | `gemini37flashthinking` | google | `false` | pro | `available` | 2026-11-19T21:14:41Z |
| `perplexity/sonar-2` | `experimental` | perplexity | `false` | pro | `available` | 2026-11-19T21:14:47Z |
| `z-ai/glm-5.2` | `glm_5_2` | z-ai | `false` | pro | `available` | 2026-11-19T21:14:53Z |
| `google/gemini-3.1-pro-thinking-high` | `gemini31pro_high` | google | `false` | pro | `available` | 2026-11-19T21:14:59Z |
| `x-ai/grok-4.5` | `grok45low` | x-ai | `false` | pro | `available` | 2026-11-19T21:15:05Z |
| `x-ai/grok-4.5-thinking` | `grok45medium` | x-ai | `false` | pro | `available` | 2026-11-19T21:15:11Z |
| `anthropic/claude-opus-4.8` | `claude48opus` | anthropic | `false` | max | `available` | 2026-10-05T20:18:45.868241Z |
| `anthropic/claude-opus-4.8-thinking` | `claude48opusthinking` | anthropic | `false` | max | `available` | 2026-10-05T20:18:49.255021Z |
| `google/gemini-3.1-pro-thinking-low` | `gemini31pro_low` | google | `false` | pro | `available` | 2026-11-19T21:15:17Z |
| `moonshot/kimi-k2.6-instant` | `kimik26instant` | moonshot | `false` | pro | `available` | 2026-11-19T21:15:23Z |
| `moonshot/kimi-k2.6-thinking` | `kimik26thinking` | moonshot | `false` | pro | `available` | 2026-11-19T21:15:30Z |
| `nvidia/nemotron-3-super-thinking` | `nv_nemotron_3_super` | nvidia | `false` | pro | `available` | 2026-11-19T21:15:36Z |
| `openai/gpt-5.4` | `gpt54` | openai | `false` | pro | `available` | 2026-11-19T21:15:42Z |
| `openai/gpt-5.4-thinking` | `gpt54_thinking` | openai | `false` | pro | `available` | 2026-11-19T21:15:48Z |
| `openai/gpt-5.5-thinking` | `gpt55_thinking` | openai | `false` | max | `available` | 2026-10-05T20:19:39.220575Z |
| `anthropic/claude-opus-4.7` | `claude47opus` | anthropic | `false` | max | `available` | 2026-10-05T20:19:42.950685Z |
| `anthropic/claude-opus-4.7-thinking` | `claude47opusthinking` | anthropic | `false` | max | `available` | 2026-10-05T20:19:47.582690Z |
| `anthropic/claude-sonnet-4.6` | `claude46sonnet` | anthropic | `false` | pro | `available` | 2026-11-19T21:15:54Z |
| `anthropic/claude-sonnet-4.6-thinking` | `claude46sonnetthinking` | anthropic | `false` | pro | `available` | 2026-11-19T21:16:00Z |
| `openai/gpt4o` | `gpt4o` | openai | `false` | unknown | `available` | 2026-11-19T21:16:06Z |
| `openai/gpt41` | `gpt41` | openai | `false` | unknown | `available` | 2026-11-19T21:16:12Z |
| `openai/gpt5` | `gpt5` | openai | `false` | unknown | `available` | 2026-11-19T21:16:18Z |
| `openai/gpt5-thinking` | `gpt5_thinking` | openai | `false` | unknown | `available` | 2026-11-19T21:16:25Z |
| `openai/gpt51` | `gpt51` | openai | `false` | unknown | `available` | 2026-11-19T21:16:31Z |
| `openai/gpt51-thinking` | `gpt51_thinking` | openai | `false` | unknown | `available` | 2026-11-19T21:16:37Z |
| `openai/gpt51-low-thinking` | `gpt51_low_thinking` | openai | `false` | unknown | `available` | 2026-11-19T21:16:43Z |
| `openai/gpt5-mini` | `gpt5_mini` | openai | `false` | unknown | `available` | 2026-11-19T21:16:50Z |
| `openai/gpt5-nano` | `gpt5_nano` | openai | `false` | unknown | `available` | 2026-11-19T21:16:56Z |
| `openai/gpt5-pro` | `gpt5_pro` | openai | `false` | unknown | `available` | 2026-11-19T21:17:02Z |
| `openai/gpt52` | `gpt52` | openai | `false` | unknown | `available` | 2026-11-19T21:17:09Z |
| `openai/gpt52-thinking` | `gpt52_thinking` | openai | `false` | unknown | `available` | 2026-11-19T21:17:15Z |
| `openai/gpt52-pro` | `gpt52_pro` | openai | `false` | unknown | `available` | 2026-11-19T21:17:21Z |
| `openai/gpt55` | `gpt55` | openai | `false` | unknown | `available` | 2026-11-19T21:17:27Z |
| `anthropic/claude2` | `claude2` | anthropic | `false` | unknown | `available` | 2026-11-19T21:17:34Z |
| `anthropic/claude37sonnetthinking` | `claude37sonnetthinking` | anthropic | `false` | unknown | `available` | 2026-11-19T21:17:40Z |
| `anthropic/claude40sonnetthinking` | `claude40sonnetthinking` | anthropic | `false` | unknown | `available` | 2026-11-19T21:17:46Z |
| `google/gemini25pro` | `gemini25pro` | google | `false` | unknown | `available` | 2026-11-19T21:17:52Z |
| `google/gemini30pro` | `gemini30pro` | google | `false` | unknown | `available` | 2026-11-19T21:17:59Z |
| `google/gemini30flash` | `gemini30flash` | google | `false` | unknown | `available` | 2026-11-19T21:18:05Z |
| `google/gemini30flash-high` | `gemini30flash_high` | google | `false` | unknown | `available` | 2026-11-19T21:18:11Z |
| `google/gemini35flash` | `gemini35flash` | google | `false` | unknown | `available` | 2026-11-19T21:18:17Z |
| `google/gemini35flash-medium` | `gemini35flash_medium` | google | `false` | unknown | `available` | 2026-11-19T21:18:23Z |
| `google/gemini35flash-high` | `gemini35flash_high` | google | `false` | unknown | `available` | 2026-11-19T21:18:30Z |
| `x-ai/grok` | `grok` | x-ai | `false` | unknown | `available` | 2026-11-19T21:18:36Z |
| `anthropic/claude40opus` | `claude40opus` | anthropic | `false` | unknown | `available` | 2026-11-19T21:18:42Z |
| `anthropic/claude40opusthinking` | `claude40opusthinking` | anthropic | `false` | unknown | `available` | 2026-11-19T21:18:49Z |
| `anthropic/claude41opus` | `claude41opus` | anthropic | `false` | unknown | `available` | 2026-11-19T21:18:55Z |
| `anthropic/claude41opusthinking` | `claude41opusthinking` | anthropic | `false` | unknown | `available` | 2026-11-19T21:19:01Z |
| `anthropic/claude45opus` | `claude45opus` | anthropic | `false` | unknown | `available` | 2026-11-19T21:19:07Z |
| `anthropic/claude45opusthinking` | `claude45opusthinking` | anthropic | `false` | unknown | `available` | 2026-11-19T21:19:13Z |
| `anthropic/claude46opus` | `claude46opus` | anthropic | `false` | unknown | `available` | 2026-11-19T21:19:19Z |
| `anthropic/claude46opusthinking` | `claude46opusthinking` | anthropic | `false` | unknown | `available` | 2026-11-19T21:19:26Z |
| `anthropic/claude45sonnet` | `claude45sonnet` | anthropic | `false` | unknown | `available` | 2026-11-19T21:19:33Z |
| `anthropic/claude45sonnetthinking` | `claude45sonnetthinking` | anthropic | `false` | unknown | `available` | 2026-11-19T21:19:39Z |
| `anthropic/claude45haiku` | `claude45haiku` | anthropic | `false` | unknown | `unavailable` | 2026-11-19T21:19:44Z |
| `anthropic/claude45haikuthinking` | `claude45haikuthinking` | anthropic | `false` | unknown | `unavailable` | 2026-11-19T21:19:50Z |
| `moonshot/kimik2thinking` | `kimik2thinking` | moonshot | `false` | unknown | `available` | 2026-11-19T21:19:56Z |
| `moonshot/kimik25thinking` | `kimik25thinking` | moonshot | `false` | unknown | `available` | 2026-11-19T21:20:02Z |
| `x-ai/grok4` | `grok4` | x-ai | `false` | unknown | `available` | 2026-11-19T21:20:08Z |
| `x-ai/grok4nonthinking` | `grok4nonthinking` | x-ai | `false` | unknown | `available` | 2026-11-19T21:20:14Z |
| `x-ai/grok41reasoning` | `grok41reasoning` | x-ai | `false` | unknown | `available` | 2026-11-19T21:20:20Z |
| `x-ai/grok41nonreasoning` | `grok41nonreasoning` | x-ai | `false` | unknown | `available` | 2026-11-19T21:20:26Z |
| `openai/o4mini` | `o4mini` | openai | `false` | unknown | `available` | 2026-11-19T21:20:32Z |
| `openai/o3pro` | `o3pro` | openai | `false` | unknown | `available` | 2026-11-19T21:20:39Z |

<!-- END GENERATED MODEL CATALOG -->
