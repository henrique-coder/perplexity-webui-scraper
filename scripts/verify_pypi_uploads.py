"""Check PyPI release files to resume interrupted artifact uploads."""

from __future__ import annotations

from hashlib import sha256
from json import load
from os import environ
from pathlib import Path
from sys import argv
from time import sleep
from typing import TYPE_CHECKING
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


if TYPE_CHECKING:
    from collections.abc import Callable


_TRANSIENT_HTTP_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})


def _is_transient_error(error: BaseException) -> bool:
    """Return whether an HTTP or URL error is transient and safe to retry."""
    if isinstance(error, HTTPError):
        return error.code in _TRANSIENT_HTTP_STATUS_CODES

    return isinstance(error, URLError)


def missing_artifact_paths(artifacts: list[Path], published_files: dict[str, str]) -> list[Path]:
    """Return unpublished files, rejecting same-name files with mismatched hashes."""
    missing_files: list[Path] = []

    for artifact in artifacts:
        digest = sha256()

        with artifact.open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(block)

        hash_bytes = digest.hexdigest()
        published_hash = published_files.get(artifact.name)

        if published_hash is None:
            missing_files.append(artifact)
        elif published_hash != hash_bytes:
            raise ValueError(f"PyPI already has {artifact.name} with a different SHA-256 digest.")

    return missing_files


def fetch_published_files(package_name: str, version: str) -> dict[str, str]:
    """Fetch filenames and SHA-256 hashes from the PyPI release JSON API."""
    url = f"https://pypi.org/pypi/{package_name}/{version}/json"
    request = Request(url, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"}, method="GET")

    try:
        with urlopen(request, timeout=20) as response:  # nosec B310
            return {item["filename"]: item["digests"]["sha256"] for item in load(response)["urls"]}
    except HTTPError as error:
        if error.code == 404:
            return {}

        raise


def verify_with_retries(
    artifacts: list[Path],
    package_name: str,
    version: str,
    *,
    max_attempts: int = 18,
    delay_seconds: float = 5.0,
    sleep_fn: Callable[[float], None] | None = None,
) -> list[Path]:
    """Poll PyPI release metadata until all artifacts appear or attempts exhaust."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1.")

    pause = sleep if sleep_fn is None else sleep_fn

    for attempt in range(1, max_attempts + 1):
        try:
            published_files = fetch_published_files(package_name, version)
            missing_files = missing_artifact_paths(artifacts, published_files)
        except (HTTPError, URLError) as error:
            if not _is_transient_error(error) or attempt == max_attempts:
                raise
        else:
            if not missing_files or attempt == max_attempts:
                return missing_files

        pause(delay_seconds)

    return []


def main(arguments: list[str] | None = None) -> int:
    """Check PyPI state and report whether any release artifact needs uploading."""
    package_name = environ["PACKAGE_NAME"]
    version = environ["VERSION"]
    artifacts = sorted((*Path("dist").glob("*.whl"), *Path("dist").glob("*.tar.gz")))

    if not artifacts:
        raise ValueError("No wheel or source distribution found in dist/.")

    verify_only = "--verify-only" in (argv[1:] if arguments is None else arguments)

    if verify_only:
        missing_files = verify_with_retries(artifacts, package_name, version)

        if missing_files:
            raise ValueError(f"PyPI publication incomplete; missing: {', '.join(path.name for path in missing_files)}")

        return 0

    published_files = fetch_published_files(package_name, version)
    missing_files = missing_artifact_paths(artifacts, published_files)
    publish = bool(missing_files)

    with Path(environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"publish={str(publish).lower()}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
