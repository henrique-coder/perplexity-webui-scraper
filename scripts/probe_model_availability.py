"""Test live availability for every model in the registry."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from math import isfinite
from os import environ
from pathlib import Path
from sys import stdout
from tempfile import NamedTemporaryFile
from time import sleep
from typing import TYPE_CHECKING, Annotated, Any

from dotenv import dotenv_values
from orjson import OPT_INDENT_2, dumps, loads
from typer import Option, Typer

from perplexity_webui_scraper import Perplexity
from perplexity_webui_scraper._internal.exceptions import (
    AuthenticationError,
    HTTPError,
    RateLimitError,
    ResponseParsingError,
)
from perplexity_webui_scraper.auth.cookies import parse_session_credential
from perplexity_webui_scraper.config import ClientConfig, ConversationConfig
from perplexity_webui_scraper.core.account import TIER_RANK
from perplexity_webui_scraper.models.registry import MODELS


if TYPE_CHECKING:
    from perplexity_webui_scraper.models.types import Model


_PROMPT = "Reply with exactly: OK"
_DEFAULT_REPORT = Path("reports/model-smoke-results.json")
_DEFAULT_CATALOG = Path(__file__).resolve().parents[1] / "src/perplexity_webui_scraper/_static/models.json"
_CONCLUSIVE_STATUSES = frozenset({"passed", "model_rejected", "blocked_by_account_tier"})

app = Typer(
    name="smoke-test-models",
    help="Run short live pings for every model in the registry.",
    add_completion=False,
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _read_session_token(env_file: Path) -> str:
    """Read and validate the Perplexity session token from .env or environment."""
    file_token = (dotenv_values(env_file).get("PERPLEXITY_SESSION_TOKEN") or "").strip() if env_file.is_file() else ""
    token = file_token or environ.get("PERPLEXITY_SESSION_TOKEN", "").strip()

    if not token:
        raise ValueError(f"PERPLEXITY_SESSION_TOKEN is missing from {env_file}")

    parse_session_credential(token)

    return token


def _write_json(path: Path, payload: Any) -> None:
    """Persist JSON atomically via a sibling temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with NamedTemporaryFile("wb", dir=path.parent, delete=False) as temporary:
        temporary.write(dumps(payload, option=OPT_INDENT_2))
        temporary.write(b"\n")
        temporary_path = Path(temporary.name)

    temporary_path.replace(path)


def _write_report(path: Path, report: dict[str, Any]) -> None:
    """Persist reports atomically to allow interrupted runs to resume."""
    _write_json(path, report)


def _account_tier_gate(model: Model, account_tier: str) -> str | None:
    """Return why the current account cannot test this model, if applicable."""
    if model.min_tier == "unknown" or account_tier not in TIER_RANK or TIER_RANK[account_tier] < 0:
        return None

    if TIER_RANK[account_tier] < TIER_RANK[model.min_tier]:
        return f"requires_{model.min_tier}_tier"

    return None


def _rate_limit_delay(error: HTTPError, attempt: int, backoff_multiplier: float) -> float:
    """Return a bounded delay after HTTP 429, preferring valid Retry-After seconds."""
    if isinstance(error, RateLimitError) and error.retry_after:
        try:
            parsed = float(error.retry_after.strip())
        except ValueError:
            parsed = -1.0

        if isfinite(parsed) and parsed >= 0:
            return min(60.0, max(1.0, parsed))

    return min(60.0, (2**attempt) * backoff_multiplier)


def _probe_model(
    model: Model,
    token: str,
    attempts: int = 2,
    backoff_multiplier: float = 1.0,
) -> dict[str, Any]:
    """Send a short prompt, retrying rate-limited requests after backoff."""
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
                sleep(_rate_limit_delay(error, attempt, backoff_multiplier))
                continue

            status = "rate_limited" if error.status_code == 429 else "http_error"
            details: dict[str, Any] = {
                "status": status,
                "http_status": error.status_code,
                "error_type": type(error).__name__,
            }

            if error.status_code != 429:
                details["error_message"] = error.message[:120]

            result.update(details)
            break
        except ResponseParsingError as error:
            message = error.message.lower()
            unavailable_markers = ("model not found", "unknown model", "model unavailable", "unsupported model")
            status = "model_rejected" if any(marker in message for marker in unavailable_markers) else "response_error"
            result.update(
                {
                    "status": status,
                    "error_type": type(error).__name__,
                    "error_message": error.message[:120],
                }
            )
            break
        except Exception as error:
            result.update({"status": "error", "error_type": type(error).__name__})
            break

    result["completed_at"] = _utc_now()

    return result


