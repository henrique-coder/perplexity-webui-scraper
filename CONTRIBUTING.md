# Contributing

Thank you for considering a contribution to `perplexity-webui-scraper`.

This project wraps private Perplexity WebUI endpoints. Changes should be conservative, well-tested, and documented because upstream behavior can change without notice.

## Before Opening an Issue

- Search existing issues first.
- Make sure you are using the latest released version.
- Check the documentation at <https://henrique-coder.github.io/perplexity-webui-scraper>.
- Do not include session tokens, cookies, account IDs, private prompts, or private files in public issues.

## Development Setup

Requirements:

- Python 3.11, 3.12, 3.13, or 3.14
- `uv`
- `pnpm`
- `just`

Install all development dependencies:

```bash
uv sync --all-extras --all-groups
pnpm install
```

Useful commands:

| Command                                     | Purpose                                                                                                                 |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `just format`                               | Format Python, Markdown, YAML, TOML, and related project files.                                                         |
| `just lint`                                 | Run Ruff, ty, Prettier, and Taplo checks.                                                                               |
| `just test`                                 | Run the pytest suite.                                                                                                   |
| `uv run --group docs mkdocs build --strict` | Build the documentation site with MkDocs using the `docs` dependency group. `--strict` fails on documentation warnings. |
| `uv build`                                  | Build the Python source distribution and wheel.                                                                         |

`mkdocs` is the documentation generator used by this project. The command above does not publish anything; it only verifies that the local documentation can be built successfully.

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
4. The workflow publishes the Python package, API and MCP images, and documentation before creating the immutable tag and GitHub Release. It can safely resume after an interrupted PyPI publication.

- Keep changes focused on one concern.
- Add or update tests for behavior changes.
- Update README, MkDocs pages, and `CHANGELOG.md` when user-facing behavior changes.
- Keep model metadata in `src/perplexity_webui_scraper/_static/models.json`.
- Do not commit local secrets, `.env`, debug logs, generated docs output, virtual environments, or build artifacts.
- Run `just lint`, `just test`, `uv run --group docs mkdocs build --strict`, and `uv build` before requesting review.

## Model Metadata

Model definitions live in `src/perplexity_webui_scraper/_static/models.json`.

When adding or correcting a model, use Perplexity's internal model config endpoint when available:

```text
https://www.perplexity.ai/rest/models/config
```

The WebUI network panel can also be used as a fallback to confirm `model_preference`, mode, provider, and tier behavior. Always redact cookies, session tokens, request headers, account IDs, and private prompt data before sharing evidence in an issue or pull request.

The picker is only a subset of the backend registry: absence from the picker does not prove that a model identifier has stopped working. Never delete an existing `models.json` entry. Retain unverified entries as unstable, and mark an entry disabled only after its failure has been confirmed; disabled entries remain documented for compatibility and historical reference.

Model changes should update:

- `src/perplexity_webui_scraper/_static/models.json`
- generated README or MkDocs model tables (`just model-docs`)
- tests that validate the model registry, when applicable
- `CHANGELOG.md` if the change is user-facing

## Code Style

- Follow the existing `src/` package structure.
- Prefer Pydantic models for structured data.
- Keep public APIs typed and documented.
- Keep internal Perplexity endpoint behavior isolated in focused modules.
- Avoid broad refactors unless they are required for the change.

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
