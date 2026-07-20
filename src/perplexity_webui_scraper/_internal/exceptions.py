"""Custom exception hierarchy for the Perplexity WebUI Scraper library.

All exceptions inherit from ``PerplexityError`` so callers can catch the
entire family with a single ``except PerplexityError`` clause, or narrow
to specific subclasses for fine-grained error handling.
"""

from __future__ import annotations


__all__: list[str] = [
    "AuthenticationError",
    "FileAccessError",
    "FileUploadError",
    "FileValidationError",
    "HTTPError",
    "ModelAccessError",
    "ModelRiskWarning",
    "ModelStatusError",
    "PerplexityError",
    "RateLimitError",
    "ResearchClarifyingQuestionsError",
    "ResponseParsingError",
    "StreamingError",
]


class PerplexityError(Exception):
    """Base exception for all Perplexity-related errors.

    Attributes:
        message: Human-readable error description.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class HTTPError(PerplexityError):
    """Raised when an HTTP request returns an unexpected status code.

    Attributes:
        status_code: HTTP status code, if available.
        url: Request URL, if available.
        response_body: First 500 characters of the response body, if available.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        url: str | None = None,
        response_body: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.url = url
        self.response_body = response_body[:500] if response_body and len(response_body) > 500 else response_body
        super().__init__(message)

    def __repr__(self) -> str:
        return f"HTTPError(status={self.status_code}, url={self.url!r}, message={self.message!r})"


class AuthenticationError(HTTPError):
    """Raised when the session token is invalid or expired (HTTP 403)."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message or "Access forbidden (403). Session token invalid or expired.",
            status_code=403,
        )


class RateLimitError(HTTPError):
    """Raised when the Perplexity rate limit is exceeded (HTTP 429)."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message or "Rate limit exceeded (429). Please wait before retrying.",
            status_code=429,
        )


class ModelAccessError(PerplexityError):
    """Raised when the authenticated account cannot use a selected model."""

    def __init__(self, model_id: str, required_tier: str, account_tier: str) -> None:
        self.model_id = model_id
        self.required_tier = required_tier
        self.account_tier = account_tier
        super().__init__(f"Model {model_id!r} requires a {required_tier} account, but this session is {account_tier}.")


class ModelStatusError(PerplexityError):
    """Raised when a non-available model is used without acknowledgement."""

    def __init__(self, model_id: str, status: str, explanation: str) -> None:
        self.model_id = model_id
        self.status = status
        super().__init__(
            f"Model {model_id!r} has status {status!r}. {explanation} "
            "Set allow_risky_model=True to acknowledge this risk."
        )


class ModelRiskWarning(UserWarning):
    """Warn that an explicitly allowed risky model may fail without notice."""


class FileAccessError(PerplexityError):
    """Raised when the authenticated account cannot use file attachments."""

    def __init__(self, account_tier: str) -> None:
        self.account_tier = account_tier
        super().__init__("File attachments require a paid Perplexity account; this session is free.")


class FileUploadError(PerplexityError):
    """Raised when a file upload to Perplexity's S3 bucket fails.

    Attributes:
        file_path: Display name or path of the file that failed to upload.
    """

    def __init__(self, file_path: str, reason: str) -> None:
        self.file_path = file_path
        super().__init__(f"Upload failed for '{file_path}': {reason}")


class FileValidationError(PerplexityError):
    """Raised when a file fails local validation before upload.

    Attributes:
        file_path: Display name or path of the file that failed validation.
    """

    def __init__(self, file_path: str, reason: str) -> None:
        self.file_path = file_path
        super().__init__(f"File validation failed for '{file_path}': {reason}")


class ResearchClarifyingQuestionsError(PerplexityError):
    """Raised when Research mode requires clarifying questions before answering.

    Perplexity's Deep Research model may return a
    ``RESEARCH_CLARIFYING_QUESTIONS`` SSE step instead of a final answer when
    the query is ambiguous.  The caller should catch this exception, present the
    questions to the user, and retry with a more specific query.

    Attributes:
        questions: List of clarifying question strings extracted from the response.
    """

    def __init__(self, questions: list[str]) -> None:
        self.questions = questions
        formatted = "\n".join(f"  - {q}" for q in questions) if questions else "  (none)"
        super().__init__(
            f"Research mode requires clarification:\n{formatted}\nPlease rephrase your query to be more specific."
        )


class ResponseParsingError(PerplexityError):
    """Raised when the API response cannot be parsed into a known structure.

    Attributes:
        raw_data: Stringified raw response data for debugging, if available.
    """

    def __init__(self, message: str, raw_data: str | None = None) -> None:
        self.raw_data = raw_data
        super().__init__(f"Failed to parse API response: {message}")


class StreamingError(PerplexityError):
    """Raised when an error occurs during SSE streaming."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Streaming error: {message}")
