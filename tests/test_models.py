from __future__ import annotations

from copy import deepcopy

from pydantic import ValidationError
from pytest import raises

from perplexity_webui_scraper.models.registry import MODELS, ModelRegistry
from perplexity_webui_scraper.models.types import Model


_MODEL: dict[str, object] = {
    "id": "provider/model",
    "name": "Provider Model",
    "description": "A test model.",
    "identifier": "provider_model",
    "tool_name": "pplx_provider_model",
    "min_tier": "pro",
    "mode": "copilot",
}


def test_bundled_model_registry_is_valid() -> None:
    models = MODELS.list_all()
    ids = [model.id for model in models]
    tool_names = [model.tool_name for model in models]

    assert models
    assert len(ids) == len(set(ids))
    assert len(tool_names) == len(set(tool_names))
    assert MODELS.resolve("perplexity/best").id == "perplexity/best"
    assert MODELS.resolve("perplexity/best").min_tier == "free"
    assert MODELS.resolve("perplexity/best").identifier == "turbo"
    assert MODELS.resolve("perplexity/best").identifier_by_tier["free"] == "turbo"
    assert MODELS.resolve("perplexity/best").identifier_by_tier["pro"] == "pplx_pro_upgraded"
    assert MODELS.resolve("perplexity/best").mode == "copilot"
    assert MODELS.resolve("perplexity/best").mode_by_tier["free"] == "copilot"
    assert MODELS.resolve("perplexity/best").mode_by_tier["pro"] == "copilot"


def test_model_rejects_unknown_fields() -> None:
    model_data = dict(_MODEL)
    model_data["unexpected"] = True

    with raises(ValidationError):
        Model.model_validate(model_data)


def test_model_registry_rejects_duplicate_ids() -> None:
    duplicate = deepcopy(_MODEL)
    duplicate["tool_name"] = "pplx_provider_model_other"

    with raises(ValueError, match="Duplicate model id"):
        ModelRegistry([_MODEL, duplicate])


def test_model_registry_rejects_duplicate_tool_names() -> None:
    duplicate = deepcopy(_MODEL)
    duplicate["id"] = "provider/other-model"

    with raises(ValueError, match="Duplicate MCP tool name"):
        ModelRegistry([_MODEL, duplicate])
