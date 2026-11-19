"""Tests for API discovery and per-credential client-cache behavior."""

from __future__ import annotations

from base64 import b64encode
from hashlib import sha256
from time import monotonic
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call, patch

from fastapi import HTTPException
from pytest import fixture, mark, raises, warns
from starlette.testclient import TestClient

from perplexity_webui_scraper._internal.constants import MAX_FILES, SESSION_COOKIE_PREFIX, SESSION_TOKEN_JWE_HEADER
from perplexity_webui_scraper._internal.exceptions import (
    AuthenticationError,
    ModelAccessError,
    ModelRiskWarning,
    ModelStatusError,
)
from perplexity_webui_scraper.api.app import app
from perplexity_webui_scraper.api.auth import AccountTierCache, ClientPool, account_tier_cache, client_pool
from perplexity_webui_scraper.api.helpers import (
    _JSON_SYSTEM_PROMPT,
    _MASTER_REMINDER_PROMPT,
    _MASTER_SYSTEM_PROMPT,
    build_query_and_files,
)
from perplexity_webui_scraper.api.routes.completions import _validate_model
from perplexity_webui_scraper.api.schemas import __all__ as api_schema_exports
from perplexity_webui_scraper.api.schemas.request import ChatCompletionRequest, ChatMessage
from perplexity_webui_scraper.auth.session_token import pack_session_token
from perplexity_webui_scraper.config.conversation import ConversationConfig
from perplexity_webui_scraper.core import Conversation
from perplexity_webui_scraper.models.registry import MODELS


if TYPE_CHECKING:
    from collections.abc import Generator

    from perplexity_webui_scraper.core.account import AccountTier


_SYNTHETIC_JWE = f"{SESSION_TOKEN_JWE_HEADER}..EBESExQVFhcYGRob.AQIDBAUGBw.MDEyMzQ1Njc4OTo7PD0-Pw"
TOKEN = f"{SESSION_COOKIE_PREFIX}123e4567-e89b-42d3-a456-426614174000={_SYNTHETIC_JWE}"
TOKEN_SECOND = f"{SESSION_COOKIE_PREFIX}223e4567-e89b-42d3-a456-426614174000={_SYNTHETIC_JWE}"


def _mock_conversation() -> MagicMock:
    conversation = MagicMock(spec=Conversation)
    conversation.uuid = "synthetic-thread"
    conversation.answer = "Mock answer"
    conversation.ask = MagicMock()
    return conversation


def _mock_profile_client(tier: AccountTier) -> MagicMock:
    profile = MagicMock()
    profile.account_tier = tier
    upstream = MagicMock()
    upstream.get_account_profile.return_value = profile

    return upstream


@fixture(autouse=True)
def _clear_auth_caches() -> Generator[None, None, None]:
    account_tier_cache.clear()
    client_pool._clients.clear()
    yield
    account_tier_cache.clear()
    client_pool._clients.clear()


@fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


def test_api_schema_exports_exclude_removed_chat_completion_contracts() -> None:
    assert {
        "ChatCompletionRequest",
        "ChatCompletionResponse",
        "ChatCompletionChunk",
        "ChatMessage",
        "PerplexityExtensions",
    } <= set(api_schema_exports)

    assert not {name for name in api_schema_exports if name.startswith("Responses")}
    assert "CoordinatesInput" not in api_schema_exports


def test_chat_completions_is_the_only_generation_route(client: TestClient) -> None:
    openapi = client.get("/openapi.json").json()

    assert "/v1/chat/completions" in openapi["paths"]
    assert "/v1/models" in openapi["paths"]
    assert "/v1/responses" not in openapi["paths"]
    assert client.post("/v1/responses", json={}).status_code == 404


def test_models_route_requires_authentication_and_lists_usable_models(client: TestClient) -> None:
    unauthenticated = client.get("/v1/models")

    assert unauthenticated.status_code == 401

    upstream = _mock_profile_client("max")

    with patch("perplexity_webui_scraper.api.routes.models.client_pool.get_or_create", return_value=upstream):
        response = client.get("/v1/models", headers={"Authorization": f"Bearer {TOKEN}"})

    assert response.status_code == 200
    assert response.json()["object"] == "list"


