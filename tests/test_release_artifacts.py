"""Tests for safely resuming release artifact uploads."""

from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tarfile import TarInfo
from tarfile import open as open_tar
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from zipfile import ZipFile

from pytest import raises

from scripts.check_pypi_artifacts import fetch_published_files, missing_artifact_paths
from scripts.validate_release_artifacts import validate_artifacts


def test_missing_artifact_paths_returns_all_unpublished_files(tmp_path: Path) -> None:
    wheel = tmp_path / "package-1.2.0-py3-none-any.whl"
    sdist = tmp_path / "package-1.2.0.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")

    assert missing_artifact_paths([wheel, sdist], {}) == [wheel, sdist]


def test_missing_artifact_paths_skips_matching_published_files(tmp_path: Path) -> None:
    wheel = tmp_path / "package-1.2.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    published = {wheel.name: sha256(b"wheel").hexdigest()}

    assert missing_artifact_paths([wheel], published) == []


def test_missing_artifact_paths_returns_only_files_not_yet_published(tmp_path: Path) -> None:
    wheel = tmp_path / "package-1.2.0-py3-none-any.whl"
    sdist = tmp_path / "package-1.2.0.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")
    published = {wheel.name: sha256(b"wheel").hexdigest()}

    assert missing_artifact_paths([wheel, sdist], published) == [sdist]


def test_missing_artifact_paths_rejects_published_files_with_different_hash(tmp_path: Path) -> None:
    wheel = tmp_path / "package-1.2.0-py3-none-any.whl"
    wheel.write_bytes(b"current build")
    published = {wheel.name: sha256(b"prior build").hexdigest()}

    with raises(ValueError, match="different SHA-256 digest"):
        missing_artifact_paths([wheel], published)


def test_missing_artifact_paths_rejects_partial_same_version_with_different_files(tmp_path: Path) -> None:
    existing_wheel = tmp_path / "package-1.2.0-py3-none-any.whl"
    missing_sdist = tmp_path / "package-1.2.0.tar.gz"
    existing_wheel.write_bytes(b"new build wheel")
    missing_sdist.write_bytes(b"new build sdist")
    published = {existing_wheel.name: sha256(b"old build wheel").hexdigest()}

    with raises(ValueError, match="different SHA-256 digest"):
        missing_artifact_paths([existing_wheel, missing_sdist], published)


def test_fetch_published_files_returns_empty_for_missing_version() -> None:
    error = HTTPError("https://pypi.org/pypi/example/1.2.1/json", 404, "missing", MagicMock(), None)

    with patch("scripts.check_pypi_artifacts.urlopen", side_effect=error):
        assert fetch_published_files("example", "1.2.1") == {}


def _write_wheel(path: Path, version: str) -> None:
    metadata = f"Metadata-Version: 2.4\nName: package\nVersion: {version}\n"
    with ZipFile(path, "w") as wheel:
        wheel.writestr("package-1.2.1.dist-info/METADATA", metadata)


def _write_sdist(path: Path, version: str) -> None:
    metadata = f"Metadata-Version: 2.4\nName: package\nVersion: {version}\n".encode()
    member = TarInfo(f"package-{version}/PKG-INFO")
    member.size = len(metadata)
    with open_tar(path, "w:gz") as archive:
        archive.addfile(member, BytesIO(metadata))


def test_validate_artifacts_accepts_matching_wheel_and_sdist_versions(tmp_path: Path) -> None:
    wheel = tmp_path / "package-1.2.1-py3-none-any.whl"
    sdist = tmp_path / "package-1.2.1.tar.gz"
    _write_wheel(wheel, "1.2.1")
    _write_sdist(sdist, "1.2.1")

    validate_artifacts([wheel, sdist], "1.2.1")


def test_validate_artifacts_rejects_mismatched_wheel_version(tmp_path: Path) -> None:
    wheel = tmp_path / "package-1.2.1-py3-none-any.whl"
    sdist = tmp_path / "package-1.2.1.tar.gz"
    _write_wheel(wheel, "1.2.0")
    _write_sdist(sdist, "1.2.1")

    with raises(ValueError, match="Artifact versions must match"):
        validate_artifacts([wheel, sdist], "1.2.1")


def test_validate_artifacts_rejects_missing_distribution(tmp_path: Path) -> None:
    wheel = tmp_path / "package-1.2.1-py3-none-any.whl"
    _write_wheel(wheel, "1.2.1")

    with raises(ValueError, match="exactly one wheel and one sdist"):
        validate_artifacts([wheel], "1.2.1")
