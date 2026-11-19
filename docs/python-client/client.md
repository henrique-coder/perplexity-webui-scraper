# Client & Account

Pass either a compact `wsk_` credential or a raw `__Secure-pplx.session.<UUIDv4>=<JWE>` cookie pair as `session_token`. Both forms normalize to the same account session. See [Session Token](../token.md) for credential generation, offline conversion, and security guidance.

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

| Parameter       | Type                                  | Default | Description                                                                                     |
| --------------- | ------------------------------------- | ------- | ----------------------------------------------------------------------------------------------- |
| `session_token` | `str`                                 | —       | Compact `wsk_` v1 token or raw `__Secure-pplx.session.<UUIDv4>=<JWE>` cookie pair.              |
| `config`        | <code>ClientConfig &#124; None</code> | `None`  | Optional transport, retry, rate-limit, and logging configuration (`ClientConfig()` if omitted). |

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

| Attribute      | Type                                     | Description                                                     |
| -------------- | ---------------------------------------- | --------------------------------------------------------------- |
| `session`      | `AccountSession`                         | Typed `/api/auth/session` payload.                              |
| `settings`     | <code>AccountSettings &#124; None</code> | Typed `/rest/user/settings` payload when queried as a fallback. |
| `account_tier` | `AccountTier`                            | Normalized tier (`"free"`, `"pro"`, `"max"`, or `"unknown"`).   |

### `AccountSession`

| Attribute                   | Type                                 | Description                                         |
| --------------------------- | ------------------------------------ | --------------------------------------------------- |
| `expires`                   | <code>str &#124; None</code>         | Session expiration timestamp string.                |
| `prevent_username_redirect` | <code>bool &#124; None</code>        | Upstream redirect flag (`preventUsernameRedirect`). |
| `user`                      | <code>AccountUser &#124; None</code> | Authenticated user details.                         |
| `account_tier`              | `AccountTier`                        | Normalized tier derived from `user`.                |

### `AccountUser`

| Attribute             | Type                         | Description                                                   |
| --------------------- | ---------------------------- | ------------------------------------------------------------- |
| `id`                  | <code>str &#124; None</code> | Account UUID.                                                 |
| `email`               | <code>str &#124; None</code> | Account email address.                                        |
| `username`            | <code>str &#124; None</code> | Public username.                                              |
| `name`                | <code>str &#124; None</code> | Display name.                                                 |
| `image`               | <code>str &#124; None</code> | Avatar URL.                                                   |
| `org_uuid`            | <code>str &#124; None</code> | Organization UUID, if any.                                    |
| `org_role`            | <code>str &#124; None</code> | Organization role, if any.                                    |
| `subscription_tier`   | <code>str &#124; None</code> | Raw upstream subscription tier.                               |
| `subscription_status` | <code>str &#124; None</code> | Raw upstream subscription status.                             |
| `subscription_source` | <code>str &#124; None</code> | Raw upstream subscription source.                             |
| `payment_tier`        | <code>str &#124; None</code> | Raw upstream payment tier.                                    |
| `account_tier`        | `AccountTier`                | Normalized tier (`"free"`, `"pro"`, `"max"`, or `"unknown"`). |

### `AccountSettings`

| Attribute             | Type                          | Description                                                   |
| --------------------- | ----------------------------- | ------------------------------------------------------------- |
| `subscription_tier`   | <code>str &#124; None</code>  | Raw subscription tier from user settings.                     |
| `subscription_status` | <code>str &#124; None</code>  | Raw subscription status.                                      |
| `subscription_source` | <code>str &#124; None</code>  | Raw subscription source.                                      |
| `stripe_status`       | <code>str &#124; None</code>  | Stripe subscription state.                                    |
| `revenuecat_status`   | <code>str &#124; None</code>  | RevenueCat subscription state.                                |
| `revenuecat_source`   | <code>str &#124; None</code>  | RevenueCat subscription source.                               |
| `default_model`       | <code>str &#124; None</code>  | Account default model identifier.                             |
| `query_count`         | <code>int &#124; None</code>  | Total query count.                                            |
| `query_count_copilot` | <code>int &#124; None</code>  | Copilot query count.                                          |
| `query_count_mobile`  | <code>int &#124; None</code>  | Mobile query count.                                           |
| `is_verified`         | <code>bool &#124; None</code> | Account verification status.                                  |
| `account_tier`        | `AccountTier`                 | Normalized tier (`"free"`, `"pro"`, `"max"`, or `"unknown"`). |
