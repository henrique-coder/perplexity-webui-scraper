"""Extract AI responses from Perplexity's web interface.

Public API surface — import everything from here::

    from perplexity_webui_scraper import (
        Perplexity,
        Conversation,
        ClientConfig,
        ConversationConfig,
        MODELS,
        Model,
        Response,
        SearchResultItem,
        Coordinates,
        FileInput,
        CitationMode,
        SearchFocus,
        SourceFocus,
        TimeRange,
        LogLevel,
        PerplexityError,
        HTTPError,
        AuthenticationError,
        RateLimitError,
        FileAccessError,
        FileUploadError,
        FileValidationError,
        ResearchClarifyingQuestionsError,
        ModelAccessError,
        ResponseParsingError,
        StreamingError,
    )
"""

from __future__ import annotations

from importlib.metadata import version

from perplexity_webui_scraper._internal.exceptions import (
    AuthenticationError,
    FileAccessError,
    FileUploadError,
    FileValidationError,
    HTTPError,
    ModelAccessError,
    PerplexityError,
    RateLimitError,
    ResearchClarifyingQuestionsError,
    ResponseParsingError,
    StreamingError,
)
from perplexity_webui_scraper._internal.types import (
    CitationMode,
    FileInput,
    LogLevel,
    SearchFocus,
    SourceFocus,
    TimeRange,
)
from perplexity_webui_scraper.config.client import ClientConfig
from perplexity_webui_scraper.config.conversation import ConversationConfig
from perplexity_webui_scraper.core.account import (
    AccountProfile,
    AccountSession,
    AccountSettings,
    AccountTier,
    AccountUser,
)
from perplexity_webui_scraper.core.client import Perplexity
from perplexity_webui_scraper.core.conversation import Conversation
from perplexity_webui_scraper.core.response import Coordinates, Response, SearchResultItem
from perplexity_webui_scraper.models.registry import MODELS
from perplexity_webui_scraper.models.types import Model


__version__: str = version("perplexity-webui-scraper")

__all__: list[str] = [
    "MODELS",
    "AccountProfile",
    "AccountSession",
    "AccountSettings",
    "AccountTier",
    "AccountUser",
    "AuthenticationError",
    "CitationMode",
    "ClientConfig",
    "Conversation",
    "ConversationConfig",
    "Coordinates",
    "FileAccessError",
    "FileInput",
    "FileUploadError",
    "FileValidationError",
    "HTTPError",
    "LogLevel",
    "Model",
    "ModelAccessError",
    "Perplexity",
    "PerplexityError",
    "RateLimitError",
    "ResearchClarifyingQuestionsError",
    "Response",
    "ResponseParsingError",
    "SearchFocus",
    "SearchResultItem",
    "SourceFocus",
    "StreamingError",
    "TimeRange",
]
