"""Render the release-specific README used in the PyPI package metadata."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


_LOGO_URL_PATTERN = re.compile(
    r"https://raw\.githubusercontent\.com/henrique-coder/perplexity-webui-scraper/[^/\s]+/docs/assets/icon\.png"
)
_LOGO_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/henrique-coder/perplexity-webui-scraper/{reference}/docs/assets/icon.png"
)
_REFERENCE_PATTERN = re.compile(r"[A-Za-z0-9._-]+")


def render_readme(source: str, reference: str) -> str:
    """Replace the README logo reference with an immutable source revision.

    Args:
        source: README contents containing the production logo URL.
        reference: Git commit SHA or other immutable GitHub revision.

    Returns:
        README contents with the logo URL pointing to ``reference``.

    Raises:
        ValueError: If the revision is unsafe for a URL path or the expected
            logo reference is not found exactly once.
    """
    if not _REFERENCE_PATTERN.fullmatch(reference):
        raise ValueError("README revision must contain only letters, digits, dots, underscores, or hyphens")

    rendered, replacements = _LOGO_URL_PATTERN.subn(_LOGO_URL_TEMPLATE.format(reference=reference), source)

    if replacements != 1:
        raise ValueError(f"Expected exactly one README logo URL, found {replacements}")

    return rendered


def main() -> None:
    """Render the README file in place for the package build."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, help="Immutable GitHub revision for the release README")
    parser.add_argument("--source", type=Path, default=Path("README.md"), help="README path to render")
    args = parser.parse_args()

    source = args.source.read_text(encoding="utf-8")
    args.source.write_text(render_readme(source, args.reference), encoding="utf-8")


if __name__ == "__main__":
    main()
