from __future__ import annotations

from copy import deepcopy

from pydantic import ValidationError
from pytest import raises, warns

from perplexity_webui_scraper import DisabledModelError, ModelRiskWarning, UnstableModelError
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
    assert sum(not model.unstable for model in models) == 18
    assert sum(model.unstable for model in models) == 52
    assert sum(model.unstable and not model.disabled for model in models) == 7
    assert sum(model.disabled for model in models) == 45
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
    assert MODELS.resolve("openai/gpt4o").disabled is True


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


def test_disabled_model_metadata_requires_unstable_warning() -> None:
    invalid = dict(_MODEL, disabled=True)
    with raises(ValidationError, match="disabled models must also be unstable"):
        Model.model_validate(invalid)

    invalid = dict(_MODEL, unstable=True)
    with raises(ValidationError, match="must include a warning"):
        Model.model_validate(invalid)


def test_unstable_model_requires_acknowledgement() -> None:
    with raises(UnstableModelError):
        MODELS.resolve_for_use("openai/gpt-5.4")

    with warns(ModelRiskWarning):
        model = MODELS.resolve_for_use("openai/gpt-5.4", allow_unstable_model=True)
    assert model.identifier == "gpt54"


def test_disabled_model_requires_stronger_acknowledgement() -> None:
    disabled = dict(
        _MODEL,
        unstable=True,
        disabled=True,
        warning="Known unavailable.",
    )
    registry = ModelRegistry([disabled])
    with raises(DisabledModelError):
        registry.resolve_for_use("provider/model", allow_unstable_model=True)
    with warns(ModelRiskWarning):
        assert registry.resolve_for_use("provider/model", allow_disabled_model=True).disabled


def test_custom_model_is_explicit_and_validated() -> None:
    with raises(UnstableModelError):
        MODELS.resolve_for_use("custom:gpt57")
    with warns(ModelRiskWarning):
        model = MODELS.resolve_for_use(
            "custom:gpt57",
            allow_unstable_model=True,
            custom_model_mode="search",
        )
    assert model.identifier == "gpt57"
    assert model.mode == "search"
    assert model.min_tier is None
    with raises(ValueError, match="Custom model identifiers"):
        MODELS.resolve_for_use("custom:", allow_unstable_model=True)
    with raises(ValueError, match="Unknown model"):
        MODELS.resolve_for_use("gpt57", allow_unstable_model=True)
