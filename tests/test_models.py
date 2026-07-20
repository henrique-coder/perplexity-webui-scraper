from __future__ import annotations

from copy import deepcopy

from pydantic import ValidationError
from pytest import mark, raises, warns

from perplexity_webui_scraper import ModelRiskWarning, ModelStatusError
from perplexity_webui_scraper.models.registry import MODELS, ModelRegistry
from perplexity_webui_scraper.models.types import Model


_MODEL: dict[str, object] = {
    "id": "provider/model",
    "name": "Provider Model",
    "description": "A test model.",
    "identifier": "provider_model",
    "tool_name": "pplx_provider_model",
    "provider": "provider",
    "min_tier": "pro",
    "mode": "copilot",
}


def test_bundled_model_registry_is_valid() -> None:
    models = MODELS.list_all()
    ids = [model.id for model in models]
    tool_names = [model.tool_name for model in models]

    assert len(models) == 70
    assert sum(model.status == "available" for model in models) == 18
    assert sum(model.status == "unstable" for model in models) == 7
    assert sum(model.status == "unknown" for model in models) == 45
    assert not any(model.status == "unavailable" for model in models)
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
    assert MODELS.resolve("openai/gpt-5.6-terra").identifier == "gpt56_terra"
    assert MODELS.resolve("openai/gpt-5.6-terra").min_tier == "pro"
    assert MODELS.resolve("openai/gpt-5.6-sol").identifier == "gpt56_sol"
    assert MODELS.resolve("openai/gpt-5.6-sol").min_tier == "max"
    assert MODELS.resolve("anthropic/claude-sonnet-5").identifier == "claude50sonnet"
    assert MODELS.resolve("anthropic/claude-sonnet-5").min_tier == "pro"
    assert MODELS.resolve("anthropic/claude-opus-4.8").identifier == "claude48opus"
    assert MODELS.resolve("anthropic/claude-opus-4.8").min_tier == "max"
    assert MODELS.resolve("nvidia/nemotron-3-ultra-thinking").identifier == "nv_nemotron_3_ultra"
    assert MODELS.resolve("nvidia/nemotron-3-ultra-thinking").min_tier == "pro"
    assert MODELS.resolve("openai/gpt-5.4").tool_name == "pplx_gpt54"
    assert MODELS.resolve("anthropic/claude-sonnet-4.6-thinking").tool_name == "pplx_claude_s46_think"
    assert MODELS.resolve("openai/gpt-5.4").status == "unstable"
    assert MODELS.resolve("openai/gpt4o").status == "unknown"


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


@mark.parametrize("legacy_field", ["unstable", "disabled", "warning"])
def test_model_rejects_legacy_availability_fields(legacy_field: str) -> None:
    with raises(ValidationError):
        Model.model_validate({**_MODEL, legacy_field: True})


def test_unstable_model_requires_acknowledgement() -> None:
    with raises(ModelStatusError) as exc_info:
        MODELS.resolve_for_use("openai/gpt-5.4")
    assert exc_info.value.status == "unstable"

    with warns(ModelRiskWarning):
        model = MODELS.resolve_for_use("openai/gpt-5.4", allow_risky_model=True)
    assert model.identifier == "gpt54"


@mark.parametrize("status", ["unknown", "unavailable"])
def test_other_risky_statuses_use_the_same_acknowledgement(status: str) -> None:
    registry = ModelRegistry([{**_MODEL, "status": status}])
    with raises(ModelStatusError) as exc_info:
        registry.resolve_for_use("provider/model")
    assert exc_info.value.status == status
    with warns(ModelRiskWarning):
        assert registry.resolve_for_use("provider/model", allow_risky_model=True).status == status


def test_custom_model_is_explicit_and_validated() -> None:
    with raises(ModelStatusError):
        MODELS.resolve_for_use("custom:gpt57")
    with warns(ModelRiskWarning):
        model = MODELS.resolve_for_use(
            "custom:gpt57",
            allow_risky_model=True,
            custom_model_mode="search",
        )
    assert model.identifier == "gpt57"
    assert model.mode == "search"
    assert model.min_tier is None
    assert model.status == "unknown"
    with raises(ValueError, match="Custom model identifiers"):
        MODELS.resolve_for_use("custom:", allow_risky_model=True)
    with raises(ValueError, match="Unknown model"):
        MODELS.resolve_for_use("gpt57", allow_risky_model=True)
