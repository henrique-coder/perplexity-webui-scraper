# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0).

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