def apply_report_to_catalog(report: dict[str, Any], catalog_path: Path = _DEFAULT_CATALOG) -> tuple[int, int]:
    """Apply conclusive availability results to the bundled model catalog JSON."""
    catalog = loads(catalog_path.read_bytes())

    if not isinstance(catalog, list):
        raise TypeError(f"Expected a JSON array in {catalog_path}")

    results_by_id = {
        item["id"]: item
        for item in report.get("models", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    updated = 0
    unchanged = 0

    for entry in catalog:
        if not isinstance(entry, dict):
            unchanged += 1
            continue

        result = results_by_id.get(entry.get("id"))
        completed_at = result.get("completed_at") if isinstance(result, dict) else None
        status = result.get("status") if isinstance(result, dict) else None

        if isinstance(completed_at, str) and status == "passed":
            entry["status"] = "available"
            entry["last_tested_at"] = completed_at
            updated += 1
        elif isinstance(completed_at, str) and status == "model_rejected":
            entry["status"] = "unavailable"
            entry["last_tested_at"] = completed_at
            updated += 1
        else:
            unchanged += 1

    _write_json(catalog_path, catalog)

    return updated, unchanged


def _load_resume(path: Path, *, retry_inconclusive: bool = False) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}

    existing = loads(path.read_bytes())
    allowed_statuses = {"running", "complete"} if retry_inconclusive else {"running"}

    if not isinstance(existing, dict) or existing.get("status") not in allowed_statuses:
        return {}

    valid_ids = {model.id for model in MODELS.list_all()}

    return {
        result["id"]: result
        for result in existing.get("models", [])
        if isinstance(result, dict)
        and result.get("id") in valid_ids
        and (not retry_inconclusive or result.get("status") in _CONCLUSIVE_STATUSES)
    }


def _run(
    report_path: Path,
    workers: int,
    *,
    attempts: int = 4,
    delay: float = 1.0,
    apply: bool = False,
    retry_inconclusive: bool = False,
) -> dict[str, Any]:
    token = _read_session_token(Path.cwd() / ".env")

    with Perplexity(token, config=ClientConfig(timeout=30, max_retries=0)) as client:
        account_tier = client.get_account_profile().account_tier

    models = MODELS.list_all()
    results = _load_resume(report_path, retry_inconclusive=retry_inconclusive)

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
    batch_size = 1 if workers == 1 else workers * 3
    backoff_multiplier = 4.0 if attempts > 2 else 1.0

    for offset in range(0, len(pending), batch_size):
        batch = pending[offset : offset + batch_size]

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_probe_model, model, token, attempts, backoff_multiplier): model for model in batch
            }

            for future in as_completed(futures):
                model = futures[future]
                item = future.result()
                results[model.id] = item
                timestamp = item.get("completed_at") or item.get("tested_at") or ""
                stdout.write(f"[{len(results)}/{len(models)}] {model.id} -> {item['status']} ({timestamp})\n")
                stdout.flush()

        report["models"] = [results[model.id] for model in models if model.id in results]
        _write_report(report_path, report)

        if delay > 0 and offset + batch_size < len(pending):
            sleep(delay)

    report["models"] = [results[model.id] for model in models]
    report["summary"] = {
        status: sum(item["status"] == status for item in report["models"])
        for status in sorted({item["status"] for item in report["models"]})
    }
    report["status"] = "complete"
    report["completed_at"] = _utc_now()

    _write_report(report_path, report)

    if apply:
        updated, unchanged = apply_report_to_catalog(report)
        stdout.write(f"Applied report to catalog: {updated} updated, {unchanged} unchanged.\n")
        stdout.flush()

    return report


@app.command()
def main(
    workers: Annotated[
        int,
        Option("--workers", min=1, max=8, help="Parallel requests, from 1 to 8."),
    ] = 1,
    attempts: Annotated[
        int,
        Option("--attempts", min=1, max=8, help="Maximum attempts per model, from 1 to 8."),
    ] = 4,
    delay: Annotated[
        float,
        Option("--delay", min=0.0, max=30.0, help="Seconds to wait between batches."),
    ] = 1.0,
    output: Annotated[
        Path,
        Option("--output", help="Output report path."),
    ] = _DEFAULT_REPORT,
    apply: Annotated[
        bool,
        Option("--apply", help="Apply conclusive results to src/perplexity_webui_scraper/_static/models.json."),
    ] = False,
    retry_inconclusive: Annotated[
        bool,
        Option("--retry-inconclusive", help="Keep conclusive results from an existing report and retry the rest."),
    ] = False,
) -> None:
    """Run short live availability pings across catalog models."""
    _run(
        output,
        workers,
        attempts=attempts,
        delay=delay,
        apply=apply,
        retry_inconclusive=retry_inconclusive,
    )


if __name__ == "__main__":
    app()