def test_chat_request_body_limit_does_not_affect_model_listing(client: TestClient) -> None:
    upstream = _mock_profile_client("max")

    with patch("perplexity_webui_scraper.api.routes.models.client_pool.get_or_create", return_value=upstream):
        response = client.get(
            "/v1/models",
            headers={"Authorization": f"Bearer {TOKEN}", "Content-Length": str(10 * 1024 * 1024 + 1)},
        )

    assert response.status_code == 200


def test_missing_auth_header_returns_401(client: TestClient) -> None:
    response = client.post(
        "/v1/chat/completions",
        json={"model": "perplexity/best", "messages": [{"role": "user", "content": "Hello"}]},
    )

    assert response.status_code == 401
    assert "Missing or invalid Authorization header" in response.json()["error"]["message"]
    assert "[MASKED_SENSITIVE_DATA]" not in response.text
    assert "wsk_" in response.json()["error"]["message"]
    assert "__Secure-pplx.session.<account UUID>=value" in response.json()["error"]["message"]


def test_chat_request_validation_does_not_echo_private_values(client: TestClient) -> None:
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "perplexity/best",
            "messages": [{"role": "user", "content": {"private": "do-not-reflect"}}],
        },
        headers={"Authorization": f"Bearer {TOKEN}"},
    )

    assert response.status_code == 422
    assert "do-not-reflect" not in response.text


def test_chat_request_body_limit_rejects_large_body(client: TestClient) -> None:
    response = client.post(
        "/v1/chat/completions",
        content=b" " * (10 * 1024 * 1024 + 1),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )

    assert response.status_code == 413


def test_api_key_without_session_token_is_misconfigured(client: TestClient) -> None:
    with (
        patch.dict("os.environ", {"PERPLEXITY_API_KEY": "custom-secret"}, clear=True),
        patch("perplexity_webui_scraper.api.auth.client_pool.get_or_create") as get_client,
    ):
        response = client.post(
            "/v1/chat/completions",
            json={"model": "perplexity/best", "messages": [{"role": "user", "content": "Hello"}]},
            headers={"Authorization": "Bearer custom-secret"},
        )

    assert response.status_code == 503
    get_client.assert_not_called()


def test_server_default_token_without_api_key_runs_passwordless(client: TestClient) -> None:
    conversation = _mock_conversation()
    upstream = _mock_profile_client("pro")
    upstream.create_conversation.return_value = conversation

    with (
        patch.dict("os.environ", {"PERPLEXITY_SESSION_TOKEN": TOKEN}, clear=True),
        patch("perplexity_webui_scraper.api.auth.client_pool.get_or_create", return_value=upstream) as get_client,
    ):
        models_no_auth = client.get("/v1/models")
        models_dummy = client.get("/v1/models", headers={"Authorization": "Bearer placeholder"})
        chat_no_auth = client.post(
            "/v1/chat/completions",
            json={"model": "perplexity/best", "messages": [{"role": "user", "content": "Hello"}]},
        )

    assert models_no_auth.status_code == 200
    assert models_dummy.status_code == 200
    assert chat_no_auth.status_code == 200
    assert chat_no_auth.json()["choices"][0]["message"]["content"] == "Mock answer"
    assert get_client.call_args_list == [call(TOKEN), call(TOKEN)]
    upstream.get_account_profile.assert_called_once()


def test_server_default_token_and_api_key_require_bearer_api_key(client: TestClient) -> None:
    conversation = _mock_conversation()
    upstream = _mock_profile_client("pro")
    upstream.create_conversation.return_value = conversation

    with (
        patch.dict("os.environ", {"PERPLEXITY_SESSION_TOKEN": TOKEN, "PERPLEXITY_API_KEY": "gateway-key"}, clear=True),
        patch("perplexity_webui_scraper.api.auth.client_pool.get_or_create", return_value=upstream) as get_client,
    ):
        models_response = client.get("/v1/models", headers={"Authorization": "Bearer gateway-key"})
        chat_response = client.post(
            "/v1/chat/completions",
            json={"model": "perplexity/best", "messages": [{"role": "user", "content": "Hello"}]},
            headers={"Authorization": "bearer gateway-key"},
        )

    assert models_response.status_code == 200
    assert chat_response.status_code == 200
    assert get_client.call_args_list == [call(TOKEN), call(TOKEN)]
    upstream.get_account_profile.assert_called_once()
    upstream.create_conversation.assert_called_once()


