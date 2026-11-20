"""HTTP client and resilience configuration."""

from __future__ import annotations

from os import PathLike  # noqa: TC003
from typing import Annotated, Literal

from curl_cffi.requests import BrowserTypeLiteral  # noqa: TC002
from pydantic import BaseModel, ConfigDict, Field


class ClientConfig(BaseModel):
    """Immutable transport and retry settings for a ``Perplexity`` client.

    Attributes:
        timeout: Request timeout in seconds.
        impersonate: Browser fingerprint profile used by curl-cffi.
        max_retries: Retry attempts for transient errors.
        retry_base_delay: Initial retry backoff in seconds.
        retry_max_delay: Maximum retry delay in seconds.
        retry_jitter: Randomized backoff factor from zero to one.
        rotate_fingerprint: Recreate the HTTP session after a retry.
        requests_per_second: Maximum request rate; zero disables throttling.
        max_init_query_length: Maximum search-init query length; zero disables truncation.
        logging_level: ``"disabled"``, ``"debug"``, ``"info"``, ``"warning"``, ``"error"``, or ``"critical"``.
        log_file: Append logs to this path instead of standard error.
    """

    model_config = ConfigDict(frozen=True)

    timeout: int = 3600
    impersonate: BrowserTypeLiteral = "chrome"
    max_retries: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0
    retry_jitter: float = 0.5
    rotate_fingerprint: bool = True
    requests_per_second: float = 0.5
    max_init_query_length: int = 2000
    logging_level: Annotated[
        Literal["disabled", "debug", "info", "warning", "error", "critical"],
        Field(description='"disabled" suppresses library logs; other values set the minimum emitted severity.'),
    ] = "disabled"
    log_file: str | PathLike[str] | None = None
