# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0).

## [Unreleased]

### Fixed

- **Deep Research automation:** Deep Research now automatically answers clarification prompts using reasonable assumptions and continues the same conversation once. Set `research_interaction="manual"` to retain the exception-based flow.
- **API CORS policy:** Removed the wildcard CORS configuration so arbitrary browser origins cannot access the local API.
- **Authentication examples:** Updated `curl` examples to read session tokens from `PERPLEXITY_SESSION_TOKEN` instead of embedding token-shaped literals.

## [1.1.5] - 2026-08-18

### Changed

- **Dependency layout:** Modernized project metadata with PEP 639 licensing, completed the API, test, lint, hook, and workflow groups, removed the private `examples` group, and kept rounded minimum versions with upper bounds only for the build backend and compatibility-sensitive packages.
- **API tests:** Replaced the direct HTTPX test dependency with Niquests' in-process ASGI session. The library continues to use curl-cffi for Perplexity requests.
- **Development commands:** Updated CI and Justfile commands to install only the extras and dependency groups required by each check, including workflow linting with zizmor.
- **Model registry:** Synchronized the official WebUI models with the v2 configuration, recorded successful health checks for Gemini 3.7 Flash and Grok 4.6 variants, and kept GLM 5.2 represented as a thinking-only model.
- **Project text:** Corrected unsupported compatibility claims, stale examples, inaccurate descriptions, CLI messages, API metadata, comments, and docstrings across current project files.

## [1.1.4] - 2026-08-05

### Added

- **Claude Opus 5:** Added the Max-tier Claude Opus 5 and Claude Opus 5 Thinking entries from Perplexity's current model configuration.
- **Kimi K3:** Added and live-tested the Pro-tier Kimi K3 Thinking identifier from Perplexity's current model configuration.

### Fixed

- **Schematized SSE parsing:** Added support for the WebUI's `workflow_block` and incremental `diff_block` stream events when no top-level `text` field is present.
- **Current WebUI streaming:** Requests now use the schematized stream with incremental text chunks, while retaining legacy response parsing for compatibility.

### Changed

- **Model metadata:** Synchronized registered model names, descriptions, and providers with Perplexity's `/rest/models/config/v2` response, separated official WebUI listing (`is_official`) from operational status, and recorded UTC results from Pro-account streaming probes for all 75 catalog entries. The 17 official models are `available`; 73 entries are `available` and two historical Claude Haiku identifiers are `unavailable` after three failed probes each. Registry tests and generated catalogs now derive their metadata instead of relying on hardcoded snapshots.

### Removed

- **Ambiguous model state:** Removed `unstable`; model status now represents only observed availability as `available`, `unknown`, or `unavailable`.

## [1.1.3] - 2026-07-20

### Added

- **Grok 4.5:** Added the Pro-tier Grok 4.5 and Grok 4.5 Thinking models after successful live probes against both picker identifiers.
- **Model test timestamps:** Added nullable `last_tested_at` metadata with the UTC instant of the test supporting each model status.
- **Generated model catalog:** API and MCP documentation tables are now rendered from `models.json`, keeping runtime tools and documentation aligned with one source of truth.

### Changed

- **Python compatibility:** Restored support for Python 3.11; the supported runtime range is now 3.11 through 3.14. Python 3.15 remains unsupported until the MCP dependency chain supports it.
- **Release workflow:** Release candidates are now validated explicitly from `prod`; public publication requires a second, deliberate `publish` dispatch and runs PyPI, container, documentation, tag, and GitHub Release in a recoverable order.
- **Model safety controls:** Python, CLI, OpenAI-compatible API, and MCP now use the single `allow_risky_model` acknowledgement for every non-available model. Acknowledged models defer the final entitlement decision to Perplexity, preventing stale local tier metadata from causing false denials.
- **Development workflow:** Added a `dev` integration branch, PR-only production promotions, cross-platform CI, release-policy validation, and automated CodeQL/dependency review.

### Fixed

- **Model compatibility:** Restored public model IDs and MCP tool names removed in v1.1.2 even though their backend identifiers remain available.
- **Container startup:** API and MCP images now execute the installed virtual-environment entry point directly instead of resolving and installing development dependencies through `uv run` at startup.

## [1.1.2] - 2026-07-10

### Added

- **Community health files:** Added code of conduct, contributing guide, security policy, support guide, funding metadata, issue forms, and pull request template.
- **Current Perplexity UI models:** Added GPT-5.6 Terra, GPT-5.6 Terra Thinking, GPT-5.6 Sol, GPT-5.6 Sol Thinking, Claude Sonnet 5, Claude Sonnet 5 Thinking, Claude Opus 4.8, Claude Opus 4.8 Thinking, and Nemotron 3 Ultra to the JSON-backed model registry.

