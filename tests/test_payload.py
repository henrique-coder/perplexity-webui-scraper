from __future__ import annotations

from uuid import UUID

from perplexity_webui_scraper.config.conversation import ConversationConfig
from perplexity_webui_scraper.core.payload import build_payload
from perplexity_webui_scraper.models.registry import MODELS


def test_payload_all_sources_expands_to_web_and_academic() -> None:
    payload = build_payload(
        query="recent science news",
        model=MODELS.resolve("perplexity/best"),
        file_urls=[],
        config=ConversationConfig(source_focus="all"),
        backend_uuid=None,
        read_write_token=None,
    )

    assert payload["params"]["sources"] == ["web", "scholar"]


def test_new_thread_payload_matches_observed_home_request_fields() -> None:
    payload = build_payload(
        query="hello",
        model=MODELS.resolve("perplexity/best"),
        file_urls=[],
        config=ConversationConfig(),
        backend_uuid=None,
        read_write_token=None,
    )

    params = payload["params"]
    UUID(params["frontend_uuid"])
    UUID(params["frontend_context_uuid"])
    assert params["query_source"] == "home"
    assert params["search_focus"] == "internet"
    assert params["skip_search_enabled"] is False
    assert params["sources"] == ["web"]


def test_writing_mode_uses_search_disabled_flag_from_webui_capture() -> None:
    payload = build_payload(
        query="generate a short poem",
        model=MODELS.resolve("perplexity/best"),
        file_urls=[],
        config=ConversationConfig(search_focus="writing"),
        backend_uuid=None,
        read_write_token=None,
    )

    assert payload["params"]["search_focus"] == "internet"
    assert payload["params"]["skip_search_enabled"] is True


def test_followup_payload_reuses_thread_and_matches_observed_followup_fields() -> None:
    backend_uuid = "e10ce1e9-2891-4fd7-aec1-6d119f4d223f"
    payload = build_payload(
        query="follow up",
        model=MODELS.resolve("perplexity/best"),
        file_urls=[],
        config=ConversationConfig(),
        backend_uuid=backend_uuid,
        read_write_token="write-token",
    )

    params = payload["params"]
    assert params["query_source"] == "followup"
    assert params["followup_source"] == "link"
    assert params["last_backend_uuid"] == backend_uuid
    assert params["read_write_token"] == "write-token"
    UUID(params["frontend_uuid"])
    assert "frontend_context_uuid" not in params
