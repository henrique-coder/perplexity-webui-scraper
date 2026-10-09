# AGENTS.md — project field guide

Read this before changing code. It explains what this project actually does, which boundaries protect it, and how to verify a change without breaking user-facing contracts.

## What this project is

`perplexity-webui-scraper` is a typed Python library that talks to Perplexity's web interface through undocumented internal endpoints, authenticating with the `__Secure-next-auth.session-token` cookie. It is not an official API client and does not scrape HTML pages. Upstream behavior may change without notice; treat endpoints, payloads, and SSE formats as fragile integration boundaries that need observable behavior and tests.

The package offers four entry points over one shared core:

1. **Python library:** `Perplexity` creates `Conversation` objects. `Conversation.ask()` owns thread state, uploads attachments, supports streaming, and exposes answers and sources.
2. **CLI:** one Typer command (`perplexity-webui-scraper`) delegates to chat, email authentication, API, and MCP commands. Optional extras keep optional dependencies out of the base installation.
3. **OpenAI-compatible REST API:** FastAPI accepts a Perplexity token on each `Authorization: Bearer ...` request, converts messages/configuration, and returns JSON or SSE. Compatibility is intentionally partial: unsupported fields may be ignored and token usage is reported as zero.
4. **MCP server:** registers one tool per catalog model plus a tool for custom model identifiers.

The library uses an existing browser session; it does not automate a browser. Session tokens are account credentials: never log or fixture real tokens, and do not expose the HTTP server to a network without understanding the risk. The API binds to localhost by default; `--host 0.0.0.0` is an explicit operator choice.

## Code map and request flow

- `src/perplexity_webui_scraper/core/`: public client (`client.py`), conversation state/lifecycle (`conversation.py`), uploads (`files.py`), payload construction (`payload.py`), SSE parsing (`parser.py`), response models (`response.py`), and account normalization/access (`account.py`).
- `http/`: curl-cffi transport, session cookie, fingerprinting, rate limiting, retries, and HTTP error translation. Keep transport/authentication mechanics here rather than reimplementing them in consumers.
- `models/` + `_static/models.json`: `Model`, validation, and ordered registry. The JSON is the source of truth for catalog entries, public IDs, MCP tool names, tiers, modes, observed status, and generated model documentation.
- `config/` and `_internal/`: typed configuration, shared aliases/internal values, endpoint constants, and exceptions.
- `api/`: per-request authentication, client/conversation caches, schemas, request conversion helpers, routes, and launcher. `cli/` and `mcp/` are adapters to the core; avoid duplicating business rules there.
- `scripts/`: CI path classification and generation/validation of derived documentation.
- `tests/`: offline tests with synthetic fixtures and mocks. Tests requiring network access or an account must be opt-in and must not be required by the normal suite.
- `docs/`, `README.md`, `CHANGELOG.md`: user documentation and release history. MkDocs builds the Read the Docs site. Catalog tables in `docs/api-reference.md` and `docs/mcp-server.md` are generated.
- Repository root: `pyproject.toml` holds Python configuration/dependencies; `uv.lock` is the lockfile; `Justfile` defines standard commands; `Containerfile*` build API/MCP images; `.github/workflows/` validate, secure, and publish releases.

A request flows through an adapter (CLI/API/MCP), typed configuration and model resolution/acknowledgement, `Conversation` account/entitlement checks and optional upload, payload construction and search initialization, `HTTPClient` calls, then SSE parsing/state updates. The result is exposed as Python response objects, API JSON, or API SSE. Preserve this shared flow and its boundaries when refactoring.

## Contracts that must not change accidentally

### API and compatibility

- Exports from `perplexity_webui_scraper/__init__.py`, model IDs/names, MCP tool names, and configuration fields are user-facing interfaces. Breaking changes require an explicit decision, compatibility tests, documentation, and a changelog entry.
- `Conversation.ask()` returns `self`; with `stream=True`, callers iterate over `Response` snapshots. Do not confuse incremental chunks with the completed answer.
- Conversations retain `backend_uuid` and `read_write_token` for follow-ups. Any changes to resets, retries, streaming, or Deep Research must prove the next prompt continues the same backend thread.
- The parser supports both legacy SSE and the schematized workflow/diff/markdown format. Do not remove compatibility based on one fixture or silently discard a known event shape.
- The API must not fetch remote image URLs. Doing so would create implicit network access and SSRF risk. Base64 data-URL attachments must be validated and bounded before decoding or allocating large buffers.
- CORS is not globally enabled. Do not add it as a convenience without an explicit origin policy.
- API clients are cached by token; conversations are cached by token/thread with a TTL. Tokens must never leak through logs, exceptions, response fields, or public error messages. Consider isolation, resource limits, and concurrency before changing cache/process behavior.

### Models and catalog

