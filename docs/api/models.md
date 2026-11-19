# Model registry

`ModelRegistry` loads the bundled `_static/models.json` catalog and resolves model IDs, operational status, and account-tier metadata. Import the singleton `MODELS` registry directly from `perplexity_webui_scraper`.

```python
from perplexity_webui_scraper import MODELS

model = MODELS.resolve("perplexity/best")
all_models = MODELS.list_all()
```

## `Model`

Frozen metadata entry describing a registered or custom Perplexity model.

| Field                | Type                         | Default     | Description                                                                            |
| -------------------- | ---------------------------- | ----------- | -------------------------------------------------------------------------------------- |
| `id`                 | `str`                        | —           | Canonical model ID (e.g. `"perplexity/best"`).                                         |
| `name`               | `str`                        | —           | Human-readable display name.                                                           |
| `description`        | `str`                        | —           | Short summary of the model's characteristics.                                          |
| `identifier`         | `str`                        | —           | Default internal Perplexity model identifier sent in the request payload.              |
| `identifier_by_tier` | `dict[ModelTier, str]`       | `{}`        | Optional tier-specific internal identifier overrides (e.g. `"free"` vs. `"pro"`).      |
| `tool_name`          | `str`                        | —           | MCP tool name registered for this model (e.g. `"pplx_best"`).                          |
| `provider`           | `str`                        | —           | Provider slug (`"perplexity"`, `"openai"`, `"anthropic"`, `"google"`, `"x-ai"`, etc.). |
| `min_tier`           | `ModelTier \| None`          | —           | Minimum required Perplexity tier (`"free"`, `"pro"`, `"max"`), or `None` when unknown. |
| `is_official`        | `bool`                       | `False`     | Whether Perplexity currently lists the model in the official WebUI picker.             |
| `mode`               | `ModelMode`                  | `"copilot"` | Default internal request mode (`"copilot"`, `"search"`, or `"research"`).              |
| `mode_by_tier`       | `dict[ModelTier, ModelMode]` | `{}`        | Optional tier-specific mode overrides.                                                 |
| `status`             | `ModelStatus`                | `"unknown"` | Operational status: `"available"`, `"unknown"`, or `"unavailable"`.                    |
| `last_tested_at`     | `datetime \| None`           | `None`      | UTC timestamp of the last conclusive test, or `None` when untested.                    |

## `ModelRegistry`

| Method                                                                               | Returns       | Description                                                                                                       |
| ------------------------------------------------------------------------------------ | ------------- | ----------------------------------------------------------------------------------------------------------------- |
| `resolve(model_id)`                                                                  | `Model`       | Look up a registered model by ID or raise `ValueError`.                                                           |
| `list_all()`                                                                         | `list[Model]` | Return all catalog models in definition order.                                                                    |
| `resolve_for_use(model_id, *, allow_risky_model=False, custom_model_mode="copilot")` | `Model`       | Resolve a catalog or `custom:<identifier>` model, raising `ModelStatusError` if non-available and unacknowledged. |

## `Model`

Frozen metadata entry describing a registered or custom Perplexity model.

| Field                | Type                         | Default     | Description                                                                            |
| -------------------- | ---------------------------- | ----------- | -------------------------------------------------------------------------------------- |
| `id`                 | `str`                        | —           | Canonical model ID (e.g. `"perplexity/best"`).                                         |
| `name`               | `str`                        | —           | Human-readable display name.                                                           |
| `description`        | `str`                        | —           | Short summary of the model's characteristics.                                          |
| `identifier`         | `str`                        | —           | Default internal Perplexity model identifier sent in the request payload.              |
| `identifier_by_tier` | `dict[ModelTier, str]`       | `{}`        | Optional tier-specific internal identifier overrides (e.g. `"free"` vs. `"pro"`).      |
| `tool_name`          | `str`                        | —           | MCP tool name registered for this model (e.g. `"pplx_best"`).                          |
| `provider`           | `str`                        | —           | Provider slug (`"perplexity"`, `"openai"`, `"anthropic"`, `"google"`, `"x-ai"`, etc.). |
| `min_tier`           | `ModelTier \| None`          | —           | Minimum required Perplexity tier (`"free"`, `"pro"`, `"max"`), or `None` when unknown. |
| `is_official`        | `bool`                       | `False`     | Whether Perplexity currently lists the model in the official WebUI picker.             |
| `mode`               | `ModelMode`                  | `"copilot"` | Default internal request mode (`"copilot"`, `"search"`, or `"research"`).              |
| `mode_by_tier`       | `dict[ModelTier, ModelMode]` | `{}`        | Optional tier-specific mode overrides.                                                 |
| `status`             | `ModelStatus`                | `"unknown"` | Operational status: `"available"`, `"unknown"`, or `"unavailable"`.                    |
| `last_tested_at`     | `datetime \| None`           | `None`      | UTC timestamp of the last conclusive test, or `None` when untested.                    |

## `ModelRegistry`

| Method                                                                               | Returns       | Description                                                                                                       |
| ------------------------------------------------------------------------------------ | ------------- | ----------------------------------------------------------------------------------------------------------------- |
| `resolve(model_id)`                                                                  | `Model`       | Look up a registered model by ID or raise `ValueError`.                                                           |
| `list_all()`                                                                         | `list[Model]` | Return all catalog models in definition order.                                                                    |
| `resolve_for_use(model_id, *, allow_risky_model=False, custom_model_mode="copilot")` | `Model`       | Resolve a catalog or `custom:<identifier>` model, raising `ModelStatusError` if non-available and unacknowledged. |
