"""Tests for safely resuming release artifact uploads."""

from hashlib import sha256
from pathlib import Path

from pytest import raises

from scripts.check_pypi_artifacts import missing_artifact_paths


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
