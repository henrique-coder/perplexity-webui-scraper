"""Regression tests for model catalog synchronization using pydoll (Python >=3.11, <3.15)."""

from __future__ import annotations

from sys import version_info
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

from pytest import mark, raises

from perplexity_webui_scraper._internal.constants import (
    API_BASE_URL,
    SESSION_COOKIE_PREFIX,
    SESSION_TOKEN_JWE_HEADER,
)
from perplexity_webui_scraper.auth.session_token import pack_session_token
from scripts.sync_model_catalog import (
    EndpointCatalog,
    EndpointDetail,
    EndpointModel,
    _fetch_webui_models,
    _provider_slug,
    _public_id,
    _read_session_token,
    _synchronize,
    _tool_name,
    sync_playwright,
)


if TYPE_CHECKING:
    from pathlib import Path


def test_read_session_token_accepts_raw_and_compact_credentials(tmp_path: Path) -> None:
    account_uuid = "123e4567-e89b-42d3-a456-426614174000"
    jwe = f"{SESSION_TOKEN_JWE_HEADER}..EBESExQVFhcYGRob.AQIDBAUGBw.MDEyMzQ1Njc4OTo7PD0-Pw"
    raw_cookie = f"{SESSION_COOKIE_PREFIX}{account_uuid}={jwe}"
    compact_token = pack_session_token(raw_cookie)
    env_file = tmp_path / ".env"

    env_file.write_text(f"PERPLEXITY_SESSION_TOKEN={raw_cookie}\n", encoding="utf-8")
    assert _read_session_token(env_file) == raw_cookie

    env_file.write_text(f"PERPLEXITY_SESSION_TOKEN={compact_token}\n", encoding="utf-8")
    assert _read_session_token(env_file) == compact_token


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
            "min_tier": "unknown",
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
            "mystery_model": EndpointDetail(
                label="Mystery",
                description="Unclassified model tier.",
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
            EndpointModel(
                label="Mystery",
                description="Unclassified model tier.",
                subscription_tier=None,
                non_reasoning_model="mystery_model",
            ),
        ],
        default_models={"default": "turbo"},
    )

    synchronized = _synchronize(local, endpoint, ["Best", "GPT-6.2 Sol", "Mystery"])

    assert [entry["id"] for entry in synchronized] == [
        "perplexity/best",
        "openai/gpt-6.2-sol",
        "openai/mystery",
        "openai/gpt4o",
    ]
    assert synchronized[0]["is_official"] is True
    assert synchronized[1]["is_official"] is True
    assert synchronized[1]["status"] == "unknown"
    assert synchronized[2]["min_tier"] == "unknown"
    assert synchronized[3]["is_official"] is False


@mark.skipif(version_info >= (3, 15), reason="pydoll-python supports Python >=3.11, <3.15")
def test_fetch_webui_models_uses_pydoll_playwright_and_sets_both_cookies() -> None:
    assert sync_playwright is not None

    account_uuid = "123e4567-e89b-42d3-a456-426614174000"
    jwe = f"{SESSION_TOKEN_JWE_HEADER}..EBESExQVFhcYGRob.AQIDBAUGBw.MDEyMzQ1Njc4OTo7PD0-Pw"
    raw_cookie = f"{SESSION_COOKIE_PREFIX}{account_uuid}={jwe}"
    compact_token = pack_session_token(raw_cookie)

    first_item = Mock()
    first_item.is_visible.return_value = True
    first_item.locator.return_value.all_text_contents.return_value = ["Best", "GPT-6.2 Sol"]
    second_item = Mock()
    second_item.is_visible.return_value = False
    third_item = Mock()
    third_item.is_visible.return_value = True
    third_item.locator.return_value.all_text_contents.return_value = ["GPT-6.2 Sol", "Mystery"]

    items_locator = Mock()
    items_locator.all.return_value = [first_item, second_item, third_item]
    button_locator = Mock()
    page = Mock()
    page.get_by_role.return_value = button_locator
    page.locator.return_value = items_locator

    context = Mock()
    context.new_page.return_value = page
    browser = Mock()
    browser.new_context.return_value = context
    playwright = Mock()
    playwright.chromium.launch.return_value = browser
    playwright_ctx = Mock()
    playwright_ctx.__enter__ = Mock(return_value=playwright)
    playwright_ctx.__exit__ = Mock(return_value=False)

    with patch("scripts.sync_model_catalog.sync_playwright", return_value=playwright_ctx):
        models = _fetch_webui_models(compact_token)

    assert models == ["Best", "GPT-6.2 Sol", "Mystery"]
    playwright.chromium.launch.assert_called_once_with(headless=True)
    context.add_cookies.assert_called_once_with(
        [
            {
                "name": f"{SESSION_COOKIE_PREFIX}{account_uuid}",
                "value": jwe,
                "url": f"{API_BASE_URL}/",
                "secure": True,
                "httpOnly": True,
                "sameSite": "Lax",
            },
            {
                "name": "__Host-pplx-last-active-account",
                "value": account_uuid,
                "url": f"{API_BASE_URL}/",
                "secure": True,
                "httpOnly": False,
                "sameSite": "Lax",
            },
        ]
    )
    page.goto.assert_called_once_with(f"{API_BASE_URL}/", wait_until="domcontentloaded")
    button_locator.wait_for.assert_called_once_with(state="visible", timeout=15_000)
    button_locator.click.assert_called_once_with()
    browser.close.assert_called_once_with()

    browser.reset_mock()
    page.goto.side_effect = RuntimeError("page failed")

    with (
        patch("scripts.sync_model_catalog.sync_playwright", return_value=playwright_ctx),
        raises(RuntimeError, match="Failed to read the authenticated Perplexity model picker"),
    ):
        _fetch_webui_models(raw_cookie)

    browser.close.assert_called_once_with()


@mark.skipif(version_info < (3, 15), reason="Checks Python >=3.15 guard error")
def test_fetch_webui_models_guides_to_python_below_3_15_on_unsupported_runtime() -> None:
    account_uuid = "123e4567-e89b-42d3-a456-426614174000"
    jwe = f"{SESSION_TOKEN_JWE_HEADER}..EBESExQVFhcYGRob.AQIDBAUGBw.MDEyMzQ1Njc4OTo7PD0-Pw"
    raw_cookie = f"{SESSION_COOKIE_PREFIX}{account_uuid}={jwe}"

    with raises(RuntimeError, match=r">=3\.11, <3\.15"):
        _fetch_webui_models(raw_cookie)
