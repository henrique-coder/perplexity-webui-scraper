"""Render checked-in model catalog tables from the JSON source of truth."""

from __future__ import annotations

from argparse import ArgumentParser
from collections import Counter
from pathlib import Path
from re import DOTALL, sub
from sys import stderr, stdout

from orjson import loads

from perplexity_webui_scraper.models.types import MODEL_STATUS_DESCRIPTIONS, Model, ModelStatus


ROOT = Path(__file__).resolve().parents[1]
MODELS_FILE = ROOT / "src/perplexity_webui_scraper/_static/models.json"
BEGIN = "<!-- BEGIN GENERATED MODEL CATALOG -->"
END = "<!-- END GENERATED MODEL CATALOG -->"
STATUS_ORDER: tuple[ModelStatus, ...] = ("available", "unknown", "unavailable")
STATUS_BEHAVIOR: dict[ModelStatus, str] = {
    "available": "Normal use; the local minimum-tier check applies.",
    "unknown": "Requires `allow_risky_model`; this is the default for unverified entries.",
    "unavailable": "Requires `allow_risky_model`; retained for history and expected to fail.",
}


def _models(catalog_path: Path = MODELS_FILE) -> list[Model]:
    """Load and validate catalog models directly from the static JSON file."""
    raw = catalog_path.read_bytes()

    return [Model.model_validate(item) for item in loads(raw)]


def _status_reference() -> list[str]:
    lines = [
        "### Model status reference",
        "",
        "| Status | Meaning | Runtime behavior |",
        "| --- | --- | --- |",
    ]
    lines.extend(
        f"| `{status}` | {MODEL_STATUS_DESCRIPTIONS[status]} | {STATUS_BEHAVIOR[status]} |" for status in STATUS_ORDER
    )

    return [*lines, ""]


def _tier(model: Model) -> str:
    return model.min_tier


def _last_tested(model: Model) -> str:
    return model.last_tested_at.isoformat().replace("+00:00", "Z") if model.last_tested_at else "—"


def _api_catalog(models: list[Model]) -> str:
    lines: list[str] = [BEGIN, *_status_reference(), "### Model catalog", ""]
    lines.extend(
        (
            "| Model ID | Internal identifier | Provider | Official | Min. tier | Status | Last tested (UTC) |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        )
    )
    lines.extend(
        "| "
        f"`{model.id}` | `{model.identifier}` | {model.provider} | "
        f"`{str(model.is_official).lower()}` | {_tier(model)} | "
        f"`{model.status}` | {_last_tested(model)} |"
        for model in models
    )
    lines.append("")
    lines.append(END)

    return "\n".join(lines)


def _mcp_catalog(models: list[Model]) -> str:
    lines: list[str] = [BEGIN, *_status_reference(), "### Model tools", ""]
    lines.extend(
        (
            "| Tool | Model ID | Name | Official | Min. tier | Status | Last tested (UTC) |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        )
    )
    lines.extend(
        "| "
        f"`{model.tool_name}` | `{model.id}` | {model.name} | `{str(model.is_official).lower()}` | {_tier(model)} | "
        f"`{model.status}` | {_last_tested(model)} |"
        for model in models
    )
    lines.append("")
    lines.extend(
        (
            "### Custom tool",
            "",
            (
                "`pplx_custom` accepts an arbitrary `custom:<identifier>` model and requires "
                "explicit risky-model acknowledgement."
            ),
            "",
            END,
        )
    )

    return "\n".join(lines)


def _replace(path: Path, rendered: str) -> tuple[str, str]:
    """Replace the generated catalog region delimited by BEGIN and END markers."""
    original = path.read_text(encoding="utf-8")

    if BEGIN not in original or END not in original:
        raise RuntimeError(f"Could not locate generated model catalog markers in {path}")

    updated = sub(f"{BEGIN}.*?{END}\n*", f"{rendered}\n\n", original, flags=DOTALL).rstrip("\n") + "\n"

    return original, updated


def render_catalog_docs(*, check: bool = False) -> int:
    """Render or verify model catalog sections across documentation pages."""
    models = _models()
    targets = (
        (ROOT / "docs/python-client/models.md", _api_catalog(models)),
        (ROOT / "docs/mcp-server.md", _mcp_catalog(models)),
    )
    stale: list[Path] = []
    updated_paths: list[Path] = []

    for path, rendered in targets:
        original, updated = _replace(path, rendered)

        if original == updated:
            continue

        if check:
            stale.append(path)
        else:
            path.write_text(updated, encoding="utf-8")
            updated_paths.append(path)

    if stale:
        stderr.write("Stale generated model catalogs:\n")

        for path in stale:
            stderr.write(f"  {path.relative_to(ROOT)}\n")

        return 1

    counts = Counter(model.status for model in models)
    action = "Verified" if check else "Generated" if updated_paths else "Already up to date"
    stdout.write(
        f"{action} model docs: {len(models)} models "
        f"({', '.join(f'{counts[status]} {status}' for status in STATUS_ORDER)}).\n"
    )

    if updated_paths:
        for path in updated_paths:
            stdout.write(f"  updated {path.relative_to(ROOT)}\n")

    return 0


def main(arguments: list[str] | None = None) -> int:
    """Parse CLI arguments and render or verify the generated model tables."""
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if checked-in catalogs are stale")
    args = parser.parse_args(arguments)

    return render_catalog_docs(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
