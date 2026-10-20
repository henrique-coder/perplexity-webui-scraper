"""Verify the exact package files produced for a release."""

from __future__ import annotations

from argparse import ArgumentParser
from hashlib import sha256
from pathlib import Path
from sys import stderr, stdout
from tarfile import TarError
from tarfile import open as open_tar
from zipfile import BadZipFile, ZipFile


def validate_artifacts(artifact_paths: list[Path], expected_version: str) -> None:
    """Reject missing, malformed, mismatched, or duplicate package artifacts."""
    if len(artifact_paths) != 2:
        raise ValueError(f"Expected exactly one wheel and one sdist; found {len(artifact_paths)} artifacts.")

    wheels = [path for path in artifact_paths if path.name.endswith(".whl")]
    sdists = [path for path in artifact_paths if path.name.endswith(".tar.gz")]
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError("Expected exactly one .whl and one .tar.gz release artifact.")

    wheel_version = _wheel_version(wheels[0])
    sdist_version = _sdist_version(sdists[0])
    if wheel_version != expected_version or sdist_version != expected_version:
        raise ValueError(
            f"Artifact versions must match {expected_version}; wheel={wheel_version}, sdist={sdist_version}."
        )
    if wheel_version != sdist_version:
        raise ValueError(f"Wheel and sdist versions differ: wheel={wheel_version}, sdist={sdist_version}.")

    wheel_digest = _sha256(wheels[0])
    sdist_digest = _sha256(sdists[0])
    if wheel_digest == sdist_digest:
        raise ValueError("Wheel and sdist unexpectedly have identical SHA-256 digests.")


def _wheel_version(path: Path) -> str:
    """Read and validate the wheel's package metadata version."""
    try:
        with ZipFile(path) as wheel:
            metadata_files = [name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")]
            if len(metadata_files) != 1:
                raise ValueError(f"Expected one wheel METADATA file in {path.name}.")
            metadata = wheel.read(metadata_files[0]).decode("utf-8")
    except (BadZipFile, UnicodeDecodeError) as error:
        raise ValueError(f"Invalid wheel archive: {path.name}.") from error
    return _metadata_version(metadata, path.name)


def _sdist_version(path: Path) -> str:
    """Read and validate the sdist's package metadata version."""
    try:
        with open_tar(path, "r:gz") as archive:
            metadata_files = [name for name in archive.getnames() if name.endswith("/PKG-INFO")]
            if len(metadata_files) != 1:
                raise ValueError(f"Expected one PKG-INFO file in {path.name}.")
            member = archive.extractfile(metadata_files[0])
            if member is None:
                raise ValueError(f"Cannot read PKG-INFO in {path.name}.")
            metadata = member.read().decode("utf-8")
    except (TarError, UnicodeDecodeError) as error:
        raise ValueError(f"Invalid source archive: {path.name}.") from error
    return _metadata_version(metadata, path.name)


def _metadata_version(metadata: str, artifact_name: str) -> str:
    """Extract the unique Version field from core package metadata."""
    versions = [line.partition(":")[2].strip() for line in metadata.splitlines() if line.lower().startswith("version:")]
    if len(versions) != 1:
        raise ValueError(f"Expected one Version field in {artifact_name} metadata.")
    if not versions[0]:
        raise ValueError(f"Invalid Version field in {artifact_name} metadata.")
    return versions[0]


def _sha256(path: Path) -> str:
    """Calculate a file's SHA-256 digest using bounded memory."""
    digest = sha256()
    with path.open("rb") as artifact:
        for block in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    """Validate command-line release artifacts against their expected version."""
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Expected package version.")
    parser.add_argument("artifacts", nargs="+", type=Path, help="Wheel and source archive paths.")
    arguments = parser.parse_args()
    try:
        validate_artifacts(arguments.artifacts, arguments.version)
    except ValueError as error:
        stderr.write(f"Release artifact validation failed: {error}\n")
        return 1
    stdout.write(f"Validated {len(arguments.artifacts)} release artifacts for {arguments.version}.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
