from __future__ import annotations

from typing import Any

from perplexity_webui_scraper import Perplexity, UserSettings


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeHTTPClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.endpoint: str | None = None

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> _FakeResponse:
        self.endpoint = endpoint
        return _FakeResponse(self.payload)


def _settings_payload() -> dict[str, Any]:
    return {
        "pages_limit": 100,
        "upload_limit": 49,
        "create_limit": 99,
        "subscription_status": "active",
        "subscription_source": "stripe",
        "subscription_tier": "yearly",
        "stripe_status": "active",
        "query_count": 1322,
        "connector_limits": {
            "repo_type_limits": {
                "COLLECTION": {
                    "max_files": 50,
                    "max_folders": 50,
                }
            },
            "global_file_count": 500,
            "max_file_size_mb": 50,
        },
        "sources": {
            "source_to_limit": {
                "web": {
                    "monthly_limit": None,
                    "remaining": None,
                },
                "ahrefs_premium_data": {
                    "monthly_limit": 50,
                    "remaining": 49,
                },
            }
        },
        "connectors": {
            "connectors": [
                {
                    "name": "github_mcp_direct",
                    "auth_type": "oauth",
                    "connected": True,
                    "error": None,
                    "connection_display_name": "user@example.com",
                    "connection_uuid": "connection-uuid",
                    "source_id": "github_mcp_direct",
                    "connection_type": "GITHUB_MCP_DIRECT",
                    "capabilities": {},
                    "disabled_capabilities": [],
                }
            ]
        },
    }


def test_user_settings_parses_known_settings_shape() -> None:
    settings = UserSettings.model_validate(_settings_payload())

    assert settings.account_tier == "pro"
    assert settings.subscription_tier == "yearly"
    assert settings.connector_limits is not None
    assert settings.connector_limits.repo_type_limits["COLLECTION"].max_files == 50
    assert settings.sources is not None
    assert settings.sources.source_to_limit["ahrefs_premium_data"].remaining == 49
    assert settings.connectors is not None
    assert settings.connectors.connectors[0].connected is True


def test_user_settings_infers_free_and_max_tiers() -> None:
    assert UserSettings.model_validate({}).account_tier == "free"
    assert UserSettings.model_validate({"subscription_tier": "max"}).account_tier == "max"


def test_perplexity_get_user_settings_returns_typed_model() -> None:
    client = Perplexity.__new__(Perplexity)
    fake_http = _FakeHTTPClient(_settings_payload())
    client._http = fake_http

    settings = client.get_user_settings()

    assert fake_http.endpoint == "/rest/user/settings"
    assert isinstance(settings, UserSettings)
    assert settings.account_tier == "pro"
