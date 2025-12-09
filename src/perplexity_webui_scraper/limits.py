"""Upload and request limits for Perplexity WebUI Scraper."""

from __future__ import annotations

from typing import Final


# File Upload Limits
MAX_FILES: Final[int] = 30
"""Maximum number of files that can be attached to a single prompt."""

MAX_FILE_SIZE: Final[int] = 50 * 1024 * 1024  # 50 MB in bytes
"""Maximum file size in bytes (50 MB)."""

# Request Limits
DEFAULT_TIMEOUT: Final[int] = 30 * 60  # 30 minutes in seconds
"""Default request timeout in seconds (30 minutes).

Set high to accommodate complex models that may take longer to respond.
"""
