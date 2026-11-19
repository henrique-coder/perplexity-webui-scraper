# Client

Pass either a raw `__Secure-pplx.session.<UUIDv4>=<JWE>` cookie pair or a compact `wsk_` credential as `session_token`. Both forms normalize to the same account session. Compact tokens are reversible obfuscation, not encryption or authenticated integrity.

Email authentication emits `wsk_` compact tokens. Convert a raw cookie or validate an existing compact token offline with `perplexity-webui-scraper token convert`, or restore raw cookie form with `perplexity-webui-scraper token deconvert`.

## `Perplexity`

Top-level client for Perplexity WebUI conversations and account introspection. Reuse one client instance per account-scoped session credential. Supports the context-manager protocol (`with Perplexity(...) as client:`).

```python
from perplexity_webui_scraper import ClientConfig, Perplexity

with Perplexity(session_token="YOUR_TOKEN", config=ClientConfig()) as client:
    conversation = client.create_conversation()
    conversation.ask("Hello, world!")
    print(conversation.answer)
```

### Constructor parameters

| Parameter       | Type                   | Default | Description                                                                                     |
| --------------- | ---------------------- | ------- | ----------------------------------------------------------------------------------------------- |
| `session_token` | `str`                  | —       | Raw `__Secure-pplx.session.<UUIDv4>=<JWE>` cookie pair or compact `wsk_` v1 session token.      |
| `config`        | `ClientConfig \| None` | `None`  | Optional transport, retry, rate-limit, and logging configuration (`ClientConfig()` if omitted). |

Raises `SessionTokenError` (a subclass of `PerplexityError` and `ValueError`) if `session_token` is malformed.

### Methods

| Method                         | Returns           | Description                                                                                |
| ------------------------------ | ----------------- | ------------------------------------------------------------------------------------------ |
| `create_conversation(config?)` | `Conversation`    | Create a new conversation thread with optional `ConversationConfig`.                       |
| `get_account_session()`        | `AccountSession`  | Query `/api/auth/session` and return typed session data with normalized `account_tier`.    |
| `get_account_settings()`       | `AccountSettings` | Query `/rest/user/settings` and return typed user and subscription settings.               |
| `get_account_profile()`        | `AccountProfile`  | Return combined account data, querying settings only when the session tier is `"unknown"`. |
| `close()`                      | `None`            | Close the underlying HTTP session and release resources.                                   |

## Account models

`get_account_profile()` returns typed account data from `/api/auth/session` and falls back to `/rest/user/settings` when the session response lacks subscription data. Before each prompt, the client checks whether the selected `available` model requires a higher account tier.

### `AccountProfile`

| Attribute      | Type                      | Description                                                     |
| -------------- | ------------------------- | --------------------------------------------------------------- |
| `session`      | `AccountSession`          | Typed `/api/auth/session` payload.                              |
| `settings`     | `AccountSettings \| None` | Typed `/rest/user/settings` payload when queried as a fallback. |
| `account_tier` | `AccountTier`             | Normalized tier (`"free"`, `"pro"`, `"max"`, or `"unknown"`).   |

### `AccountSession`

| Attribute                   | Type                  | Description                                         |
| --------------------------- | --------------------- | --------------------------------------------------- |
| `expires`                   | `str \| None`         | Session expiration timestamp string.                |
| `prevent_username_redirect` | `bool \| None`        | Upstream redirect flag (`preventUsernameRedirect`). |
| `user`                      | `AccountUser \| None` | Authenticated user details.                         |
| `account_tier`              | `AccountTier`         | Normalized tier derived from `user`.                |

### `AccountUser`

| Attribute             | Type          | Description                                                |
| --------------------- | ------------- | ---------------------------------------------------------- |
| `id`                  | `str \| None` | Account UUID.                                              |
| `email`               | `str \| None` | Account email address.                                     |
| `username`            | `str \| None` | Public username.                                           |
| `name`                | `str \| None` | Display name.                                              |
| `image`               | `str \| None` | Avatar URL.                                                |
| `org_uuid`            | `str \| None` | Organization UUID, if any.                                 |
| `org_role`            | `str \| None` | Organization role, if any.                                 |
| `subscription_tier`   | `str \| None` | Raw upstream subscription tier.                            |
| `subscription_status` | `str \| None` | Raw upstream subscription status.                          |
| `subscription_source` | `str \| None` | Raw upstream subscription source.                          |
| `payment_tier`        | `str \| None` | Raw upstream payment tier.                                 |
| `account_tier`        | `AccountTier` | Normalized tier (`"free"`, `"pro"`, `"max"`, `"unknown"`). |

### `AccountSettings`

| Attribute             | Type           | Description                                                |
| --------------------- | -------------- | ---------------------------------------------------------- |
| `subscription_tier`   | `str \| None`  | Raw subscription tier from user settings.                  |
| `subscription_status` | `str \| None`  | Raw subscription status.                                   |
| `subscription_source` | `str \| None`  | Raw subscription source.                                   |
| `stripe_status`       | `str \| None`  | Stripe subscription state.                                 |
| `revenuecat_status`   | `str \| None`  | RevenueCat subscription state.                             |
| `revenuecat_source`   | `str \| None`  | RevenueCat subscription source.                            |
| `default_model`       | `str \| None`  | Account default model identifier.                          |
| `query_count`         | `int \| None`  | Total query count.                                         |
| `query_count_copilot` | `int \| None`  | Copilot query count.                                       |
| `query_count_mobile`  | `int \| None`  | Mobile query count.                                        |
| `is_verified`         | `bool \| None` | Account verification status.                               |
| `account_tier`        | `AccountTier`  | Normalized tier (`"free"`, `"pro"`, `"max"`, `"unknown"`). |

## Session credential helpers

The top-level package also exports the credential validation and conversion functions used across all entry points:

| Symbol                         | Signature                                          | Description                                                                                |
| ------------------------------ | -------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `SessionCredentials`           | `SessionCredentials(uuid: str, cookie_value: str)` | Frozen dataclass holding the validated RFC 4122 UUIDv4 and JWE cookie value.               |
| `resolve_session_token(token)` | `(str) -> SessionCredentials`                      | Accept either a raw cookie pair or a compact `wsk_` token and return `SessionCredentials`. |
| `validate_raw_cookie(raw)`     | `(str) -> SessionCredentials`                      | Validate a raw UUID-suffixed session cookie and return `SessionCredentials`.               |
| `pack_session_token(raw)`      | `(str) -> str`                                     | Encode a raw session cookie into compact `wsk_` v1 format.                                 |
| `unpack_session_token(token)`  | `(str) -> SessionCredentials`                      | Decode and validate a compact `wsk_` v1 token into `SessionCredentials`.                   |
