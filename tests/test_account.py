from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from pytest import raises, warns

from perplexity_webui_scraper._internal.constants import ENDPOINT_AUTH_SESSION, ENDPOINT_USER_SETTINGS
from perplexity_webui_scraper._internal.exceptions import FileAccessError, ModelAccessError, ModelRiskWarning
from perplexity_webui_scraper.config.conversation import ConversationConfig
from perplexity_webui_scraper.core.account import (
    AccountSession,
    AccountSettings,
    ensure_model_access,
)
from perplexity_webui_scraper.core.client import Perplexity
from perplexity_webui_scraper.core.conversation import Conversation
from perplexity_webui_scraper.models.registry import MODELS


if TYPE_CHECKING:
    from perplexity_webui_scraper.http.client import HTTPClient


class _SessionResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeHTTP:
    def __init__(self, payload: dict[str, Any], settings_payload: dict[str, Any] | None = None) -> None:
        self.payload = payload
        self.settings_payload = settings_payload
        self.get_calls: list[tuple[str, bool]] = []
        self.stream_called = False
        self.ask_payload: dict[str, Any] | None = None

    def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        rate_limited: bool = True,
    ) -> _SessionResponse:
        self.get_calls.append((endpoint, rate_limited))
        if endpoint == ENDPOINT_USER_SETTINGS and self.settings_payload is not None:
            return _SessionResponse(self.settings_payload)

        return _SessionResponse(self.payload)

    def init_search(self, query: str) -> None:
        return None

    def stream_ask(self, payload: dict[str, Any]):
        self.stream_called = True
        self.ask_payload = payload
        yield b""


def _session_payload(subscription_tier: str, payment_tier: str = "free_with_pm") -> dict[str, Any]:
    return {
        "expires": "2026-07-30T02:59:58.715563094Z",
        "preventUsernameRedirect": False,
        "user": {
            "email": "user@example.com",
            "id": "user-id",
            "payment_tier": payment_tier,
            "subscription_status": "active",
            "subscription_tier": subscription_tier,
            "username": "user",
        },
    }


def _free_session_payload() -> dict[str, Any]:
    return {
        "expires": "2026-07-30T03:28:20.712115624Z",
        "preventUsernameRedirect": False,
        "user": {
            "email": "user@example.com",
            "id": "free-user-id",
            "subscription_source": "none",
            "subscription_status": "none",
            "username": "free_user",
        },
    }


def _free_settings_payload() -> dict[str, Any]:
    return {
        "stripe_status": "none",
        "revenuecat_status": "none",
        "revenuecat_source": "none",
        "subscription_status": "none",
        "subscription_source": "none",
        "subscription_tier": None,
        "default_model": "turbo",
        "query_count": 0,
        "query_count_copilot": 0,
        "query_count_mobile": 2088,
        "is_verified": False,
    }


def test_account_session_normalizes_subscription_tier() -> None:
    session = AccountSession.model_validate(_session_payload("pro"))

    assert session.prevent_username_redirect is False
    assert session.account_tier == "pro"
    assert session.user is not None
    assert session.user.account_tier == "pro"


def test_account_session_detects_max_tier() -> None:
    session = AccountSession.model_validate(_session_payload("max", payment_tier="max"))

    assert session.account_tier == "max"


def test_account_session_detects_free_tier_from_none_subscription() -> None:
    session = AccountSession.model_validate(_free_session_payload())

    assert session.account_tier == "free"


def test_account_settings_detects_free_tier_and_default_model() -> None:
    settings = AccountSettings.model_validate(_free_settings_payload())

    assert settings.account_tier == "free"
    assert settings.default_model == "turbo"


def test_ensure_model_access_blocks_max_model_for_pro_session() -> None:
    session = AccountSession.model_validate(_session_payload("pro"))
    model = MODELS.resolve("anthropic/claude-opus-4.8")

    with raises(ModelAccessError) as exc_info:
        ensure_model_access(session, model)

    assert exc_info.value.model_id == "anthropic/claude-opus-4.8"
    assert exc_info.value.required_tier == "max"
    assert exc_info.value.account_tier == "pro"


def test_conversation_checks_session_before_prompt_request() -> None:
    fake_http = _FakeHTTP(_session_payload("pro"))
    conversation = Conversation(
        cast("HTTPClient", fake_http),
        ConversationConfig(model="anthropic/claude-opus-4.8"),
    )

    with raises(ModelAccessError):
        conversation.ask("hello")

    assert fake_http.get_calls == [(ENDPOINT_AUTH_SESSION, False)]
    assert fake_http.stream_called is False


