"""Public import surface for the Perplexity WebUI client."""

from __future__ import annotations

from importlib.metadata import version

from perplexity_webui_scraper._internal.exceptions import (
    AuthenticationError,
    CompactTokenAlignmentError,
    CompactTokenChecksumError,
    CompactTokenFormatError,
    CompactTokenTruncatedError,
    CredentialError,
    EmbeddedUUIDError,
    FileAccessError,
    FileUploadError,
    FileValidationError,
    HTTPError,
    ModelAccessError,
    ModelRiskWarning,
    ModelStatusError,
    PerplexityError,
    RateLimitError,
    RawCookieFormatError,
    ResearchClarifyingQuestionsError,
    ResponseParsingError,
    SessionTokenError,
    StreamingError,
    UnsupportedTokenVersionError,
)
from perplexity_webui_scraper.auth.session_token import (
    SessionCredentials,
    pack_session_token,
    resolve_session_token,
    unpack_session_token,
    validate_raw_cookie,
)
from perplexity_webui_scraper.config.client import ClientConfig
from perplexity_webui_scraper.config.conversation import ConversationConfig
from perplexity_webui_scraper.config.values import (
    CitationMode,
    LogLevel,
    ResearchInteraction,
    SearchFocus,
    SourceFocus,
    TimeRange,
)
from perplexity_webui_scraper.core.account import (
    AccountProfile,
    AccountSession,
    AccountSettings,
    AccountTier,
    AccountUser,
)
from perplexity_webui_scraper.core.client import Perplexity
from perplexity_webui_scraper.core.conversation import Conversation
from perplexity_webui_scraper.core.file_types import FileInput
from perplexity_webui_scraper.core.response import ActivityEvent, Response, SearchResultItem
from perplexity_webui_scraper.models.registry import MODELS
from perplexity_webui_scraper.models.types import Model, ModelStatus


__version__: str = version("perplexity-webui-scraper")

__all__: list[str] = [
    "MODELS",
    "AccountProfile",
    "AccountSession",
    "AccountSettings",
    "AccountTier",
    "AccountUser",
    "ActivityEvent",
    "AuthenticationError",
    "CitationMode",
    "ClientConfig",
    "CompactTokenAlignmentError",
    "CompactTokenChecksumError",
    "CompactTokenFormatError",
    "CompactTokenTruncatedError",
    "Conversation",
    "ConversationConfig",
    "CredentialError",
    "EmbeddedUUIDError",
    "FileAccessError",
    "FileInput",
    "FileUploadError",
    "FileValidationError",
    "HTTPError",
    "LogLevel",
    "Model",
    "ModelAccessError",
    "ModelRiskWarning",
    "ModelStatus",
    "ModelStatusError",
    "Perplexity",
    "PerplexityError",
    "RateLimitError",
    "RawCookieFormatError",
    "ResearchClarifyingQuestionsError",
    "ResearchInteraction",
    "Response",
    "ResponseParsingError",
    "SearchFocus",
    "SearchResultItem",
    "SessionCredentials",
    "SessionTokenError",
    "SourceFocus",
    "StreamingError",
    "TimeRange",
    "UnsupportedTokenVersionError",
    "pack_session_token",
    "resolve_session_token",
    "unpack_session_token",
    "validate_raw_cookie",
]