def test_gateway_key_rejects_missing_wrong_or_x_api_key_before_client_creation(client: TestClient) -> None:
    with (
        patch.dict("os.environ", {"PERPLEXITY_SESSION_TOKEN": TOKEN, "PERPLEXITY_API_KEY": "expected"}, clear=True),
        patch("perplexity_webui_scraper.api.auth.client_pool.get_or_create") as get_client,
    ):
        missing_auth = client.post(
            "/v1/chat/completions",
            json={"model": "perplexity/best", "messages": [{"role": "user", "content": "Hello"}]},
        )
        wrong_bearer = client.get("/v1/models", headers={"Authorization": "Bearer wrong"})
        x_api_only = client.get("/v1/models", headers={"X-API-Key": "expected"})

    assert missing_auth.status_code == 401
    assert wrong_bearer.status_code == 401
    assert x_api_only.status_code == 401
    get_client.assert_not_called()


def test_direct_auth_accepts_compact_and_raw_bearer_and_rejects_x_api_key_only(client: TestClient) -> None:
    compact = pack_session_token(TOKEN)
    upstream = _mock_profile_client("free")
    conversation = _mock_conversation()
    upstream.create_conversation.return_value = conversation

    with (
        patch.dict("os.environ", {}, clear=True),
        patch("perplexity_webui_scraper.api.auth.client_pool.get_or_create", return_value=upstream),
    ):
        lower_compact = client.get("/v1/models", headers={"Authorization": f"bearer   {compact} "})
        raw_chat = client.post(
            "/v1/chat/completions",
            json={"model": "perplexity/best", "messages": [{"role": "user", "content": "Hello"}]},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
        x_api_only = client.get("/v1/models", headers={"X-API-Key": compact})

    assert lower_compact.status_code == 200
    assert raw_chat.status_code == 200
    assert x_api_only.status_code == 401
    upstream.get_account_profile.assert_called_once()
    upstream.create_conversation.assert_called_once()


def test_invalid_caller_credential_is_not_reflected(client: TestClient) -> None:
    response = client.post(
        "/v1/chat/completions",
        json={"model": "perplexity/best", "messages": [{"role": "user", "content": "Hello"}]},
        headers={"Authorization": "Bearer private-invalid-credential"},
    )

    assert response.status_code == 401
    assert "private-invalid-credential" not in response.text


def test_invalid_compact_bearer_token_returns_401_without_leaking(client: TestClient) -> None:
    response = client.post(
        "/v1/chat/completions",
        json={"model": "perplexity/best", "messages": [{"role": "user", "content": "Hello"}]},
        headers={"Authorization": "Bearer wsk_invalid_compact_token"},
    )

    assert response.status_code == 401
    assert "wsk_invalid_compact_token" not in response.text


def test_server_default_credential_is_not_reflected(client: TestClient) -> None:
    with (
        patch.dict("os.environ", {"PERPLEXITY_SESSION_TOKEN": "private-server-value"}, clear=True),
        patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create") as get_client,
    ):
        response = client.post(
            "/v1/chat/completions",
            json={"model": "perplexity/best", "messages": [{"role": "user", "content": "Hello"}]},
        )

    assert response.status_code == 503
    assert "private-server-value" not in response.text
    get_client.assert_not_called()


def test_client_pool_returns_same_client_for_aliased_credentials() -> None:
    client_instance = MagicMock()
    compact = pack_session_token(TOKEN)

    with patch("perplexity_webui_scraper.api.auth.Perplexity", return_value=client_instance) as create_client:
        pool = ClientPool(max_clients=2)
        assert pool.get_or_create(TOKEN) is client_instance
        assert pool.get_or_create(compact) is client_instance

    create_client.assert_called_once()


def test_model_validation_maps_unknown_and_invalid_custom_models() -> None:
    with raises(HTTPException, match="Unknown model"):
        _validate_model(
            ChatCompletionRequest.model_validate(
                {"model": "unknown-model", "messages": [{"role": "user", "content": "x"}]}
            )
        )

    with raises(HTTPException, match="Invalid custom model identifier"):
        _validate_model(
            ChatCompletionRequest.model_validate(
                {
                    "model": "custom:",
                    "messages": [{"role": "user", "content": "x"}],
                    "perplexity": {"allow_risky_model": True},
                }
            )
        )


def test_model_risk_requires_explicit_acknowledgement_in_api() -> None:
    request = ChatCompletionRequest.model_validate(
        {"model": "custom:gpt57", "messages": [{"role": "user", "content": "x"}]}
    )

    with raises(ModelStatusError):
        _validate_model(request)

    request = ChatCompletionRequest.model_validate(
        {
            "model": "custom:gpt57",
            "messages": [{"role": "user", "content": "x"}],
            "perplexity": {"allow_risky_model": True},
        }
    )
    with warns(ModelRiskWarning):
        _validate_model(request)


def test_model_status_is_not_skipped_by_api_model_validation(client: TestClient) -> None:
    with patch(
        "perplexity_webui_scraper.api.routes.completions.MODELS.resolve_for_use",
        side_effect=ModelStatusError("x", "unknown", "x"),
    ):
        response = client.post(
            "/v1/chat/completions",
            json={"model": "perplexity/best", "messages": [{"role": "user", "content": "Hello"}]},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )

    assert response.status_code == 400
    assert "model_status_confirmation_required" in response.text


def test_model_access_errors_use_safe_openai_error_shape(client: TestClient) -> None:
    with patch(
        "perplexity_webui_scraper.api.routes.completions._validate_model",
        side_effect=ModelAccessError("x", "max", "free"),
    ):
        response = client.post(
            "/v1/chat/completions",
            json={"model": "perplexity/best", "messages": [{"role": "user", "content": "Hello"}]},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )

    assert response.status_code == 403
    assert "model_access_denied" in response.text
    assert "x" in response.text


def test_api_does_not_allow_cross_origin_requests(client: TestClient) -> None:
    upstream = _mock_profile_client("free")

    with patch("perplexity_webui_scraper.api.routes.models.client_pool.get_or_create", return_value=upstream):
        response = client.get(
            "/v1/models",
            headers={"Authorization": f"Bearer {TOKEN}", "Origin": "https://attacker.example"},
        )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_model_catalog_exposes_registry_metadata(client: TestClient) -> None:
    upstream = _mock_profile_client("max")

    with patch("perplexity_webui_scraper.api.routes.models.client_pool.get_or_create", return_value=upstream):
        response = client.get("/v1/models", headers={"Authorization": f"Bearer {TOKEN}"})

    assert response.status_code == 200
    data = response.json()["data"]
    expected = {model.id: model for model in MODELS.list_all() if model.status != "unavailable"}
    assert {item["id"] for item in data} == set(expected)

    for item in data:
        model = expected[item["id"]]
        metadata = item["perplexity"]
        expected_tested_at = model.last_tested_at.isoformat().replace("+00:00", "Z") if model.last_tested_at else None
        assert item["owned_by"] == model.provider
        assert metadata["min_tier"] == model.min_tier
        assert metadata["is_official"] == model.is_official
        assert metadata["status"] == model.status
        assert metadata["last_tested_at"] == expected_tested_at


def test_models_route_filters_models_by_account_tier(client: TestClient) -> None:
    unknown_min_tier_ids = {
        model.id for model in MODELS.list_all() if model.status != "unavailable" and model.min_tier == "unknown"
    }
    assert unknown_min_tier_ids

    free_ids = {model.id for model in MODELS.list_all() if model.status != "unavailable" and model.min_tier == "free"}
    tier_expectations: dict[AccountTier, set[str]] = {
        "unknown": free_ids,
        "free": free_ids,
        "pro": {
            model.id
            for model in MODELS.list_all()
            if model.status != "unavailable" and model.min_tier in {"free", "pro", "unknown"}
        },
        "max": {model.id for model in MODELS.list_all() if model.status != "unavailable"},
    }

    for tier, expected_ids in tier_expectations.items():
        account_tier_cache.clear()
        upstream = _mock_profile_client(tier)

        with patch("perplexity_webui_scraper.api.routes.models.client_pool.get_or_create", return_value=upstream):
            response = client.get("/v1/models", headers={"Authorization": f"Bearer {TOKEN}"})

        assert response.status_code == 200
        returned_ids = {item["id"] for item in response.json()["data"]}
        assert returned_ids == expected_ids

        if tier in {"unknown", "free"}:
            assert returned_ids.isdisjoint(unknown_min_tier_ids)
        else:
            assert unknown_min_tier_ids <= returned_ids


def test_models_route_caches_account_tier_and_supports_gateway_auth(client: TestClient) -> None:
    upstream = _mock_profile_client("pro")

    with (
        patch.dict("os.environ", {"PERPLEXITY_SESSION_TOKEN": TOKEN, "PERPLEXITY_API_KEY": "gateway-key"}, clear=True),
        patch("perplexity_webui_scraper.api.routes.models.client_pool.get_or_create", return_value=upstream),
    ):
        first = client.get("/v1/models", headers={"Authorization": "Bearer gateway-key"})
        second = client.get("/v1/models", headers={"Authorization": "Bearer gateway-key"})

    assert first.status_code == 200
    assert second.status_code == 200
    upstream.get_account_profile.assert_called_once()

    account_tier_cache.clear()
    upstream.get_account_profile.side_effect = AuthenticationError("expired")

    with (
        patch.dict("os.environ", {"PERPLEXITY_SESSION_TOKEN": TOKEN, "PERPLEXITY_API_KEY": "gateway-key"}, clear=True),
        patch("perplexity_webui_scraper.api.routes.models.client_pool.get_or_create", return_value=upstream),
    ):
        rejected = client.get("/v1/models", headers={"Authorization": "Bearer gateway-key"})

    assert rejected.status_code == 401
    assert account_tier_cache.get(TOKEN) is None


def test_account_tier_cache_hashes_tokens_expires_entries_and_caps_capacity() -> None:
    with raises(ValueError, match="at least one"):
        AccountTierCache(max_entries=0)

    with raises(ValueError, match="greater than zero"):
        AccountTierCache(ttl_seconds=0)

    cache = AccountTierCache(max_entries=1, ttl_seconds=600)
    compact = pack_session_token(TOKEN)
    cache.set(TOKEN, "pro")

    assert TOKEN not in cache._entries
    assert sha256(TOKEN.encode("utf-8")).hexdigest() in cache._entries
    assert cache.get(compact) == "pro"

    cache.set(TOKEN_SECOND, "max")
    assert cache.get(TOKEN) is None
    assert cache.get(TOKEN_SECOND) == "max"

    key = cache._key(TOKEN_SECOND)
    cache._entries[key] = ("max", monotonic() - cache._ttl_seconds - 1.0)
    assert cache.get(TOKEN_SECOND) is None


def test_client_pool_evicts_oldest_client_at_capacity() -> None:
    first = MagicMock()
    second = MagicMock()

    with patch("perplexity_webui_scraper.api.auth.Perplexity", side_effect=[first, second]):
        pool = ClientPool(max_clients=1)
        assert pool.get_or_create(TOKEN) is first
        assert pool.get_or_create(TOKEN_SECOND) is second

    first.close.assert_called_once()
    assert TOKEN not in pool._clients
    assert pool.get_or_create(TOKEN_SECOND) is second


def test_client_pool_enforces_positive_capacity_and_ttl() -> None:
    with raises(ValueError, match="at least one"):
        ClientPool(max_clients=0)

    with raises(ValueError, match="greater than zero"):
        ClientPool(ttl_seconds=0)


def test_client_pool_releases_lock_when_client_creation_fails() -> None:
    with patch(
        "perplexity_webui_scraper.api.auth.Perplexity",
        side_effect=RuntimeError("construction failed"),
    ):
        pool = ClientPool()
        with raises(RuntimeError, match="construction failed"):
            pool.get_or_create(TOKEN)

    client_instance = MagicMock()
    with patch("perplexity_webui_scraper.api.auth.Perplexity", return_value=client_instance):
        assert pool.get_or_create(TOKEN) is client_instance


def test_client_pool_reuses_raw_and_compact_credentials_for_one_session() -> None:
    client_instance = MagicMock()
    compact = pack_session_token(TOKEN)

    with patch("perplexity_webui_scraper.api.auth.Perplexity", return_value=client_instance) as create_client:
        pool = ClientPool(max_clients=2)
        assert pool.get_or_create(TOKEN) is client_instance
        assert pool.get_or_create(compact) is client_instance

    create_client.assert_called_once()


def test_client_pool_expires_idle_clients() -> None:
    client_instance = MagicMock()

    with patch("perplexity_webui_scraper.api.auth.Perplexity", return_value=client_instance):
        pool = ClientPool(max_clients=2, ttl_seconds=0.001)
        assert pool.get_or_create(TOKEN) is client_instance
        pool._clients[TOKEN] = (client_instance, monotonic() - pool._ttl_seconds - 1.0)
        pool.get_or_create(TOKEN_SECOND)

    client_instance.close.assert_called_once()
    assert TOKEN not in pool._clients


def test_rest_coordinates_reach_conversation_config_and_reject_invalid_values(client: TestClient) -> None:
    conversation = _mock_conversation()
    upstream = MagicMock()
    upstream.create_conversation.return_value = conversation

    with patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create", return_value=upstream):
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "perplexity/best",
                "messages": [{"role": "user", "content": "Weather here?"}],
                "perplexity": {"latitude": -23.5, "longitude": -46.6},
            },
            headers={"Authorization": f"Bearer {TOKEN}"},
        )

    assert response.status_code == 200
    config = upstream.create_conversation.call_args.args[0]
    assert isinstance(config, ConversationConfig)
    assert config.latitude == -23.5
    assert config.longitude == -46.6

    for invalid_perplexity in (
        {"latitude": -23.5},
        {"longitude": -46.6},
        {"latitude": 91.0, "longitude": 0.0},
        {"latitude": 0.0, "longitude": -181.0},
    ):
        invalid_response = client.post(
            "/v1/chat/completions",
            json={
                "model": "perplexity/best",
                "messages": [{"role": "user", "content": "Weather here?"}],
                "perplexity": invalid_perplexity,
            },
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
        assert invalid_response.status_code == 422


def test_chat_completion_decodes_valid_image_data_urls_and_skips_remote_urls(client: TestClient) -> None:
    conversation = _mock_conversation()
    upstream = MagicMock()
    upstream.create_conversation.return_value = conversation
    png_bytes = b"\x89PNG\r\n\x1a\n"
    svg_bytes = b"<svg></svg>"
    png_url = f"data:image/png;base64,{b64encode(png_bytes).decode('ascii')}"
    svg_url = f"data:image/svg+xml;base64,{b64encode(svg_bytes).decode('ascii')}"

    with patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create", return_value=upstream):
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "perplexity/best",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Inspect"},
                            {"type": "image_url", "image_url": {"url": png_url}},
                            {"type": "image_url", "image_url": {"url": svg_url}},
                            {"type": "image_url", "image_url": {"url": "https://attacker.example/remote.png"}},
                        ],
                    }
                ],
            },
            headers={"Authorization": f"Bearer {TOKEN}"},
        )

    assert response.status_code == 200
    assert conversation.ask.call_args.kwargs["files"] == [
        (png_bytes, "image.png", "image/png"),
        (svg_bytes, "image.svg", "image/svg+xml"),
    ]


