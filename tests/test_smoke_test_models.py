"""Write regression tests for smoke-test status classification."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

from orjson import dumps, loads

from perplexity_webui_scraper._internal.constants import SESSION_COOKIE_PREFIX, SESSION_TOKEN_JWE_HEADER
from perplexity_webui_scraper._internal.exceptions import HTTPError
from perplexity_webui_scraper.auth.session_token import pack_session_token
from perplexity_webui_scraper.models.types import Model
from scripts.probe_model_availability import (
    _account_tier_gate,
    _probe_model,
    _read_session_token,
    _write_report,
    apply_report_to_catalog,
)


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

    env_file.write_text(f"PERPLEXITY_SESSION_TOKEN={compact_token}\n", encoding="utf-8")
    assert _read_session_token(env_file) == compact_token


def test_apply_report_to_catalog_updates_conclusive_results_only(tmp_path: Path) -> None:
    catalog_path = tmp_path / "models.json"
    old_timestamp = "2026-10-05T20:16:12.021045Z"
    catalog = [
        {"id": "test/passed", "status": "unknown", "last_tested_at": None},
        {"id": "test/rejected", "status": "available", "last_tested_at": old_timestamp},
        {"id": "test/blocked", "status": "unknown", "last_tested_at": None},
        {"id": "test/rate-limited", "status": "available", "last_tested_at": old_timestamp},
    ]
    catalog_path.write_bytes(dumps(catalog))

    report = {
        "models": [
            {"id": "test/passed", "status": "passed", "completed_at": "2026-11-19T21:10:01Z"},
            {"id": "test/rejected", "status": "model_rejected", "completed_at": "2026-11-19T21:10:05Z"},
            {"id": "test/blocked", "status": "blocked_by_account_tier", "tested_at": "2026-11-19T21:10:06Z"},
            {"id": "test/rate-limited", "status": "rate_limited", "completed_at": "2026-11-19T21:10:09Z"},
        ]
    }

    updated, unchanged = apply_report_to_catalog(report, catalog_path)
    saved = loads(catalog_path.read_bytes())

    assert (updated, unchanged) == (2, 2)
    assert saved[0] == {"id": "test/passed", "status": "available", "last_tested_at": "2026-11-19T21:10:01Z"}
    assert saved[1] == {"id": "test/rejected", "status": "unavailable", "last_tested_at": "2026-11-19T21:10:05Z"}
    assert saved[2] == {"id": "test/blocked", "status": "unknown", "last_tested_at": None}
    assert saved[3] == {"id": "test/rate-limited", "status": "available", "last_tested_at": old_timestamp}
