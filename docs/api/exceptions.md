# Exceptions

All library exceptions inherit from `PerplexityError`, allowing callers to catch the entire family with a single `except PerplexityError` clause. `SessionTokenError` subclasses also inherit from `ValueError`.

```python
from perplexity_webui_scraper import (
    AuthenticationError,
    ModelAccessError,
    ModelStatusError,
    PerplexityError,
    RateLimitError,
    SessionTokenError,
)
```

## Base exception

| Exception         | Attributes     | Description                                                         |
| ----------------- | -------------- | ------------------------------------------------------------------- |
| `PerplexityError` | `message: str` | Base exception for all errors raised by `perplexity-webui-scraper`. |

## Session credentials

Raised when validating raw `__Secure-pplx.session.<UUIDv4>=<JWE>` cookies or compact `wsk_` v1 tokens. All classes in this group inherit from `SessionTokenError` (and therefore both `PerplexityError` and `ValueError`).

| Exception                      | Parent                          | Description                                                                 |
| ------------------------------ | ------------------------------- | --------------------------------------------------------------------------- |
| `SessionTokenError`            | `PerplexityError`, `ValueError` | Base class for malformed raw session cookies and compact `wsk_` tokens.     |
| `CredentialError`              | `SessionTokenError`             | Base class for malformed or ambiguous raw cookie credentials.               |
| `RawCookieFormatError`         | `CredentialError`               | Raw session cookie lacks a valid RFC 4122 UUIDv4 or canonical A256GCM JWE.  |
| `CompactTokenFormatError`      | `SessionTokenError`             | Compact token prefix (`wsk_`), Base62 encoding, or length is invalid.       |
| `CompactTokenTruncatedError`   | `CompactTokenFormatError`       | Compact token binary payload is shorter than the minimum header + JWE size. |
| `CompactTokenAlignmentError`   | `CompactTokenFormatError`       | Compact token header sentinel check failed.                                 |
| `UnsupportedTokenVersionError` | `CompactTokenFormatError`       | Compact token uses an unsupported protocol version.                         |
| `CompactTokenChecksumError`    | `CompactTokenFormatError`       | Compact token BLAKE2s checksum does not match its payload.                  |
| `EmbeddedUUIDError`            | `CompactTokenFormatError`       | Compact token payload does not contain a valid RFC 4122 UUIDv4.             |

## HTTP & account access

| Symbol                | Kind / Parent     | Attributes                                                 | Description                                                                                     |
| --------------------- | ----------------- | ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `HTTPError`           | `PerplexityError` | `status_code: int \| None`, `message: str`                 | Upstream HTTP request returned an unexpected status code or transport failure.                  |
| `AuthenticationError` | `HTTPError`       | `status_code = 403`, `message: str`                        | Session credential was rejected by Perplexity (HTTP 403).                                       |
| `RateLimitError`      | `HTTPError`       | `status_code = 429`, `retry_after: str \| None`            | Perplexity rate limit exceeded (HTTP 429).                                                      |
| `ModelAccessError`    | `PerplexityError` | `model_id: str`, `required_tier: str`, `account_tier: str` | Authenticated account tier is below the selected available model's `min_tier`.                  |
| `ModelStatusError`    | `PerplexityError` | `model_id: str`, `status: str`                             | Model with `"unknown"` or `"unavailable"` status was selected without `allow_risky_model=True`. |
| `ModelRiskWarning`    | `UserWarning`     | —                                                          | Warning emitted when a non-available model is used with `allow_risky_model=True`.               |
| `FileAccessError`     | `PerplexityError` | `account_tier: str`                                        | File attachments were requested on a `"free"` Perplexity account.                               |

## Files, streaming & parsing

| Exception                          | Parent            | Attributes             | Description                                                                                     |
| ---------------------------------- | ----------------- | ---------------------- | ----------------------------------------------------------------------------------------------- |
| `FileValidationError`              | `PerplexityError` | `file_path: str`       | Local file validation failed before upload (missing file, empty content, oversized, bad count). |
| `FileUploadError`                  | `PerplexityError` | `file_path: str`       | Pre-signed S3 upload negotiation or transfer failed.                                            |
| `ResearchClarifyingQuestionsError` | `PerplexityError` | `questions: list[str]` | Deep Research returned clarifying questions when `research_interaction="manual"`.               |
| `ResponseParsingError`             | `PerplexityError` | `message: str`         | Upstream SSE or JSON payload could not be parsed into a valid response structure.               |
| `StreamingError`                   | `PerplexityError` | `message: str`         | SSE stream ended abnormally or reported an upstream streaming failure.                          |
