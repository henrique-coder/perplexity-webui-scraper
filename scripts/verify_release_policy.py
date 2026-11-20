"""Validate release version synchronization and dated changelog headers."""

from __future__ import annotations

from argparse import ArgumentParser
from datetime import date
from pathlib import Path
from re import IGNORECASE, MULTILINE, fullmatch, search
from sys import stderr, stdout
from tomllib import load


_HEADING_PATTERN = r"^## \[([^\]]+)\](.*)$"
_DATED_HEADING_PATTERN = r"^## \[(?P<version>\d+\.\d+\.\d+)\] - (?P<date>\d{4}-\d{2}-\d{2})$"


def validate_release_policy(root: Path, expected_version: str | None = None) -> str:
    """Verify project, lockfile, and top dated changelog section share one version."""
    with (root / "pyproject.toml").open("rb") as pyproject_file:
        project_metadata = load(pyproject_file).get("project", {})

    project_name = project_metadata.get("name", "perplexity-webui-scraper")
    project_version = project_metadata.get("version")

    with (root / "uv.lock").open("rb") as lock_file:
        lock_data = load(lock_file)

    lock_version = next(
        (package["version"] for package in lock_data.get("package", []) if package.get("name") == project_name),
        None,
    )

    if not isinstance(project_version, str) or not project_version:
        raise ValueError("pyproject.toml does not define a valid project version.")

    if lock_version != project_version:
        raise ValueError(f"uv.lock version {lock_version!r} does not match pyproject.toml {project_version!r}.")

    if expected_version is not None and project_version != expected_version:
        raise ValueError(f"Requested version {expected_version!r} does not match pyproject.toml {project_version!r}.")

    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    heading_match = search(_HEADING_PATTERN, changelog, MULTILINE)

    if heading_match is None:
        raise ValueError("CHANGELOG.md does not contain a release section heading.")

    heading_line = heading_match.group(0).strip()

    if search(r"\bunreleased\b", heading_line, IGNORECASE):
        raise ValueError(
            f"CHANGELOG.md still has an Unreleased heading ({heading_line}); "
            "replace Unreleased with the UTC release date (YYYY-MM-DD) before promotion."
        )

    dated_match = fullmatch(_DATED_HEADING_PATTERN, heading_line)

    if dated_match is None:
        raise ValueError(f"Top CHANGELOG.md heading must use '## [X.Y.Z] - YYYY-MM-DD' format; found {heading_line!r}.")

    release_date = dated_match.group("date")

    try:
        date.fromisoformat(release_date)
    except ValueError as error:
        raise ValueError(f"Top CHANGELOG.md heading contains an invalid release date: {release_date!r}.") from error

    changelog_version = dated_match.group("version")

    if changelog_version != project_version:
        raise ValueError(
            f"CHANGELOG.md top version {changelog_version!r} does not match pyproject.toml {project_version!r}."
        )

    return project_version


def main() -> int:
    """Validate release policy requirements from the command line."""
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(), help="Repository root directory.")
    parser.add_argument("--expected-version", default=None, help="Optional expected release version.")
    arguments = parser.parse_args()

    try:
        version = validate_release_policy(arguments.root, expected_version=arguments.expected_version)
    except ValueError as error:
        stderr.write(f"Release policy validation failed: {error}\n")

        return 1

    stdout.write(f"Validated release policy for {version}.\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
