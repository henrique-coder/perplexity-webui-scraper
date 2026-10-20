"""Check PyPI release files to resume interrupted artifact uploads."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen


def missing_artifact_paths(artifacts: list[Path], published_files: dict[str, str]) -> list[Path]:
    """Return unpublished files, rejecting same-name files with mismatched hashes."""
    missing_files = []
    for artifact in artifacts:
        hash_bytes = hashlib.sha256(artifact.read_bytes()).hexdigest()
        published_hash = published_files.get(artifact.name)
        if published_hash is None:
            missing_files.append(artifact)
        elif published_hash != hash_bytes:
            raise ValueError(f"PyPI already has {artifact.name} with a different SHA-256 digest.")
    return missing_files


def fetch_published_files(package_name: str, version: str) -> dict[str, str]:
    """Fetch filenames and SHA-256 hashes from the PyPI release JSON API."""
    url = f"https://pypi.org/pypi/{package_name}/{version}/json"
    try:
        with urlopen(url, timeout=20) as response:
            return {item["filename"]: item["digests"]["sha256"] for item in json.load(response)["urls"]}
    except HTTPError as error:
        if error.code == 404:
            return {}
        raise


def main() -> None:
    """Check downloaded artifacts and expose whether uv publish should run."""
    package_name = os.environ["PACKAGE_NAME"]
    version = os.environ["VERSION"]
    artifacts = sorted((*Path("dist").glob("*.whl"), *Path("dist").glob("*.tar.gz")))
    if not artifacts:
        raise SystemExit("No wheel or source distribution found in dist/.")

    missing_files = missing_artifact_paths(artifacts, fetch_published_files(package_name, version))
    publish = bool(missing_files)
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"publish={str(publish).lower()}\n")


if __name__ == "__main__":
    main()
