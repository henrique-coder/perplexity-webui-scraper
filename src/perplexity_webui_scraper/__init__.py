"""Extract AI responses from Perplexity's web interface."""

from importlib import metadata

from .config import ClientConfig, ConversationConfig
from .core import Conversation, Perplexity
from .enums import CitationMode, LogLevel, SearchFocus, SourceFocus, TimeRange
from .models import Model, Models
from .types import Coordinates, Response, SearchResultItem


__version__: str = metadata.version("perplexity-webui-scraper")
__all__: list[str] = [
    "CitationMode",
    "ClientConfig",
    "Conversation",
    "ConversationConfig",
    "Coordinates",
    "LogLevel",
    "Model",
    "Models",
    "Perplexity",
    "Response",
    "SearchFocus",
    "SearchResultItem",
    "SourceFocus",
    "TimeRange",
]