@mark.parametrize(
    "invalid_url",
    [
        "data:image/png,AAAA",
        "data:text/html;base64,PGh0bWw+",
        "data:;base64,AAAA",
        "data:image/png;base64",
        "data:image/png;base64,",
        "data:image/png;base64,AAA",
        "data:image/png;base64,AA!A",
        "data:image/png;base64,AA AA",
        "data:image/png;base64,AB==",
        "data:image/png;charset=utf-8;base64,AAAA",
        "DATA:image/png;base64,AAAA",
    ],
)
def test_chat_completion_rejects_malformed_image_data_urls_with_422(client: TestClient, invalid_url: str) -> None:
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "perplexity/best",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "image_url", "image_url": {"url": invalid_url}}],
                }
            ],
        },
        headers={"Authorization": f"Bearer {TOKEN}"},
    )

    assert response.status_code == 422
    assert invalid_url not in response.text


def test_image_data_url_size_limit_rejects_before_base64_decode(client: TestClient) -> None:
    oversized_b64 = "A" * (((10 * 1024 * 1024 + 3) // 3) * 4)

    with (
        patch("perplexity_webui_scraper.api.schemas.request.b64decode", side_effect=AssertionError("must not decode")),
        raises(ValueError, match="maximum allowed size"),
    ):
        ChatCompletionRequest.model_validate(
            {
                "model": "perplexity/best",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{oversized_b64}"}}
                        ],
                    }
                ],
            }
        )

    with (
        patch("perplexity_webui_scraper.api.schemas.request.MAX_IMAGE_BYTES", 3),
        patch("perplexity_webui_scraper.api.schemas.request.b64decode", side_effect=AssertionError("must not decode")),
    ):
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "perplexity/best",
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAAAAAA"}}],
                    }
                ],
            },
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
        with raises(ValueError, match="maximum allowed size"):
            ChatMessage(
                role="user",
                content=[{"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAAAAAA"}}],
            ).image_bytes()

    assert response.status_code == 422


