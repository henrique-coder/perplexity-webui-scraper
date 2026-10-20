"""Write regression tests for smoke-test status classification."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

from perplexity_webui_scraper._internal.exceptions import HTTPError
from perplexity_webui_scraper.models.types import Model
from scripts.smoke_test_models import _account_tier_gate, _probe_model, _write_report


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
        patch("scripts.smoke_test_models.Perplexity", return_value=client),
        patch("scripts.smoke_test_models.sleep") as sleep,
        patch("scripts.smoke_test_models.ClientConfig"),
        patch("scripts.smoke_test_models.ConversationConfig"),
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