### Changed

- **Project metadata:** Added README community links and PyPI project URLs for discussions, funding, and security policy.
- **Model metadata:** Updated bundled model descriptions, display names, API docs, MCP tool tables, README model count, usage examples, and registry tests to match the current Perplexity model configuration.

### Removed

- **Retired UI models:** Removed GPT-5.4, GPT-5.4 Thinking, GPT-5.5 Thinking, Claude Sonnet 4.6, Claude Sonnet 4.6 Thinking, Claude Opus 4.7, and Claude Opus 4.7 Thinking from the bundled registry and documentation because they no longer appear in the Perplexity UI picker.

## [1.1.1] - 2026-07-02

### Fixed

- **Release workflow:** Removed the unstable native executable build matrix and simplified releases to publish only the Python wheel, source distribution, and optional GHCR container images.
- **Release ordering:** GitHub Releases are created before PyPI publishing, and Docker images are published only after PyPI succeeds.
- **CI caching:** Added explicit pnpm store caching to CI and kept Docker layer caching on the remaining container publish jobs.
- **API dependency:** Updated the optional FastAPI extra to the `0.139.x` series.

### Removed

- **Native binary distribution:** Removed Nuitka-based standalone executable builds, `.7z` release assets, executable smoke tests, and the build-only dependency group.
- **CLI diagnostics:** Removed the temporary `perplexity-webui-scraper doctor` command that existed only to validate standalone executable bundles.

## [1.1.0] - 2026-06-30

### Added

- **GLM 5.2 model:** Added Z.ai GLM 5.2 to the JSON-backed model registry and MCP/API documentation.
- **Typed account profile API:** Added `Perplexity.get_account_session()`, `get_account_settings()`, and `get_account_profile()` plus Pydantic account models backed by Perplexity's `/api/auth/session` and `/rest/user/settings` endpoints.
- **Model registry integrity tests:** Added coverage that validates the bundled JSON model registry, rejects duplicate model IDs, rejects duplicate MCP tool names, and forbids unexpected model fields.
- **Container build context hygiene:** Added `.dockerignore` to keep local virtualenvs, debug files, caches, build outputs, and Node dependencies out of container build contexts.
- **Unified CLI test coverage:** Added `tests/test_cli.py` to verify root help output and lazy delegation for `token`, `api`, and `mcp` subcommands.
- **Native executable release pipeline:** Added GitHub Actions matrix builds that package standalone, optimized executables for Linux AMD64, Linux ARM64, macOS ARM64, and Windows AMD64 using Nuitka.
- **Optional MCP container image:** Added `Containerfile.mcp` plus GHCR publishing for explicit MCP tags (`mcp`, `X.Y.Z-mcp`, `vX.Y.Z-mcp`) alongside the default API image.
- **Manual publish workflow controls:** Added `workflow_dispatch` inputs for version override plus selective publish toggles for PyPI, GHCR (Podman), and GitHub Releases.
- **Executable branding assets:** Added packaged application icons for Windows (`.ico`) and macOS (`.icns`) release builds.
- **TOTP 2FA support in session token generation:** The `perplexity-webui-scraper token` CLI wizard now handles Perplexity accounts with TOTP-based two-factor authentication. After email OTP verification, the CLI detects the TOTP challenge redirect, prompts for the authenticator app code, and completes the login flow automatically.
- **`chat` CLI command:** New interactive REPL command `perplexity-webui-scraper chat "query"` for querying Perplexity AI directly from the terminal with real-time streaming token output via Rich Live panels. It maintains the conversation context until exited and features a clean, borderless UX inspired by Claude Code. Supports all `ConversationConfig` options as CLI arguments with short aliases, file attachments, clipboard copy, and raw output mode.
- **`chat setup` subcommand:** Interactive setup wizard that configures and saves the session token (Fernet-encrypted in the platform-specific config directory) and the default model. First-time users are guided to configure their token before using `chat`.
- **`all` optional dependency extra:** New `[all]` meta-extra that installs all optional dependencies (`cli`, `api`, `mcp`) in one go: `uv add "perplexity-webui-scraper[all]"`.
- **Encrypted token storage:** Session tokens are now encrypted with Fernet and stored in the platform-specific config directory (`platformdirs`). The `chat` command reads from this store automatically.

### Changed

