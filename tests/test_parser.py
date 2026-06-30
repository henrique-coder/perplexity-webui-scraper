from __future__ import annotations

from pytest import raises

from perplexity_webui_scraper._internal.exceptions import RateLimitError, ResponseParsingError
from perplexity_webui_scraper.core.parser import process_sse_data


def test_process_sse_data_raises_rate_limit_for_free_tier_error() -> None:
    with raises(RateLimitError) as exc_info:
        process_sse_data(
            {
                "error_code": "FREE_TIER_RATE_LIMITED",
                "experience": "upgrade",
                "status": "failed",
                "final_sse_message": True,
            },
            [],
            "clean",
        )

    assert exc_info.value.status_code == 429
    assert "FREE_TIER_RATE_LIMITED" in exc_info.value.message


def test_process_sse_data_handles_lowercase_failed_status() -> None:
    with raises(ResponseParsingError, match="Error in processing query"):
        process_sse_data(
            {
                "status": "failed",
                "text": "Error in processing query.",
            },
            [],
            "clean",
        )
