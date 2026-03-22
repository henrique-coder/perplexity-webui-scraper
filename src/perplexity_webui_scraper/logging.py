"""Logging configuration using loguru."""

from __future__ import annotations

from os import PathLike  # noqa: TC003
from pathlib import Path
from sys import stderr
from typing import TYPE_CHECKING, Any

from loguru import logger


if TYPE_CHECKING:
    from loguru import Logger

    from .types import LogLevel


logger.remove()
_logging_configured: bool = False


def configure_logging(
    level: LogLevel = "disabled",
    log_file: str | PathLike[str] | None = None,
) -> None:
    """Configure logging for the library."""

    global _logging_configured  # noqa: PLW0603

    logger.remove()
    level_str = level.upper()

    if level_str == "DISABLED":
        logger.disable("perplexity_webui_scraper")
        _logging_configured = False

        return

    logger.enable("perplexity_webui_scraper")

    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    file_format = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message} | {extra}"

    if log_file is not None:
        log_path = Path(log_file)
        logger.add(
            log_path,
            format=file_format,
            level=level_str,
            rotation=None,
            retention=None,
            compression=None,
            mode="a",
            encoding="utf-8",
            filter="perplexity_webui_scraper",
            enqueue=True,
        )
    else:
        logger.add(
            stderr,
            format=console_format,
            level=level_str,
            colorize=True,
            filter="perplexity_webui_scraper",
        )

    _logging_configured = True


def get_logger(name: str) -> Logger:
    """Get a logger instance bound to the given module name."""

    return logger.bind(module=name)


def log_request(
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    body_size: int | None = None,
) -> None:
    """Log an outgoing HTTP request."""

    logger.debug("HTTP {} {} | params={} body_size={}", method, url, params, body_size)


def log_response(
    method: str,
    url: str,
    status_code: int,
    *,
    elapsed_ms: float | None = None,
) -> None:
    """Log an HTTP response."""

    level = "DEBUG" if status_code < 400 else "WARNING"
    elapsed_fmt = f"{elapsed_ms:.2f}" if elapsed_ms is not None else "N/A"
    logger.log(level, "HTTP {} {} | status={} elapsed_ms={}", method, url, status_code, elapsed_fmt)


def log_retry(
    attempt: int,
    max_attempts: int,
    exception: BaseException | None,
    wait_seconds: float,
) -> None:
    """Log a retry attempt."""

    exc_name = type(exception).__name__ if exception else "None"
    logger.warning("Retry {}/{} | exception={} wait={:.2f}s", attempt, max_attempts, exc_name, wait_seconds)


def log_error(error: Exception, context: str = "") -> None:
    """Log an error with traceback."""

    logger.exception("Error | context={} type={} message={}", context, type(error).__name__, error)
