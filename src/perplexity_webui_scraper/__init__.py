"""Extract AI responses from Perplexity's web interface."""

from importlib import metadata

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


__version__: str = metadata.version("perplexity-webui-scraper")
__all__: list[str] = [
    "AuthenticationError",
    "CitationMode",
    "ClientConfig",
    "Conversation",
    "ConversationConfig",
    "Coordinates",
    "FileUploadError",
    "FileValidationError",
    "Model",
    "Models",
    "Perplexity",
    "PerplexityError",
    "RateLimitError",
    "Response",
    "SearchFocus",
    "SearchResultItem",
    "SourceFocus",
    "TimeRange",
]
