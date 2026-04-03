# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0).

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