def test_chat_completion_rejects_excess_image_attachments_with_422(client: TestClient) -> None:
    parts = [{"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}} for _ in range(MAX_FILES + 1)]
    response = client.post(
        "/v1/chat/completions",
        json={"model": "perplexity/best", "messages": [{"role": "user", "content": parts}]},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )

    assert response.status_code == 422


def test_build_query_and_files_prepends_master_prompt_and_preserves_system_order() -> None:
    request = ChatCompletionRequest.model_validate(
        {
            "model": "perplexity/best",
            "messages": [
                {"role": "system", "content": "First system instruction"},
                {"role": "developer", "content": "Second developer instruction"},
                {"role": "user", "content": "Earlier question"},
                {"role": "assistant", "content": "Earlier answer"},
                {"role": "user", "content": "What is TLS 1.3?"},
            ],
            "perplexity": {"response_format": "json_object"},
        }
    )

    query, files = build_query_and_files(request)

    assert files == []
    assert query == "\n\n".join(
        [
            _MASTER_SYSTEM_PROMPT,
            _JSON_SYSTEM_PROMPT,
            "<client_context>\nFirst system instruction\n\nSecond developer instruction\n</client_context>",
            "<conversation_history>\n[User]: Earlier question\n\n[Assistant]: Earlier answer\n</conversation_history>",
            "<user_query>\nWhat is TLS 1.3?\n</user_query>",
            _MASTER_REMINDER_PROMPT,
        ]
    )


def test_chat_completion_forwards_master_prompt_even_with_agent_fields(client: TestClient) -> None:
    conversation = _mock_conversation()
    upstream = MagicMock()
    upstream.create_conversation.return_value = conversation

    with patch("perplexity_webui_scraper.api.routes.completions._client_pool.get_or_create", return_value=upstream):
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "perplexity/best",
                "messages": [
                    {"role": "system", "content": "Act as Hermes autonomous CLI agent"},
                    {"role": "user", "content": "Who won the 2026 Nobel Prize in Physics?"},
                ],
                "tools": [{"type": "function", "function": {"name": "run_shell", "parameters": {}}}],
                "tool_choice": "auto",
            },
            headers={"Authorization": f"Bearer {TOKEN}"},
        )

    assert response.status_code == 200
    forwarded_query = conversation.ask.call_args.args[0]
    assert forwarded_query.startswith(_MASTER_SYSTEM_PROMPT)
    assert "<client_context>\nAct as Hermes autonomous CLI agent\n</client_context>" in forwarded_query
    assert "<user_query>\nWho won the 2026 Nobel Prize in Physics?\n</user_query>" in forwarded_query
    assert forwarded_query.endswith(_MASTER_REMINDER_PROMPT)
    assert forwarded_query.index(_MASTER_SYSTEM_PROMPT) < forwarded_query.index("Act as Hermes autonomous CLI agent")
    assert forwarded_query.index("Who won the 2026 Nobel Prize in Physics?") < forwarded_query.index(
        _MASTER_REMINDER_PROMPT
    )