- **API server consolidation:** Removed the duplicated legacy API implementation and standardized the package on `api.app`, `api.routes.*`, `api.schemas.*`, `api.helpers`, `api.auth`, and `api.conversation_cache`.
- **Model typing:** Hardened JSON-backed model metadata with explicit tier/mode literals, immutable strict Pydantic validation, duplicate detection, and field factories for mutable response defaults.
- **HTTP resilience:** Translated HTTP status failures inside the retry loop so 429 responses are retried as `RateLimitError`, and switched retry jitter to `random.uniform`.
- **CLI validation:** The `chat` command now rejects partial coordinates and renders streaming `last_chunk` content when a final `answer` is not yet available.
- **Build dependencies:** Replaced open-ended build dependency lower bounds with compatible-release ranges and removed the duplicate `pre-commit` dependency group.
- **Documentation:** Updated README and MkDocs pages to use `chat`/`chat setup`, current MCP tool names, current model IDs, and the explicit API/MCP Containerfile split.
- **Model tier enforcement:** Prompt requests now perform a fast account-session check before sending the prompt, fall back to user settings when needed, and raise `ModelAccessError` when a model requires a higher tier. REST API, CLI, MCP, and Python usage now surface the same tier-denial rule.
- **Free account attachment guard:** File attachments are blocked with `FileAccessError` before upload when the authenticated account is free.
- **Best model default:** `perplexity/best` now resolves by account tier: free accounts use Perplexity's internal `turbo` preference, while Pro/Max accounts use `pplx_pro_upgraded`; both use `copilot` mode.
- **CI Workflows:** Updated `ci.yml` to use `pnpm/action-setup`, restrict `uv sync` to the `test` and `lint` groups with `--frozen`, and execute `just format` and `just lint` directly.
- **CLI surface simplified:** Replaced the legacy `get-perplexity-session-token`, `perplexity-webui-scraper-api`, and `perplexity-webui-scraper-mcp` scripts with one canonical `perplexity-webui-scraper` command exposing `token`, `api`, and `mcp` subcommands.
- **Dependency layout:** Moved `typer` into base dependencies so the unified root CLI is always available.
- **MCP startup guidance:** Updated missing-token runtime messaging to reference `PERPLEXITY_SESSION_TOKEN=<token> perplexity-webui-scraper mcp`.
- **Container entrypoint:** Updated the default API container to launch `perplexity-webui-scraper api` instead of the removed legacy command.
- **Release workflow architecture:** Refactored publish automation into separate package, executable, Container, PyPI, and GitHub Release jobs with artifact passing between them.
- **Executable builder choice:** Standardized executable packaging on Nuitka for optimized, high-performance C-compiled binaries and faster CI builds.
- **Container publishing:** The default GHCR image remains API-first (`latest`, `X.Y.Z`, `vX.Y.Z`, semver tags), while MCP publishing is now opt-in via `-mcp` tags.
- **Documentation:** Updated README and docs to consistently use the unified CLI commands, published API container image, and optional MCP container image.

### Removed

- **Legacy API modules:** Removed `perplexity_webui_scraper.api.server`, `perplexity_webui_scraper.api.models`, and `perplexity_webui_scraper.api.cli`.
- **Legacy console scripts:** Dropped generation and documentation of the three previous standalone command entry points.

## [1.0.2] - 2026-05-01

### Fixed

- **Model Registry:** Corrected Anthropic models by replacing Claude Opus 4.6 with the newly released Claude Sonnet 4.6 (and its Thinking variant). Adjusted the tier requirement from `max` to `pro`.

---

## [1.0.1] - 2026-05-01

### Added

- **Automated API Documentation:** Integrated `mkdocstrings[python]` into the MkDocs Material setup. Seven dedicated pages under `docs/api/` now render API docs directly from Google-style docstrings — covering the client, conversation, configuration models, response models, model registry, type aliases, and exception hierarchy.
- **`just docs` recipe:** Added a `docs` Justfile task that runs `mkdocs serve --watch docs --watch src` for hot-reloading local documentation previews.
- **`.prettierignore`:** Added rule to exclude `docs/api/` from Prettier formatting, preventing it from escaping underscores in `:::` mkdocstrings directives.

### Changed

