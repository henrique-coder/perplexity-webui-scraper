"""AI model definitions and registry."""

from __future__ import annotations

from pathlib import Path

import orjson
from pydantic import BaseModel, ConfigDict


class Model(BaseModel):
    """Immutable metadata for a single Perplexity AI model.

    Attributes:
        id: Canonical string key used to select this model (e.g. "openai/gpt-5.4").
        name: Human-readable display name.
        description: Short description of the model's characteristics.
        identifier: Internal Perplexity model identifier sent in the API payload.
        tool_name: MCP tool name used to register this model.
        min_tier: Minimum Perplexity subscription required: "pro" or "max".
        mode: API request mode (e.g. "copilot").
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str
    identifier: str
    tool_name: str
    min_tier: str
    mode: str = "copilot"


class ModelRegistry:
    """Registry of all available Perplexity AI models. Access via ``MODELS.resolve("model-id")``."""

    _models: dict[str, Model]

    def __init__(self) -> None:
        """Initialize the registry by loading models.json."""

        self._models = {}
        models_file = Path(__file__).parent / "models.json"

        if models_file.exists():
            data = orjson.loads(models_file.read_bytes())
            for item in data:
                model = Model.model_validate(item)
                self._models[model.id] = model

    def resolve(self, model_id: str) -> Model:
        """Look up a model by its string ID (e.g. ``"openai/gpt-5.4"``). Raises ``ValueError`` if not found."""

        if model_id in self._models:
            return self._models[model_id]

        available = ", ".join(f'"{m}"' for m in self._models)
        msg = f"Unknown model {model_id!r}. Available models: {available}"

        raise ValueError(msg)

    def _all(self) -> list[Model]:
        """Return all registered Model instances in definition order."""

        return list(self._models.values())


#: Singleton registry. Use ``MODELS.resolve("model-id")``.
MODELS: ModelRegistry = ModelRegistry()


def _resolve_model(model_id: str) -> Model:
    """Shim kept for internal callers. Prefer ``MODELS.resolve(model_id)``."""

    return MODELS.resolve(model_id)