- Use only Perplexity's current model-configuration endpoint: `https://www.perplexity.ai/rest/models/config/v2`. Do not use the retired `/rest/models/config` endpoint or invent a catalog snapshot when v2 is unavailable. If v2 is blocked, document the limitation and use redacted WebUI evidence; do not make speculative catalog changes.
- Keep `_static/models.json` ordered with `perplexity/best` and `perplexity/deep-research` first, followed by official WebUI models in current UI order, then historical identifiers newest to oldest. Do not sort by tier, status, or test timestamp.
- `is_official` means only that a model appears in the official picker. Operational status requires evidence: `available`, `unknown`, or `unavailable`. Insufficient account tier does not prove unavailability. New/custom identifiers start as `unknown`; `last_tested_at` is set only to the UTC time of a conclusive test.
- `perplexity/best` selects an internal identifier based on account tier; preserve the behavior in `core/account.py`. Non-available models require `allow_risky_model=True`; do not locally deny those models based on potentially stale tier metadata—the backend makes the final entitlement decision.
- Tests and generated docs derive IDs, counts, statuses, and timestamps from the loaded registry, never from copied catalog snapshots. Use synthetic registries for isolated behavior and reserve literal IDs for explicit public-compatibility tests.
- Before changing `models.json`, also inspect `scripts/render_model_docs.py`, catalog tests, and both generated pages. Run `just model-docs` when updating tables and `just model-docs-check` (or `uv run --no-dev scripts/render_model_docs.py --check`) to verify them.

### Data, files, and security

- Session tokens are secrets. Never put real tokens, cookies, email/2FA codes, private content, session headers, or identifiable request payloads in fixtures, logs, screenshots, examples, or reports.
- Do not read or change `.env` or credential files unless explicitly asked. Redact tokens, account IDs, and private prompts before sharing evidence.
- Treat files as untrusted input. Preserve count/size limits, validation, and error handling in the normal path; do not trust a caller-supplied MIME type alone.
- Do not turn upstream exceptions containing sensitive data into API/CLI errors that reveal tokens, cookies, private data, or entire responses. Keep diagnostic details useful, bounded, and redacted.
- Static checks and builds are not proof of runtime behavior or security. Test trust boundaries and exercise critical paths where possible.

## Working rules for agents

1. **Understand before editing.** Read this guide, relevant README/docs, manifests, and tests. Search for symbol definitions and usages; read the complete files on the affected path. Run `git status --short --branch` and inspect the diff; preserve pre-existing changes.
2. **Audit before restructuring.** For bugs, reproduce the behavior and identify the root cause; add a failing regression test before the fix when practical. For broad refactors, propose phases and preserve contracts. A repository-wide request is not permission for an indiscriminate rewrite.
3. **Keep changes cohesive.** Match local style. Use V4A patches for existing files and the write tool for new files. Do not globally reformat, rename public symbols, remove legacy behavior, change dependencies/lockfiles, or move packages without concrete need and checked usages.
4. **Do not infer dead code from appearance.** A symbol may be public or loaded dynamically; search for all references. Before removing a fallback, wrapper, branch, or historical comment, inspect context and `git blame`. Distinguish confirmed defects from plausible risks and aesthetic preferences.
5. **Comments must earn their place.** Explain why a boundary, workaround, upstream contract, or non-obvious rule exists; do not narrate obvious code. Remove comments only when demonstrably false, duplicated, or obsolete. Update comments/docs when behavior changes.
6. **No implicit external actions.** Do not commit, push, publish, make authenticated network requests, or update remote state without a clear request. Prefer offline tests.
7. **Report scope honestly.** A project audit must distinguish full coverage from sampling. List limitations and verifiable evidence; do not claim to have read every file unless you did.

## Changelog and documentation

- Before editing `CHANGELOG.md`, inspect its opening sections: `Unreleased` (if present) and the next release section. Add one entry per body of work, consolidate already-represented items, and do not rewrite dated history except to correct an explicitly identified factual error. The current file may have no `Unreleased` section; do not invent one for unrelated work.
- Keep repository-authored documentation and comments in English, matching the existing project. When discussing the project with Henrique, use the language he used unless he asks otherwise.
- For user-visible behavior changes, update relevant docs/README and the changelog when appropriate. Do not propagate stale examples across documents.
- `scripts/render_model_docs.py` owns generated catalog sections. Do not hand-edit generated regions without first correcting the generator or its markers.
- Release builds may temporarily render the README for PyPI; the workflow restores the source. Do not commit generated output such as `site/`, `dist/`, `.venv/`, or `node_modules/`.

## Python quality and canonical commands

The supported Python range is `>=3.11,<3.15`; use `uv` and respect the lockfile. Ruff conventions: double quotes, four-space indentation, LF, 120 columns, and Google-style docstrings. `ty` is required; type errors block the change.

- `just format` runs Ruff fixes/formatting, Prettier, and TOML formatting. Run it only when relevant and inspect for unrelated churn.
- `just lint` runs Ruff, `ty`, Prettier, Taplo, `zizmor`, and the generated-catalog check.
- `just test` runs `pytest`.
- `uv run --no-dev --group docs mkdocs build --strict` builds docs.
- `uv build` builds the wheel and sdist; use it when packaging/static assets are affected.
- Fast validation: `uv run --no-sync pytest -q` and `just lint`. For docs/package/build changes, include strict docs build and/or `uv build` as appropriate.
- Re-run relevant checks after the final edit. Report environmental warnings (such as `zizmor` offline mode) separately from test results.

## How to approach refactoring here

A folder reshuffle must solve real coupling, not just express a different preference. First inventory imports, public API, entry points, packaged assets, generated docs, and test coverage. Migrate in reversible steps: extract without behavior changes, add contract tests, update imports/docs, verify wheel/sdist, then remove the old path. Do not remove historical model identifiers without evidence of impact and approval consistent with the compatibility contract.
