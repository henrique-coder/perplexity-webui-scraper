# Session Token

!!! warning "Perplexity session credential"

    All entry points — the Python client, CLI, OpenAI-compatible API, and MCP server — accept either a **compact `wsk_` v1 token** or a **raw `__Secure-pplx.session.<UUIDv4>=<JWE>` cookie pair**. Both resolve to the same account cookie. The compact `wsk_` format is reversible obfuscation, not encryption or authenticated integrity; protect either format like an account password. This library reuses an existing Perplexity session and does not authenticate from an arbitrary token without a valid account session.

## Generating a token via CLI

Install the `token` extra (or run directly with `uvx`):

```bash
uv add 'perplexity-webui-scraper[token]'
uv run perplexity-webui-scraper token --email user@example.com

# Or run without adding to a project
uvx --from 'perplexity-webui-scraper[token]' perplexity-webui-scraper token --email user@example.com
```

Omitting `--email` / `-e` prompts interactively. The flow supports a six-digit email verification code or an HTTPS `www.perplexity.ai/api/auth/callback/email` link for the matching account, followed by optional TOTP verification, then prints the compact `wsk_` credential and asks before copying it to the clipboard. Email, verification code/link, and TOTP inputs are shown as typed; only pasted credentials in `token convert` and `token deconvert` are masked.

Malformed verification inputs are rejected locally without making another network request. Invalid verification responses prompt for a fresh code without resending the email or discarding your active login session.

## Offline conversion and validation

Convert between a raw session cookie and a compact `wsk_` token completely offline:

```bash
# Convert a raw cookie pair or validate an existing wsk_ token
perplexity-webui-scraper token convert

# Restore a compact wsk_ token back to its raw cookie pair
perplexity-webui-scraper token deconvert
```

Both commands accept either a compact `wsk_` token or a raw cookie pair, mask only the pasted credential input, ask before copying to the clipboard (defaulting to no), and reject positional arguments so credentials are not exposed in shell history or process listings. Conversion does not encrypt the cookie or improve its security.

## Python credential helpers

The package exports the underlying credential helpers for validation and programmatic conversion:

| Symbol                         | Signature                                          | Description                                                                                |
| ------------------------------ | -------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `SessionCredentials`           | `SessionCredentials(uuid: str, cookie_value: str)` | Frozen dataclass holding the validated RFC 4122 UUIDv4 and JWE cookie value.               |
| `resolve_session_token(token)` | `(str) -> SessionCredentials`                      | Accept either a compact `wsk_` token or a raw cookie pair and return `SessionCredentials`. |
| `validate_raw_cookie(raw)`     | `(str) -> SessionCredentials`                      | Validate a raw UUID-suffixed session cookie and return `SessionCredentials`.               |
| `pack_session_token(token)`    | `(str) -> str`                                     | Accept a raw cookie pair or compact `wsk_` token and return compact `wsk_` v1 format.      |
| `unpack_session_token(token)`  | `(str) -> SessionCredentials`                      | Accept a compact `wsk_` token or raw cookie pair and return `SessionCredentials`.          |