def test_acknowledged_unstable_model_defers_tier_check_to_backend() -> None:
    fake_http = _FakeHTTP(_session_payload("pro"))
    conversation = Conversation(
        cast("HTTPClient", fake_http),
        ConversationConfig(model="openai/gpt-5.5-thinking", allow_risky_model=True),
    )

    with warns(ModelRiskWarning):
        conversation.ask("hello")

    assert fake_http.get_calls == [(ENDPOINT_AUTH_SESSION, False)]
    assert fake_http.ask_payload is not None
    assert fake_http.ask_payload["params"]["model_preference"] == "gpt55_thinking"


def test_best_model_uses_turbo_copilot_for_free_account() -> None:
    fake_http = _FakeHTTP(_free_session_payload())
    conversation = Conversation(
        cast("HTTPClient", fake_http),
        ConversationConfig(model="perplexity/best"),
    )

    conversation.ask("hello")

    assert fake_http.get_calls == [(ENDPOINT_AUTH_SESSION, False)]
    assert fake_http.ask_payload is not None
    assert fake_http.ask_payload["params"]["model_preference"] == "turbo"
    assert fake_http.ask_payload["params"]["mode"] == "copilot"


def test_best_model_uses_pro_upgraded_copilot_for_pro_account() -> None:
    fake_http = _FakeHTTP(_session_payload("pro"))
    conversation = Conversation(
        cast("HTTPClient", fake_http),
        ConversationConfig(model="perplexity/best"),
    )

    conversation.ask("hello")

    assert fake_http.get_calls == [(ENDPOINT_AUTH_SESSION, False)]
    assert fake_http.ask_payload is not None
    assert fake_http.ask_payload["params"]["model_preference"] == "pplx_pro_upgraded"
    assert fake_http.ask_payload["params"]["mode"] == "copilot"


def test_custom_model_builds_payload_after_risk_acknowledgement() -> None:
    fake_http = _FakeHTTP(_session_payload("pro"))
    conversation = Conversation(
        cast("HTTPClient", fake_http),
        ConversationConfig(
            model="custom:gpt57",
            allow_risky_model=True,
            custom_model_mode="search",
        ),
    )

    with warns(ModelRiskWarning):
        conversation.ask("hello")

    assert fake_http.ask_payload is not None
    assert fake_http.ask_payload["params"]["model_preference"] == "gpt57"
    assert fake_http.ask_payload["params"]["mode"] == "search"


def test_unknown_session_tier_falls_back_to_user_settings() -> None:
    fake_http = _FakeHTTP(
        {"expires": "2026-07-30T03:28:20.712115624Z", "user": {"email": "user@example.com"}},
        settings_payload=_free_settings_payload(),
    )
    conversation = Conversation(
        cast("HTTPClient", fake_http),
        ConversationConfig(model="perplexity/best"),
    )

    conversation.ask("hello")

    assert fake_http.get_calls == [(ENDPOINT_AUTH_SESSION, False), (ENDPOINT_USER_SETTINGS, False)]
    assert fake_http.ask_payload is not None
    assert fake_http.ask_payload["params"]["model_preference"] == "turbo"
    assert fake_http.ask_payload["params"]["mode"] == "copilot"


def test_free_account_cannot_send_files() -> None:
    fake_http = _FakeHTTP(_free_session_payload())
    conversation = Conversation(
        cast("HTTPClient", fake_http),
        ConversationConfig(model="perplexity/best"),
    )

    with raises(FileAccessError) as exc_info:
        conversation.ask("describe this", files=["image.png"])

    assert exc_info.value.account_tier == "free"
    assert fake_http.get_calls == [(ENDPOINT_AUTH_SESSION, False)]
    assert fake_http.stream_called is False


def test_client_get_account_session_uses_fast_session_request() -> None:
    fake_http = _FakeHTTP(_session_payload("pro"))
    client = Perplexity.__new__(Perplexity)
    client._http = fake_http  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

    session = client.get_account_session()

    assert session.account_tier == "pro"
    assert fake_http.get_calls == [(ENDPOINT_AUTH_SESSION, False)]


def test_client_get_account_profile_uses_settings_only_when_needed() -> None:
    fake_http = _FakeHTTP(
        {"expires": "2026-07-30T03:28:20.712115624Z", "user": {"email": "user@example.com"}},
        settings_payload=_free_settings_payload(),
    )
    client = Perplexity.__new__(Perplexity)
    client._http = fake_http  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

    profile = client.get_account_profile()

    assert profile.account_tier == "free"
    assert profile.settings is not None
    assert fake_http.get_calls == [(ENDPOINT_AUTH_SESSION, False), (ENDPOINT_USER_SETTINGS, False)]
