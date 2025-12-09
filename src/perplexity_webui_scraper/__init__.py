"""Unofficial Python client for Perplexity AI."""

from importlib.metadata import version

from .config import ClientConfig, ConversationConfig
from .core import Conversation, Perplexity
from .enums import CitationMode, SearchFocus, SourceFocus, TimeRange
from .exceptions import (
    AuthenticationError,
    FileUploadError,
    FileValidationError,
    PerplexityError,
    RateLimitError,
)
from .models import Model, Models
from .types import Coordinates, Response, SearchResultItem


__version__: str = version("perplexity-webui-scraper")

__all__: list[str] = [
    # Main client
    "Perplexity",
    "Conversation",
    # Configuration
    "ConversationConfig",
    "ClientConfig",
    "Coordinates",
    # Enums
    "CitationMode",
    "SearchFocus",
    "SourceFocus",
    "TimeRange",
    # Models
    "Model",
    "Models",
    # Response types
    "Response",
    "SearchResultItem",
    # Exceptions
    "AuthenticationError",
    "FileUploadError",
    "FileValidationError",
    "PerplexityError",
    "RateLimitError",
]
