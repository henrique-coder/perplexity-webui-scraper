"""Classify changed files so CI runs only the checks affected by a change."""

from __future__ import annotations

from argparse import ArgumentParser
from os import environ
from pathlib import Path, PurePosixPath
from subprocess import check_output
from sys import stdout
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Iterable


CHECKS = ("python", "documentation", "frontend", "workflows", "metadata")
PYTHON_PATHS = ("src/", "tests/", "pyproject.toml", "uv.lock", "Justfile", "scripts/")
DOCUMENTATION_PATHS = ("docs/", "README.md", "mkdocs.yml")
FRONTEND_PATHS = ("package.json", "pnpm-lock.yaml", ".prettier", ".taplo")
WORKFLOW_PATHS = (".github/workflows/", ".github/actions/")


def _matches(path: str, prefixes: tuple[str, ...]) -> bool:
    """Return whether *path* is covered by a path prefix or exact filename."""
    return any(path == prefix or path.startswith(prefix) for prefix in prefixes)


def classify_paths(paths: Iterable[str]) -> dict[str, bool]:
    """Return the independent CI check categories affected by *paths*."""
    changed = {PurePosixPath(path).as_posix() for path in paths if path}
    result = {
        "python": any(_matches(path, PYTHON_PATHS) for path in changed),
        "documentation": any(_matches(path, DOCUMENTATION_PATHS) for path in changed),
        "frontend": any(_matches(path, FRONTEND_PATHS) for path in changed),
        "workflows": any(_matches(path, WORKFLOW_PATHS) for path in changed),
    }
    result["metadata"] = bool(changed) and not any(result.values())
    return result


def _changed_paths(base: str, head: str, *, cwd: Path | None = None) -> list[str]:
    """Read added, copied, modified, renamed, and deleted paths from the Git diff."""
    output = check_output(
        ["git", "diff", "--name-only", "--diff-filter=ACMRD", base, head],
        cwd=cwd,
        text=True,
    )
    return output.splitlines()


def _write_outputs(result: dict[str, bool]) -> None:
    """Write GitHub Actions outputs, or print them when run locally."""
    lines = [f"{name}={str(enabled).lower()}" for name, enabled in result.items()]
    output_path = environ.get("GITHUB_OUTPUT")
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as output_file:
            output_file.write("\n".join(lines) + "\n")
        return
    stdout.write("\n".join(lines) + "\n")


def main() -> int:
    """Parse the diff range and emit the CI categories that should run."""
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("base", nargs="?", help="Base Git revision")
    parser.add_argument("head", nargs="?", help="Head Git revision")
    parser.add_argument("--all", action="store_true", help="Run every category without reading a Git diff")
    args = parser.parse_args()

    if args.all:
        _write_outputs(dict.fromkeys(CHECKS, True))
        return 0

    if not args.base or not args.head:
        parser.error("base and head are required unless --all is used")
    _write_outputs(classify_paths(_changed_paths(args.base, args.head)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