- **API server startup banner:** Replaced `typer.echo` with a Rich `Panel` (via `rich.console.Console`) in both `api/cli.py` and `api/launcher.py`. The panel now shows server URL, docs, ReDoc, and auth format with icons and styled text.
- **Import style:** Standardised all bare `import X` statements across the codebase to `from X import Y` form (`orjson`, `os`, `uvicorn`) for consistency with the project-wide style guide.
- **Clipboard copy default:** Changed the `get-perplexity-session-token` clipboard prompt from opt-out (`[Y/n]`) to opt-in (`[y/N]`), defaulting to `False`.
- **`uvicorn` import guard removed:** The `try/except ImportError` probe for `uvicorn` in `api/cli.py` and `api/launcher.py` has been removed. `uvicorn` is now imported unconditionally at the top of the module alongside other dependencies.
- **Model display name:** Updated `perplexity/best` model `name` from `"Pro"` to `"Best"` and MCP `tool_name` from `pplx_ask` to `pplx_best` in `_static/models.json`.
- **`mkdocstrings[python]`** added to the `docs` dependency group in `pyproject.toml`.
- **`mkdocs.yml`:** Registered the `mkdocstrings` plugin with Google-style handler options (`merge_init_into_class`, `separate_signature`, `signature_crossrefs`, `unwrap_annotated`, private member filter). Navigation expanded with a nested **Python API** section.

---

## [1.0.0] - 2026-04-30

### 🚨 MAJOR BREAKING CHANGES (v1.0.0 Stable Release)

- **Ground-up Architectural Refactor:** The codebase was structurally rewritten from flat files into a modular `src/` layout with isolated domains (`api/`, `cli/`, `config/`, `core/`, `http/`, `mcp/`, `models/`, and `_internal/`). Old imports from `< 0.8.0` are fundamentally broken.
- **Python >= 3.12 constraint:** Raised the minimum Python requirement to utilize modern constructs like PEP 695 generics (`[T]`) and structural pattern matching (`match`/`case`).

### Added

- **Containerization Support:** Added an Alpine-based `Containerfile` and direct `Justfile` tasks (`build-container`, `run-container`, `stop-container`) for frictionless API deployment via Podman.
- **Advanced TLS Fingerprinting:** Integrated `curl_cffi` as the core HTTP backend, swapping out `requests` to provide browser-grade TLS fingerprints that natively bypass bot-detection algorithms.
- **JSON-Backed Model Registry:** Migrated the hardcoded models introduced in 0.8.0 to a dynamically loaded `_static/models.json` architecture.
- **Structured Logging:** Integrated `loguru` to handle all internal console outputs with structured, filtered logging instead of standard `print()`.
- **Rich CLI UX:** Restored `pyperclip` and added `rich` to the `[cli]` optional dependency group. The `get-perplexity-session-token` script now features a beautiful Typer-based terminal UI and automatically copies the captured token directly to the clipboard.
- **Strict Typing Enforcement:** Adopted `ty` as the definitive static type checker and rigidly enforced pure Google-style docstrings via `ruff` across all modules.

### Changed

- Re-architected Pydantic schemas by stripping all `Field()` metadata (previously added in 0.8.0), migrating entirely to native, clean type hints.
- Exported the `Coordinates` class directly to `_internal/types.py` to eradicate circular dependencies between conversation and response modules.

### Removed

- Removed all flat source files from the project root (`core.py`, `models.py`, `http.py`, etc) as they were completely replaced by the new package structure.

---

## [0.8.0] - 2026-04-12

### Added

- **Model Registry Rewrite:** Replaced the raw dictionary with a robust `ModelRegistry(BaseModel)` singleton. Includes iterative safe lookup via `MODELS.resolve("model-id")` and direct attribute access (`MODELS.gpt_5_4`), ensuring full type safety and IDE autocompletion for models.
- **Pydantic Descriptions:** Implemented `Field(description=...)` for all parameters across all models (`config.py`, `types.py`, `models.py`), guaranteeing perfect IDE hover hints natively linked to Pylance/Pyright.
- Added `[tool.pyright]` configuration inside `pyproject.toml` so IDEs correctly auto-detect and resolve `pydantic` types generated by the `.venv` out-of-the-box.
- Added `space_uuid` parameter to `ConversationConfig` to route conversations into a specific Perplexity Space (collection).

### Changed

- **CLI Authentication (`get-perplexity-session-token`)**: Removed `.env` logic completely. Refactored to safely copy the session token straight to the user's clipboard utilizing `pyperclip`. Standardized "copy" prompt as default `[Y/n]` and implemented ephemeral screens.
- Enforced a universal parameter ordering across all config models: required fields first, directly followed by importance-sorted optionals.
- Simplified core docstrings to targeted single-liners for cleaner IDE overlays.

### Removed

- Removed the `title` property from `Conversation` and the `title` field from `Response` — they have been non-functional for a long time and were never reliably populated by the API.

## [0.7.1] - 2026-04-03

### Changed

