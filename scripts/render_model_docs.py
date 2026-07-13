"""Render checked-in model catalog tables from the JSON source of truth."""

from __future__ import annotations

from argparse import ArgumentParser
from importlib.resources import files
from pathlib import Path
from re import DOTALL, MULTILINE, sub
from sys import stderr, stdout

from orjson import loads

from perplexity_webui_scraper.models.types import Model


ROOT = Path(__file__).resolve().parents[1]
BEGIN = "<!-- BEGIN GENERATED MODEL CATALOG -->"
END = "<!-- END GENERATED MODEL CATALOG -->"


def _models() -> list[Model]:
    raw = files("perplexity_webui_scraper._static").joinpath("models.json").read_bytes()  # type: ignore[arg-type]
    return [Model.model_validate(item) for item in loads(raw)]


def _groups(models: list[Model]) -> list[tuple[str, list[Model]]]:
    return [
        ("Stable", [model for model in models if not model.unstable]),
        ("Unstable", [model for model in models if model.unstable and not model.disabled]),
        ("Disabled", [model for model in models if model.disabled]),
    ]


def _tier(model: Model) -> str:
    return model.min_tier or "unknown"


def _api_catalog(models: list[Model]) -> str:
    lines: list[str] = [BEGIN]
    for heading, entries in _groups(models):
        lines.extend((f"### {heading}", ""))
        if not entries:
            lines.extend(("_No models in this category._", ""))
            continue
        lines.extend(
            (
                "| Model ID | Internal identifier | Provider | Min. tier | Warning |",
                "| --- | --- | --- | --- | --- |",
            )
        )
        for model in entries:
            warning = model.warning or "—"
            lines.append(f"| `{model.id}` | `{model.identifier}` | {model.provider} | {_tier(model)} | {warning} |")
        lines.append("")
    lines.append(END)
    return "\n".join(lines)


def _mcp_catalog(models: list[Model]) -> str:
    lines: list[str] = [BEGIN]
    for heading, entries in _groups(models):
        lines.extend((f"### {heading} tools", ""))
        if not entries:
            lines.extend(("_No tools in this category._", ""))
            continue
        lines.extend(
            (
                "| Tool | Model ID | Name | Min. tier | Warning |",
                "| --- | --- | --- | --- | --- |",
            )
        )
        for model in entries:
            warning = model.warning or "—"
            lines.append(f"| `{model.tool_name}` | `{model.id}` | {model.name} | {_tier(model)} | {warning} |")
        lines.append("")
    lines.extend(
        (
            "### Custom tool",
            "",
            (
                "`pplx_custom` accepts an arbitrary `custom:<identifier>` model and requires "
                "explicit unstable-model acknowledgement."
            ),
            "",
            END,
        )
    )
    return "\n".join(lines)


def _replace(path: Path, rendered: str, fallback_pattern: str) -> tuple[str, str]:
    original = path.read_text(encoding="utf-8")
    if BEGIN in original and END in original:
        updated = sub(f"{BEGIN}.*?{END}\n*", f"{rendered}\n\n", original, flags=DOTALL)
    else:
        updated = sub(fallback_pattern, rendered, original, count=1, flags=DOTALL | MULTILINE)
    if updated == original and rendered not in original:
        raise RuntimeError(f"Could not locate generated model catalog in {path}")
    return original, updated


def main() -> int:
    parser = ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if checked-in catalogs are stale")
    args = parser.parse_args()
    models = _models()
    targets = [
        (
            ROOT / "docs/api-reference.md",
            _api_catalog(models),
            r"^\| Model ID.*?\n\n(?=Inspect models programmatically:)",
        ),
        (
            ROOT / "docs/mcp-server.md",
            _mcp_catalog(models),
            r"^\| Tool.*?\n\n(?=\*\*All tools support)",
        ),
    ]
    stale: list[Path] = []
    updated_paths: list[Path] = []
    for path, rendered, fallback in targets:
        original, updated = _replace(path, rendered, fallback)
        if original == updated:
            continue
        if args.check:
            stale.append(path)
        else:
            path.write_text(updated, encoding="utf-8")
            updated_paths.append(path)
    if stale:
        stderr.write("Stale generated model catalogs:\n")
        for path in stale:
            stderr.write(f"  {path.relative_to(ROOT)}\n")
        return 1
    stable = sum(not model.unstable for model in models)
    unstable = sum(model.unstable and not model.disabled for model in models)
    disabled = sum(model.disabled for model in models)
    action = "Verified" if args.check else "Generated" if updated_paths else "Already up to date"
    stdout.write(
        f"{action} model docs: {len(models)} models ({stable} stable, {unstable} unstable, {disabled} disabled).\n"
    )
    if updated_paths:
        for path in updated_paths:
            stdout.write(f"  updated {path.relative_to(ROOT)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
