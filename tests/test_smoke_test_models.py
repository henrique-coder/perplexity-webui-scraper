"""Write regression tests for smoke-test status classification."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

from pytest import raises

from perplexity_webui_scraper._internal.constants import API_BASE_URL, SESSION_COOKIE_PREFIX, SESSION_TOKEN_JWE_HEADER
from perplexity_webui_scraper._internal.exceptions import HTTPError
from perplexity_webui_scraper.auth.session_token import pack_session_token
from perplexity_webui_scraper.models.types import Model
from scripts.probe_model_availability import (
    _account_tier_gate,
    _probe_model,
    _read_session_token,
    _write_report,
)
from scripts.sync_model_catalog import (
    EndpointCatalog,
    EndpointDetail,
    EndpointModel,
    _build_chromium_options,
    _fetch_webui_models,
    _provider_slug,
    _public_id,
    _resolve_browser_path,
    _synchronize,
    _tool_name,
)
from scripts.sync_model_catalog import _read_session_token as _read_sync_token


_MODEL = Model(
    id="test/model",
    name="Test model",
    description="Test model description",
    identifier="test_model",
    tool_name="test_model",
    provider="test",
    min_tier="pro",
)


def test_unknown_tier_model_is_not_classified_unavailable() -> None:
    assert _account_tier_gate(_MODEL, "pro") is None


def test_max_tier_model_is_blocked_by_pro_account() -> None:
    model = _MODEL.model_copy(update={"min_tier": "max"})

    assert _account_tier_gate(model, "pro") == "requires_max_tier"


def test_probe_retries_rate_limit_once_and_records_pass() -> None:
    conversation = Mock(answer="OK")
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.create_conversation.return_value = conversation
    rate_limit = HTTPError("rate limited", status_code=429)

    with (
        patch("scripts.probe_model_availability.Perplexity", return_value=client),
        patch("scripts.probe_model_availability.sleep") as sleep,
        patch("scripts.probe_model_availability.ClientConfig"),
        patch("scripts.probe_model_availability.ConversationConfig"),
    ):
        conversation.ask.side_effect = [rate_limit, None]
        result = _probe_model(_MODEL, "synthetic-test-token")

    assert result["status"] == "passed"
    assert result["attempts"] == 2
    assert result["answer_characters"] == 2
    sleep.assert_called_once_with(2)


def test_write_report_stores_utc_timestamps_without_token(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    timestamp = datetime.now(UTC).isoformat()
    report = {"tested_at": timestamp, "status": "running", "models": []}

    _write_report(report_path, report)

    assert report_path.is_file()
    assert "synthetic-test-token" not in report_path.read_text()


def test_scripts_read_session_token_accepts_raw_and_compact_credentials(tmp_path: Path) -> None:
    account_uuid = "123e4567-e89b-42d3-a456-426614174000"
    jwe = f"{SESSION_TOKEN_JWE_HEADER}..EBESExQVFhcYGRob.AQIDBAUGBw.MDEyMzQ1Njc4OTo7PD0-Pw"
    raw_cookie = f"{SESSION_COOKIE_PREFIX}{account_uuid}={jwe}"
    compact_token = pack_session_token(raw_cookie)
    env_file = tmp_path / ".env"

    env_file.write_text(f"PERPLEXITY_SESSION_TOKEN={raw_cookie}\n", encoding="utf-8")
    assert _read_session_token(env_file) == raw_cookie
    assert _read_sync_token(env_file) == raw_cookie

    env_file.write_text(f"PERPLEXITY_SESSION_TOKEN={compact_token}\n", encoding="utf-8")
    assert _read_session_token(env_file) == compact_token
    assert _read_sync_token(env_file) == compact_token


def test_model_catalog_sync_preserves_history_and_validates_entries() -> None:
    assert _provider_slug("X_AI") == "x-ai"
    assert _provider_slug("ZAI") == "z-ai"
    assert _public_id("openai", "GPT-6.2 Sol", reasoning=True) == "openai/gpt-6.2-sol-thinking"
    assert _tool_name("openai/gpt-6.2-sol-thinking") == "pplx_gpt62_sol_think"

    local = [
        {
            "id": "perplexity/best",
            "name": "Best",
            "description": "Default model.",
            "identifier": "turbo",
            "identifier_by_tier": {"pro": "pplx_pro_upgraded"},
            "tool_name": "pplx_best",
            "provider": "perplexity",
            "min_tier": "free",
            "is_official": True,
            "mode": "copilot",
            "mode_by_tier": {},
            "status": "available",
            "last_tested_at": "2026-10-05T20:16:12Z",
        },
        {
            "id": "openai/gpt4o",
            "name": "GPT-4o",
            "description": "Historical model.",
            "identifier": "gpt4o",
            "identifier_by_tier": {},
            "tool_name": "pplx_gpt4o",
            "provider": "openai",
            "min_tier": None,
            "is_official": False,
            "mode": "copilot",
            "mode_by_tier": {},
            "status": "available",
            "last_tested_at": "2026-10-05T20:20:07Z",
        },
    ]
    endpoint = EndpointCatalog(
        models={
            "turbo": EndpointDetail(
                label="Best",
                description="Default model.",
                mode="search",
                provider="perplexity",
            ),
            "gpt6_2_sol": EndpointDetail(
                label="GPT-6.2 Sol",
                description="Fast flagship.",
                mode="search",
                provider="openai",
            ),
        },
        search_config=[
            EndpointModel(
                label="GPT-6.2 Sol",
                description="Fast flagship.",
                subscription_tier="pro",
                non_reasoning_model="gpt6_2_sol",
            ),
        ],
        default_models={"default": "turbo"},
    )

    synchronized = _synchronize(local, endpoint, ["Best", "GPT-6.2 Sol"])

    assert [entry["id"] for entry in synchronized] == [
        "perplexity/best",
        "openai/gpt-6.2-sol",
        "openai/gpt4o",
    ]
    assert synchronized[0]["is_official"] is True
    assert synchronized[1]["is_official"] is True
    assert synchronized[1]["status"] == "unknown"
    assert synchronized[2]["is_official"] is False


def test_drissionpage_browser_options_and_picker_collection(tmp_path: Path) -> None:
    fake_browser = tmp_path / "chrome"
    fake_browser.write_text("", encoding="utf-8")
    assert _resolve_browser_path(fake_browser) == fake_browser

    with raises(FileNotFoundError):
        _resolve_browser_path(tmp_path / "missing-browser")

    options_instance = Mock()
    options_instance.auto_port.return_value = options_instance

    with patch("scripts.sync_model_catalog.ChromiumOptions", return_value=options_instance):
        built = _build_chromium_options(fake_browser)

    assert built is options_instance
    options_instance.auto_port.assert_called_once_with()
    options_instance.headless.assert_called_once_with(True)
    options_instance.set_argument.assert_any_call("--disable-blink-features=AutomationControlled")
    options_instance.set_browser_path.assert_called_once_with(str(fake_browser))

    account_uuid = "123e4567-e89b-42d3-a456-426614174000"
    jwe = f"{SESSION_TOKEN_JWE_HEADER}..EBESExQVFhcYGRob.AQIDBAUGBw.MDEyMzQ1Njc4OTo7PD0-Pw"
    raw_cookie = f"{SESSION_COOKIE_PREFIX}{account_uuid}={jwe}"
    page_mock = Mock()
    page_mock.run_js.side_effect = [True, ["Best", "GPT-6.2 Sol"]]

    with (
        patch("scripts.sync_model_catalog._build_chromium_options", return_value=options_instance),
        patch("scripts.sync_model_catalog.ChromiumPage", return_value=page_mock) as page_cls,
    ):
        models = _fetch_webui_models(raw_cookie, browser_path=fake_browser)

    assert models == ["Best", "GPT-6.2 Sol"]
    page_cls.assert_called_once_with(addr_or_opts=options_instance)
    page_mock.run_cdp.assert_any_call("Network.enable")
    page_mock.run_cdp.assert_any_call(
        "Network.setCookie",
        name=f"{SESSION_COOKIE_PREFIX}{account_uuid}",
        value=jwe,
        url=f"{API_BASE_URL}/",
        secure=True,
        httpOnly=True,
        sameSite="Lax",
    )
    page_mock.run_cdp.assert_any_call(
        "Network.setCookie",
        name="__Host-pplx-last-active-account",
        value=account_uuid,
        url=f"{API_BASE_URL}/",
        secure=True,
        httpOnly=False,
        sameSite="Lax",
    )
    page_mock.get.assert_called_once_with(f"{API_BASE_URL}/")
    page_mock.quit.assert_called_once_with(del_data=True)

    failing_page = Mock()
    failing_page.get.side_effect = RuntimeError("navigation error")

    with (
        patch("scripts.sync_model_catalog._build_chromium_options", return_value=options_instance),
        patch("scripts.sync_model_catalog.ChromiumPage", return_value=failing_page),
        raises(RuntimeError, match="Failed to read the authenticated Perplexity model picker"),
    ):
        _fetch_webui_models(raw_cookie, browser_path=fake_browser)

    failing_page.quit.assert_called_once_with(del_data=True)
