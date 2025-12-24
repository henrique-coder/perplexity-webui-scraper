"""Custom exceptions for Perplexity WebUI Scraper."""

from __future__ import annotations


class PerplexityError(Exception):
    """Base exception for all Perplexity-related errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AuthenticationError(PerplexityError):
    """Raised when session token is invalid or expired (HTTP 403)."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message
            or "Access forbidden (403). Your session token is invalid or expired. "
            "Please obtain a new session token from your browser cookies.",
            status_code=403,
        )


class RateLimitError(PerplexityError):
    """Raised when rate limit is exceeded (HTTP 429)."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message or "Rate limit exceeded (429). Please wait a moment before trying again.",
            status_code=429,
        )


class FileUploadError(PerplexityError):
    """Raised when file upload fails."""

    def __init__(self, file_path: str, reason: str) -> None:
        self.file_path = file_path
        super().__init__(f"Upload failed for '{file_path}': {reason}")


class FileValidationError(PerplexityError):
    """Raised when file validation fails."""

    def __init__(self, file_path: str, reason: str) -> None:
        self.file_path = file_path
        super().__init__(f"File validation failed for '{file_path}': {reason}")


class ResearchClarifyingQuestionsError(PerplexityError):
    """Raised when Research mode requires clarifying questions.

    This library does not support programmatic interaction with clarifying questions.
    Consider rephrasing your query to be more specific.

    Attributes:
        questions: List of clarifying questions from the API.
    """

    def __init__(self, questions: list[str]) -> None:
        self.questions = questions
        questions_text = "\n".join(f"  - {q}" for q in questions) if questions else "  (no questions provided)"

        super().__init__(
            f"Research mode is asking clarifying questions:\n{questions_text}\n\n"
            "Programmatic interaction with clarifying questions is not supported. "
            "Please rephrase your query to be more specific."
        )


class ResponseParsingError(PerplexityError):
    """Raised when the API response cannot be parsed.

    Attributes:
        raw_data: The raw data that failed to parse.
    """

    def __init__(self, message: str, raw_data: str | None = None) -> None:
        self.raw_data = raw_data
        super().__init__(f"Failed to parse API response: {message}")


class StreamingError(PerplexityError):
    """Raised when an error occurs during streaming."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Streaming error: {message}")
