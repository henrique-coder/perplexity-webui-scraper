# Maintainer scripts

Development and release helper scripts. Install the `scripts` dependency group before running catalog synchronization or availability probes:

```bash
uv sync --no-dev --group scripts
```

## Catalog and documentation scripts

| Script                        | Purpose                                                                         |
| ----------------------------- | ------------------------------------------------------------------------------- |
| `sync_model_catalog.py`       | Synchronize `models.json` from `/rest/models/config/v2` and DrissionPage WebUI. |
| `generate_model_docs.py`      | Regenerate or verify generated model catalog tables in `docs/`.                 |
| `probe_model_availability.py` | Run short live availability pings and write `reports/model-smoke-results.json`. |

```bash
uv run --no-sync python scripts/sync_model_catalog.py
uv run --no-sync python scripts/sync_model_catalog.py --check
uv run --no-sync python scripts/generate_model_docs.py
uv run --no-sync python scripts/generate_model_docs.py --check
uv run --no-sync python scripts/probe_model_availability.py --workers 4
```

`sync_model_catalog.py` and `probe_model_availability.py` read `PERPLEXITY_SESSION_TOKEN` from `.env` or the environment without printing or saving credentials. `sync_model_catalog.py` drives an already installed Chrome, Chromium, Edge, or Brave binary through DrissionPage without downloading browser runtimes.

## CI and release scripts (stdlib-only)

| Script                        | Purpose                                                                 |
| ----------------------------- | ----------------------------------------------------------------------- |
| `classify_ci_paths.py`        | Map changed Git paths to the CI jobs that need to run.                  |
| `rewrite_pypi_readme.py`      | Pin the README logo URL to an immutable commit SHA before `uv build`.   |
| `verify_pypi_uploads.py`      | Check published PyPI files and SHA-256 digests before or after upload.  |
| `verify_release_artifacts.py` | Validate wheel and sdist version metadata and distinct SHA-256 digests. |
| `verify_release_policy.py`    | Verify `pyproject.toml`, `uv.lock`, and dated `CHANGELOG.md` match.     |
