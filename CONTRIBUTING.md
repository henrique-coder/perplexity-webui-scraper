# Contributing

Thank you for considering a contribution to `perplexity-webui-scraper`.

This project wraps private Perplexity WebUI endpoints. Changes should be conservative, well-tested, and documented because upstream behavior can change without notice.

## Before Opening an Issue

- Search existing issues first.
- Make sure you are using the latest released version.
- Check the documentation at <https://perplexity-webui-scraper.readthedocs.io>.
- Do not include session tokens, cookies, account IDs, private prompts, or private files in public issues.

## Development Setup

Requirements:

- Python `>=3.11, <3.16`. `.python-version` selects Python 3.15 for local development. CI tests each supported minor version; CI quality and package-build jobs use Python 3.14. API/MCP containers use Python 3.15.
- `uv`
- `pnpm`
- `just`

Install all development dependencies:

```bash
uv sync --all-extras --all-groups
pnpm install
```

CI quality, documentation, and package-build jobs use Python 3.14. The unit-test matrix covers Python 3.11 through 3.15 across three operating systems; API/MCP container images use Python 3.15.

Useful commands:

| Command                                                    | Purpose                                                                |
| ---------------------------------------------------------- | ---------------------------------------------------------------------- |
| `just format`                                              | Format Python, Markdown, YAML, TOML, and related project files.        |
| `just lint`                                                | Run Ruff, ty, Prettier, Taplo, workflow, and generated-catalog checks. |
| `just test`                                                | Run the pytest suite using the `.python-version` runtime.              |
| `uv run --only-group docs zensical build --clean --strict` | Build docs; `--strict` fails on warnings.                              |
| `uv build`                                                 | Build the source distribution and wheel.                               |

Install the Git hook once per checkout:

```bash
uv run --only-group hooks prek install --hook-type pre-push
```

The `just lint` check runs at `git push`, not at `git add` or `git commit`. CI remains authoritative. Use `git push --no-verify` only after running the checks manually.

`zensical` is the documentation generator used by this project. The command above does not publish anything; it only verifies that the local documentation can be built successfully.

## Pull Request Checklist

### Branch workflow

- `dev` is the default integration branch. Create feature and fix branches from `dev`, and open normal pull requests back into `dev`.
- `prod` contains only release-ready code. Do not push to it directly or target it from feature branches.
- Promote a release with a same-repository pull request from `dev` to `prod` after version, changelog, tests, documentation, and package build are ready.
- After a release promotion, continue new work from the updated `dev` branch.

### Release workflow

1. Keep the target section in `CHANGELOG.md` as `## [X.Y.Z] - Unreleased` while developing.
2. In the final `dev` to `prod` promotion PR, replace `Unreleased` with the UTC release date (`YYYY-MM-DD`).
3. On `prod`, run **Publish Release** once in `validate` mode, review its build output, then rerun it with `publish` selected.
4. The workflow publishes the Python package and API/MCP images before creating the immutable tag and GitHub Release. Read the Docs builds and publishes documentation through its configured Git integration; it is not published by the release workflow. The release workflow can resume after an interrupted PyPI publication.

- Keep changes focused on one concern.
- The chat-generation contract is `POST /v1/chat/completions` only; keep `GET /v1/models` available. API contract changes require compatibility tests, docs, and a changelog entry.
- Accept account credentials only as a valid raw UUIDv4 session-cookie/JWE pair or compact `wsk_` v1 token. The compact form is reversible obfuscation, not encryption or authenticated integrity.
- When removing compatibility code for a breaking release, verify imports and public callers, then update docs, changelog, and contract tests. Keep upstream parser formats only while they remain observed and tested.
- Add or update tests for behavior changes.
- Update README, documentation pages, and `CHANGELOG.md` when user-facing behavior changes.
- Keep model metadata in `src/perplexity_webui_scraper/_static/models.json`.
- Do not commit local secrets, `.env`, debug logs, generated docs output, virtual environments, or build artifacts.
- Run `just lint`, `just test`, `uv run --only-group docs zensical build --clean --strict`, and `uv build` before requesting review.

## Model Metadata

Model definitions live in `src/perplexity_webui_scraper/_static/models.json`.

Keep the catalog ordered for people reading it: default entry points first (`perplexity/best` and `perplexity/deep-research`), then the remaining official WebUI models in their current UI order, followed by historical identifiers from newest to oldest. Do not sort by status or test date; both are operational metadata and change over time.

When adding or correcting a model, use Perplexity's internal model config endpoint when available:

```text
https://www.perplexity.ai/rest/models/config/v2
```

The WebUI network panel can also be used as a fallback to confirm `model_preference`, mode, provider, and tier behavior. Always redact cookies, session tokens, request headers, account IDs, and private prompt data before sharing evidence in an issue or pull request.

- The picker is only a subset of the backend registry: absence from the picker does not prove that a model identifier has stopped working. Never delete an existing `models.json` entry. Set `is_official` to `true` only when the model is listed by the official WebUI. Use exactly one operational `status`: `available` for models confirmed to work normally, `unknown` for unverified models (the default for new or custom identifiers), and `unavailable` only after backend failure is confirmed. Official listing does not imply that a model has been tested, and account-tier denial alone does not make a model unavailable. Historical identifiers remain in the catalog to preserve their public model IDs and MCP tool names.

Set `last_tested_at` to the UTC timestamp of the live test that supports the current `status`. Leave it as `null` when no conclusive live test has been performed; presence in `/rest/models/config/v2` alone is not a successful model test.

Tests and generated documentation must derive model IDs, counts, statuses, and timestamps from the loaded registry. Do not hardcode a snapshot of `models.json`; use small synthetic registry fixtures for status behavior and reserve literal model IDs for explicit public-compatibility tests only.

Model changes should update:

- `src/perplexity_webui_scraper/_static/models.json`
- generated README or documentation model tables (`just model-docs`)
- tests that validate the model registry, when applicable
- `CHANGELOG.md` if the change is user-facing

## Code Style

- Follow the existing `src/` package structure.
- Prefer Pydantic models for structured data.
- Keep public APIs typed and documented.
- Keep internal Perplexity endpoint behavior isolated in focused modules.
- Avoid broad refactors unless they are required for the change.
- Use blank lines to show logical processing phases inside functions: separate resource setup/acquisition, before loops or conditionals, and before the final return where it closes a phase. Keep related assignments and literals together; do not insert a blank line after every statement.
- For compound blocks, separate distinct operations when it improves scanability, but keep tightly coupled operations together and preserve comments with the code they explain.
- Run Ruff for mechanical formatting and import ordering. Apply this logical spacing manually; do not add a project-specific formatter to rewrite every Python file.
- When formatting an existing file, inspect its full diff and keep behavior and unrelated edits unchanged. Apply this style to new Python files from the first edit.

## Commit Style

Use short, conventional commit messages:

```text
fix: handle free account attachment limits
feat: add account profile models
docs: update cli usage examples
ci: simplify release publishing
```

## Security

Do not report security-sensitive details in public issues. See `SECURITY.md` for the supported reporting process.