- Updated default examples and documentation across the codebase to feature the GPT-5.4 model instead of the deprecated variations.
- Updated dependencies `requests` (to 2.33.0) and `cryptography` (to 46.0.6) via dependabot.

### Removed

- Removed deprecated models: Gemini 3 Flash (`gemini-3-flash`), Gemini 3 Flash Thinking (`gemini-3-flash-thinking`), Grok 4.1 (`grok-4.1`), e Grok 4.1 Thinking (`grok-4.1-thinking`).

## [0.7.0] - 2026-03-22

### Added

- Introduced a drop-in **OpenAI-compatible REST API** server (`[api]` extra) using FastAPI.
- Added full support for multimodal messages (text and base64-encoded image URLs) via the new API. This uses the standard OpenAI Vision schema, making it natively compatible with any generic chatbot frontend (e.g. Open WebUI, AnythingLLM, LibreChat).
- Implemented per-request authentication using the `Authorization: Bearer <token>` header, aligning with industry standards.
- Engineered a client cache mechanism to reuse Perplexity clients across requests with the same token, significantly boosting performance.
- Introduced the `perplexity` extension payload block to pass Perplexity-specific parameters inside native OpenAI requests.

### Changed

- **Refactored Enums to Strings**: All Enums (`CitationMode`, `SearchFocus`, `SourceFocus`, `TimeRange`, `LogLevel`) have been entirely removed and replaced with intuitive lowercase string literals (e.g., `"web"`, `"academic"`, `"finance"`, `"all"`).
- Re-architected `core.py` to seamlessly map the new intuitive user-facing string literals to Perplexity's hidden internal backend strings (`"scholar"`, `"edgar"`, etc).
- Refactored `mcp/server.py` and `api/server.py` to enforce the new type-safe Literal strings and eliminate dictionary lookups.
- Migrated default logging to use lowercase `LogLevel` strings safely parsed by Pydantic at runtime.
- Simplified `example.py` configuration snippets using the updated standard literals.

### Removed

- Deleted the `enums.py` file completely.
- Removed legacy CLI arguments handling session tokens dynamically via parameters or `.env` to enforce secure per-request Bearer authentication.

## [0.6.4] - 2026-03-22

### Changed

- Disabled appending inline source citations in the MCP server responses to optimize context token consumption.
- Bumped development dependencies (`mkdocs-material`, `ruff`, and `ty`) to their latest versions.

### Fixed

- Refactored exception handling in `server.py` to enforce explicit return statements inside `try...else` blocks.

## [0.6.3] - 2026-03-16

### Added

- Added NVIDIA's Nemotron 3 Super Thinking (`nv-nemotron-3-super-thinking`) reasoning model.
- Introduced `[cli]` optional dependency group for terminal-based utilities.
- Implemented enhanced GitHub Release body formatting: rounded contributor avatars, open-by-default commit history, and improved paragraph spacing.

### Changed

- Replaced Moonshot AI's `Kimi K2.5 Thinking` with NVIDIA's `Nemotron 3 Super Thinking` in the model catalog.
- Updated MCP server tool registration: `pplx_kimi_k25_think` is now `pplx_nemotron3_super_think`.
- Refactored dependencies: moved `rich` to `[cli]` extras to ensure the core library remains lightweight.
- Standardized all documentation and installation guides to exclusively recommend `uv` and `uvx`.

### Fixed

- Repaired broken Markdown table syntax in `docs/api-reference.md` caused by unescaped union type pipes.
- Resolved documentation layout issues including misaligned table headers and spacing bugs.
- Fixed a type-checking edge case in `_upload_file` by explicitly casting paths during content reads.

## [0.6.2] - 2026-03-13

### Added

- Created complete native documentation site using MkDocs Material.
- Automated setup for GitHub Pages with native zero-branch action deployment instead of legacy `gh-pages` clones.

### Changed

- Refactored `core.py` to enable concurrent thread-pooled file uploads, supporting huge attachments in parallel without network blocking/latency.
- Updated argument validation pipelines using strict Python 3.10+ `match`/`case` structural pattern matching instead of explicit type tracking instances.
- Neutralized hardcoded workflow rules and environment references in `AGENTS.md` to be fully cross-platform.
- Restructured `pyproject.toml` allocating `mkdocs` to an isolated `docs` dependency group for clean CI/CD sync boundaries.

### Fixed

- Replaced ambiguous `# type: ignore` suppresses with explicit and defensive runtime assertion typings in HTTP resilience retry mechanics.

## [0.6.1] - 2026-03-12

### Changed

- Bumped project version to 0.6.1 to match existing current stable version.
