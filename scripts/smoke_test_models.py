"""Test live availability for every model in the registry."""

from __future__ import annotations

from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from json import dumps, loads
from pathlib import Path
from shlex import split
from tempfile import NamedTemporaryFile
from time import sleep
from typing import TYPE_CHECKING, Any

from perplexity_webui_scraper import Perplexity
from perplexity_webui_scraper._internal.exceptions import AuthenticationError, HTTPError, ResponseParsingError
from perplexity_webui_scraper.config import ClientConfig, ConversationConfig
from perplexity_webui_scraper.models.registry import MODELS


if TYPE_CHECKING:
    from perplexity_webui_scraper.models.types import Model


_PROMPT = "Reply with exactly: OK"
_TIER_RANK: dict[str, int] = {"free": 0, "pro": 1, "max": 2}
_DEFAULT_REPORT = Path("reports/model-smoke-results.json")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _read_session_token(env_file: Path) -> str:
    """Read the Perplexity token from .env without exposing it."""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if value.startswith("export "):
            value = value.removeprefix("export ").lstrip()
        key, separator, raw_value = value.partition("=")
        if separator and key.strip() == "PERPLEXITY_SESSION_TOKEN":
            parsed = split(raw_value.strip(), comments=True, posix=True)
            if parsed and parsed[0]:
                return parsed[0]
    raise ValueError(f"PERPLEXITY_SESSION_TOKEN is missing from {env_file}")


def _write_report(path: Path, report: dict[str, Any]) -> None:
    """Persist reports atomically to allow interrupted runs to resume."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
        temporary.write(dumps(report, indent=2) + "\n")
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def _account_tier_gate(model: Model, account_tier: str) -> str | None:
    """Return why the current account cannot test this model, if applicable."""
    if model.min_tier is None or account_tier not in _TIER_RANK:
        return None
    if _TIER_RANK[account_tier] < _TIER_RANK[model.min_tier]:
        return f"requires_{model.min_tier}_tier"
    return None


def _probe_model(model: Model, token: str, attempts: int = 2) -> dict[str, Any]:
    """Send a short prompt, retrying one rate-limited request after backoff."""
    result: dict[str, Any] = {
        "id": model.id,
        "name": model.name,
        "catalog_status": model.status,
        "min_tier": model.min_tier,
        "tested_at": _utc_now(),
        "attempts": 0,
    }
    for attempt in range(1, attempts + 1):
        result["attempts"] = attempt
        try:
            config = ClientConfig(timeout=90, max_retries=0)
            conversation_config = ConversationConfig(model=model.id, allow_risky_model=True)
            with Perplexity(token, config=config) as client:
                conversation = client.create_conversation(conversation_config)
                conversation.ask(_PROMPT, allow_risky_model=True)
                answer = (conversation.answer or "").strip()
            if answer:
                result.update({"status": "passed", "answer_characters": len(answer)})
            else:
                result.update({"status": "empty_response", "answer_characters": 0})
            break
        except AuthenticationError as error:
            result.update({"status": "authentication_error", "http_status": error.status_code})
            break
        except HTTPError as error:
            if error.status_code == 429 and attempt < attempts:
                sleep(2**attempt)
                continue
            status = "rate_limited" if error.status_code == 429 else "http_error"
            result.update({"status": status, "http_status": error.status_code, "error_type": type(error).__name__})
            break
        except ResponseParsingError as error:
            message = error.message.lower()
            unavailable_markers = ("model not found", "unknown model", "model unavailable", "unsupported model")
            status = "model_rejected" if any(marker in message for marker in unavailable_markers) else "response_error"
            result.update({"status": status, "error_type": type(error).__name__})
            break
        except Exception as error:
            result.update({"status": "error", "error_type": type(error).__name__})
            break
    result["completed_at"] = _utc_now()
    return result


def _load_resume(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    existing = loads(path.read_text(encoding="utf-8"))
    if not isinstance(existing, dict) or existing.get("status") != "running":
        return {}
    valid_ids = {model.id for model in MODELS.list_all()}
    return {
        result["id"]: result
        for result in existing.get("models", [])
        if isinstance(result, dict) and result.get("id") in valid_ids
    }


def _run(report_path: Path, workers: int) -> dict[str, Any]:
    token = _read_session_token(Path.cwd() / ".env")
    with Perplexity(token, config=ClientConfig(timeout=30, max_retries=0)) as client:
        account_tier = client.get_account_profile().account_tier

    models = MODELS.list_all()
    results = _load_resume(report_path)
    for model in models:
        gate_reason = _account_tier_gate(model, account_tier)
        if gate_reason and model.id not in results:
            results[model.id] = {
                "id": model.id,
                "name": model.name,
                "catalog_status": model.status,
                "min_tier": model.min_tier,
                "tested_at": _utc_now(),
                "status": "blocked_by_account_tier",
                "reason": gate_reason,
            }

    report: dict[str, Any] = {
        "tested_at": _utc_now(),
        "completed_at": None,
        "status": "running",
        "account_tier": account_tier,
        "ping": _PROMPT,
        "catalog_count": len(models),
        "models": [results[model.id] for model in models if model.id in results],
    }
    _write_report(report_path, report)

    pending = [model for model in models if model.id not in results]
    batch_size = workers * 3
    for offset in range(0, len(pending), batch_size):
        batch = pending[offset : offset + batch_size]
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_probe_model, model, token): model for model in batch}
            for future in as_completed(futures):
                model = futures[future]
                results[model.id] = future.result()
        report["models"] = [results[model.id] for model in models if model.id in results]
        _write_report(report_path, report)

    report["models"] = [results[model.id] for model in models]
    report["summary"] = {
        status: sum(item["status"] == status for item in report["models"])
        for status in sorted({item["status"] for item in report["models"]})
    }
    report["status"] = "complete"
    report["completed_at"] = _utc_now()
    _write_report(report_path, report)
    return report


def main() -> None:
    parser = ArgumentParser(description="Run short live pings for every model in the registry.")
    parser.add_argument("--workers", type=int, default=4, help="Parallel requests, from 1 to 8 (default: 4).")
    parser.add_argument("--output", type=Path, default=_DEFAULT_REPORT, help="Output report path.")
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error("--workers must be between 1 and 8")
    _run(args.output, args.workers)


if __name__ == "__main__":
    main()
