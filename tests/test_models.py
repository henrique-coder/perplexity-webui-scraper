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

    assert models
    assert all(model.status in {"available", "unknown", "unavailable"} for model in models)
    assert all(isinstance(model.is_official, bool) for model in models)
    assert all(model.last_tested_at is not None for model in models if model.status in {"available", "unavailable"})
    official_positions = [index for index, model in enumerate(models) if model.is_official]
    historical_positions = [index for index, model in enumerate(models) if not model.is_official]
    assert not historical_positions or max(official_positions) < min(historical_positions)
    assert len(ids) == len(set(ids))
    assert len(tool_names) == len(set(tool_names))
    assert all(model.id and model.identifier and model.tool_name for model in models)
    assert all(model.provider and model.description for model in models)


def test_model_rejects_unknown_fields() -> None:
    model_data = dict(_MODEL)
    model_data["unexpected"] = True

    with raises(ValidationError):
        Model.model_validate(model_data)


@mark.parametrize("timestamp", ["2026-07-20T23:34:21", "2026-07-21T02:34:21+03:00"])
def test_model_rejects_non_utc_test_timestamps(timestamp: str) -> None:
    with raises(ValidationError, match="last_tested_at must use UTC"):
        Model.model_validate({**_MODEL, "last_tested_at": timestamp})


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


def test_unknown_model_requires_acknowledgement() -> None:
    registry = ModelRegistry([{**_MODEL, "status": "unknown"}])

    with raises(ModelStatusError) as exc_info:
        registry.resolve_for_use("provider/model")

    assert exc_info.value.status == "unknown"

    with warns(ModelRiskWarning):
        model = registry.resolve_for_use("provider/model", allow_risky_model=True)
    assert model.identifier == "provider_model"


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
