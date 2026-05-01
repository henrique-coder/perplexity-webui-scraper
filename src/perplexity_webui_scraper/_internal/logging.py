"""Logging configuration using loguru.

Provides a single ``configure_logging()`` entry point called once during
``Perplexity.__init__``, and helper functions for structured log messages
throughout the library.
"""

from __future__ import annotations

from pathlib import Path
from sys import stderr
from typing import TYPE_CHECKING, Any

from loguru import logger


if TYPE_CHECKING:
    from os import PathLike

    from loguru import Logger

    from perplexity_webui_scraper._internal.types import LogLevel


# Remove any default handlers so the library does not emit noise unless
# the caller explicitly enables logging via configure_logging().
logger.remove()

_logging_configured: bool = False


def configure_logging(
    level: LogLevel = "disabled",
    log_file: str | PathLike[str] | None = None,
) -> None:
    """Configure loguru for the ``perplexity_webui_scraper`` namespace.

    Args:
        level: Log verbosity.  ``"disabled"`` suppresses all output (default).
            Any other value maps to the corresponding loguru level.
        log_file: If provided, log output is written to this file path instead
            of stderr.  File is opened in append mode with UTF-8 encoding.
    """
    global _logging_configured  # noqa: PLW0603

    logger.remove()
    level_str = level.upper()

    if level_str == "DISABLED":
        logger.disable("perplexity_webui_scraper")
        _logging_configured = False
        return

    logger.enable("perplexity_webui_scraper")

    console_fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    file_fmt = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message} | {extra}"

    if log_file is not None:
        logger.add(
            Path(log_file),
            format=file_fmt,
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
            format=console_fmt,
            level=level_str,
            colorize=True,
            filter="perplexity_webui_scraper",
        )

    _logging_configured = True


def get_logger(name: str) -> Logger:
    """Return a loguru ``Logger`` bound to the given module name.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A bound logger instance.
    """
    return logger.bind(module=name)


def log_request(
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    body_size: int | None = None,
) -> None:
    """Log an outgoing HTTP request at DEBUG level.

    Args:
        method: HTTP method string (``"GET"``, ``"POST"``, …).
        url: Full request URL.
        params: Query parameters, if any.
        body_size: Request body size in bytes, if applicable.
    """
    logger.debug("HTTP {} {} | params={} body_size={}", method, url, params, body_size)


def log_response(
    method: str,
    url: str,
    status_code: int,
    *,
    elapsed_ms: float | None = None,
) -> None:
    """Log an HTTP response at DEBUG or WARNING level depending on status.

    Args:
        method: HTTP method string.
        url: Request URL.
        status_code: HTTP response status code.
        elapsed_ms: Round-trip time in milliseconds.
    """
    level = "DEBUG" if status_code < 400 else "WARNING"
    elapsed_fmt = f"{elapsed_ms:.2f}" if elapsed_ms is not None else "N/A"
    logger.log(
        level,
        "HTTP {} {} | status={} elapsed_ms={}",
        method,
        url,
        status_code,
        elapsed_fmt,
    )


def log_retry(
    attempt: int,
    max_attempts: int,
    exception: BaseException | None,
    wait_seconds: float,
) -> None:
    """Log a retry attempt at WARNING level.

    Args:
        attempt: Current attempt number (1-based).
        max_attempts: Total allowed attempts.
        exception: The exception that triggered the retry.
        wait_seconds: Seconds to wait before the next attempt.
    """
    exc_name = type(exception).__name__ if exception else "None"
    logger.warning(
        "Retry {}/{} | exception={} wait={:.2f}s",
        attempt,
        max_attempts,
        exc_name,
        wait_seconds,
    )


def log_error(error: Exception, context: str = "") -> None:
    """Log an exception with full traceback at ERROR level.

    Args:
        error: The exception to log.
        context: Optional context string prepended to the log message.
    """
    logger.exception(
        "Error | context={} type={} message={}",
        context,
        type(error).__name__,
        error,
    )
