# Project instructions

## Changelog discipline

- Before editing `CHANGELOG.md`, inspect the existing `Unreleased` section and the next release section.
- Add only changes that are not already represented in the current `Unreleased` section or a prior release.
- If an item is already present and the implementation evolves, update or consolidate that entry instead of adding a duplicate.
- Keep work that spans multiple days in the same changelog entry; the entry describes the final state, not the date of each intermediate change.
- Do not rewrite dated release history unless correcting an explicit factual error. New work belongs in `Unreleased` and moves to the next release only during release preparation.

## Model metadata

- Use Perplexity's current model configuration endpoint exclusively: `https://www.perplexity.ai/rest/models/config/v2`.
- Do not use the retired `/rest/models/config` endpoint or copy its response as a substitute. If v2 is blocked, document the limitation and use redacted WebUI evidence without speculative catalog changes.
- Keep `models.json` ordered with `perplexity/best` and `perplexity/deep-research` first, followed by official WebUI models in UI order, then historical identifiers from newest to oldest.
- Derive model IDs, counts, statuses, and timestamps from the loaded registry. Do not hardcode catalog snapshots in tests or generated documentation.

## Python quality

- Format every Python file with `uv run ruff format`: double quotes, four-space indentation, LF endings, a 120-character limit, and Google-style docstrings.
- Run `uv run ruff check --fix` before `uv run ruff format`, then finish with `just lint` and `uv run ty check`.
- Treat ty errors as blockers; warning behavior remains governed by `pyproject.toml`.
- Keep a blank line between completed work and a following `return`, but not before the first statement of a block.
- Use synthetic fixtures for isolated behavior and reserve literal model IDs for explicit public-compatibility tests.
