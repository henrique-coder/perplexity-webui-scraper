"""Logging configuration using loguru.

Provides detailed, structured logging for all library operations.
Logging is disabled by default and can be enabled via ClientConfig.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import TYPE_CHECKING, Any

from loguru import logger

from .enums import LogLevel


if TYPE_CHECKING:
    from os import PathLike

# Remove default handler to start with a clean slate
logger.remove()

# Flag to track if logging is configured
_logging_configured: bool = False


def configure_logging(
    level: LogLevel | str = LogLevel.DISABLED,
    log_file: str | PathLike[str] | None = None,
) -> None:
    """Configure logging for the library.

    Args:
        level: Logging level (LogLevel enum or string). Default is DISABLED.
        log_file: Optional file path to write logs. If set, logs go to file only.
                  If None, logs go to console. Logs are appended, never deleted.

    Note:
        - If log_file is set: logs go to file only (no console output)
        - If log_file is None: logs go to console only
        - Log format includes timestamp, level, module, function, and message
    """

    global _logging_configured  # noqa: PLW0603

    # Remove any existing handlers
    logger.remove()

    # Normalize level to string
    level_str = level.value if isinstance(level, LogLevel) else str(level).upper()

    if level_str == "DISABLED":
        # Logging disabled, add a null handler to suppress all output
        logger.disable("perplexity_webui_scraper")
        _logging_configured = False
        return

    # Enable the logger
    logger.enable("perplexity_webui_scraper")

    # Console format - concise but informative
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # File format - detailed with extra context
    file_format = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message} | {extra}"

    if log_file is not None:
        # Log to file only (no console output)
        log_path = Path(log_file)
        logger.add(
            log_path,
            format=file_format,
            level=level_str,
            rotation=None,  # Never rotate
            retention=None,  # Never delete
            compression=None,  # No compression
            mode="a",  # Append mode
            encoding="utf-8",
            filter="perplexity_webui_scraper",
            enqueue=True,  # Thread-safe
        )
    else:
        # Log to console only (no file)
        logger.add(
            sys.stderr,
            format=console_format,
            level=level_str,
            colorize=True,
            filter="perplexity_webui_scraper",
        )

    _logging_configured = True


def get_logger(name: str) -> Any:
    """Get a logger instance bound to the given module name.

    Args:
        name: Module name (typically __name__).

    Returns:
        A loguru logger instance bound to the module.
    """

    return logger.bind(module=name)


# Convenience shortcuts for common log operations
def log_request(
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    body_size: int | None = None,
) -> None:
    """
    Log an outgoing HTTP request with full details.
    """

    logger.debug(
        "HTTP request initiated | method={method} url={url} params={params} "
        "headers_count={headers_count} body_size={body_size}",
        method=method,
        url=url,
        params=params,
        headers_count=len(headers) if headers else 0,
        body_size=body_size,
    )


def log_response(
    method: str,
    url: str,
    status_code: int,
    *,
    elapsed_ms: float | None = None,
    content_length: int | None = None,
    headers: dict[str, str] | None = None,
) -> None:
    """
    Log an HTTP response with full details.
    """

    level = "DEBUG" if status_code < 400 else "WARNING"
    logger.log(
        level,
        "HTTP response received | method={method} url={url} status={status_code} "
        "elapsed_ms={elapsed_ms:.2f} content_length={content_length}",
        method=method,
        url=url,
        status_code=status_code,
        elapsed_ms=elapsed_ms or 0,
        content_length=content_length,
    )


def log_retry(
    attempt: int,
    max_attempts: int,
    exception: BaseException | None,
    wait_seconds: float,
) -> None:
    """
    Log a retry attempt.
    """

    logger.warning(
        "Retry attempt | attempt={attempt}/{max_attempts} exception={exception_type}: {exception_msg} "
        "wait_seconds={wait_seconds:.2f}",
        attempt=attempt,
        max_attempts=max_attempts,
        exception_type=type(exception).__name__ if exception else "None",
        exception_msg=str(exception) if exception else "None",
        wait_seconds=wait_seconds,
    )


def log_cloudflare_detected(status_code: int, markers_found: list[str]) -> None:
    """
    Log Cloudflare challenge detection.
    """

    logger.warning(
        "Cloudflare challenge detected | status_code={status_code} markers={markers}",
        status_code=status_code,
        markers=markers_found,
    )


def log_fingerprint_rotation(old_profile: str, new_profile: str) -> None:
    """
    Log browser fingerprint rotation.
    """

    logger.info(
        "Browser fingerprint rotated | old_profile={old} new_profile={new}",
        old=old_profile,
        new=new_profile,
    )


def log_rate_limit(wait_seconds: float) -> None:
    """
    Log rate limiting wait.
    """

    logger.debug(
        "Rate limiter throttling | wait_seconds={wait_seconds:.3f}",
        wait_seconds=wait_seconds,
    )


def log_session_created(impersonate: str, timeout: int) -> None:
    """
    Log HTTP session creation.
    """

    logger.info(
        "HTTP session created | browser_profile={profile} timeout={timeout}s",
        profile=impersonate,
        timeout=timeout,
    )


def log_conversation_created(config_summary: str) -> None:
    """
    Log conversation creation.
    """

    logger.info(
        "Conversation created | config={config}",
        config=config_summary,
    )


def log_query_sent(query: str, model: str, has_files: bool) -> None:
    """
    Log a query being sent.
    """

    logger.info(
        "Query sent | model={model} has_files={has_files} query_preview={query_preview}",
        model=model,
        has_files=has_files,
        query_preview=query[:100] + "..." if len(query) > 100 else query,
    )


def log_stream_chunk(chunk_size: int, is_final: bool) -> None:
    """
    Log a streaming chunk received.
    """

    logger.debug(
        "Stream chunk received | size={size} is_final={is_final}",
        size=chunk_size,
        is_final=is_final,
    )


def log_error(error: Exception, context: str = "") -> None:
    """
    Log an error with full traceback.
    """

    logger.exception(
        "Error occurred | context={context} error_type={error_type} message={message}",
        context=context,
        error_type=type(error).__name__,
        message=str(error),
    )
