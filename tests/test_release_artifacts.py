from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tarfile import TarInfo
from tarfile import open as open_tar
from typing import Any
from unittest.mock import MagicMock
from urllib.error import HTTPError
from urllib.request import Request
from zipfile import ZipFile

from pytest import raises

from scripts.verify_pypi_uploads import fetch_published_files, missing_artifact_paths
from scripts.verify_pypi_uploads import main as check_pypi_artifacts
from scripts.verify_release_artifacts import validate_artifacts


PACKAGE_VERSION = "9.8.7"


def test_missing_artifact_paths_skips_identical_files_and_rejects_mismatch(tmp_path: Path) -> None:
    wheel = tmp_path / "package-py3-none-any.whl"
    sdist = tmp_path / "package.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")
    published = {wheel.name: sha256(b"wheel").hexdigest()}

    assert missing_artifact_paths([wheel, sdist], published) == [sdist]

    published[wheel.name] = sha256(b"different wheel").hexdigest()
    with raises(ValueError, match="different SHA-256 digest"):
        missing_artifact_paths([wheel, sdist], published)


def test_fetch_published_files_treats_missing_release_as_unpublished(monkeypatch: Any) -> None:
    error = HTTPError("release endpoint", 404, "missing", MagicMock(), None)
    request_arguments: list[tuple[str, str]] = []

    def urlopen(request: Request, **_kwargs: object) -> None:
        request_arguments.append((request.full_url, request.get_method()))
        raise error

    monkeypatch.setattr("scripts.verify_pypi_uploads.urlopen", urlopen)

    assert fetch_published_files("package", "0") == {}
    assert request_arguments == [("https://pypi.org/pypi/package/0/json", "GET")]


def test_check_pypi_artifacts_verify_only_requires_every_digest(tmp_path: Path, monkeypatch: Any) -> None:
    wheel, sdist = _write_artifacts(tmp_path, PACKAGE_VERSION, PACKAGE_VERSION)
    wheel_digest = sha256(wheel.read_bytes()).hexdigest()
    monkeypatch.chdir(tmp_path)
    (tmp_path / "dist").mkdir()
    wheel.rename(tmp_path / "dist" / wheel.name)
    sdist.rename(tmp_path / "dist" / sdist.name)
    monkeypatch.setenv("PACKAGE_NAME", "package")
    monkeypatch.setenv("VERSION", PACKAGE_VERSION)
    monkeypatch.setattr(
        "scripts.verify_pypi_uploads.fetch_published_files",
        lambda _package, _version: {(tmp_path / "dist" / wheel.name).name: wheel_digest},
    )

    with raises(ValueError, match="PyPI publication incomplete"):
        check_pypi_artifacts(["--verify-only"])


def _write_artifacts(directory: Path, wheel_version: str, sdist_version: str) -> list[Path]:
    wheel = directory / f"package-{wheel_version}-py3-none-any.whl"
    metadata = f"Metadata-Version: 2.4\nName: package\nVersion: {wheel_version}\n"
    with ZipFile(wheel, "w") as archive:
        archive.writestr(f"package-{wheel_version}.dist-info/METADATA", metadata)

    sdist = directory / f"package-{sdist_version}.tar.gz"
    metadata_bytes = f"Metadata-Version: 2.4\nName: package\nVersion: {sdist_version}\n".encode()
    member = TarInfo(f"package-{sdist_version}/PKG-INFO")
    member.size = len(metadata_bytes)
    with open_tar(sdist, "w:gz") as archive:
        archive.addfile(member, BytesIO(metadata_bytes))

    return [wheel, sdist]


def test_validate_artifacts_accepts_matching_metadata_and_rejects_mismatch(tmp_path: Path) -> None:
    artifacts = _write_artifacts(tmp_path, PACKAGE_VERSION, PACKAGE_VERSION)
    validate_artifacts(artifacts, PACKAGE_VERSION)

    mismatched_version = f"{PACKAGE_VERSION}.1"
    mismatched = _write_artifacts(tmp_path, PACKAGE_VERSION, mismatched_version)
    with raises(ValueError, match="Artifact versions must match"):
        validate_artifacts(mismatched, PACKAGE_VERSION)


def test_validate_artifacts_rejects_identical_artifact_digests(monkeypatch: Any, tmp_path: Path) -> None:
    artifacts = _write_artifacts(tmp_path, PACKAGE_VERSION, PACKAGE_VERSION)
    monkeypatch.setattr("scripts.verify_release_artifacts._sha256", lambda _path: "same-digest")

    with raises(ValueError, match="identical SHA-256 digests"):
        validate_artifacts(artifacts, PACKAGE_VERSION)


def test_validate_artifacts_requires_wheel_and_source_archive(tmp_path: Path) -> None:
    wheel, sdist = _write_artifacts(tmp_path, PACKAGE_VERSION, PACKAGE_VERSION)

    with raises(ValueError, match="exactly one wheel and one sdist"):
        validate_artifacts([wheel], PACKAGE_VERSION)

    with raises(ValueError, match="exactly one wheel and one sdist"):
        validate_artifacts([sdist], PACKAGE_VERSION)


def test_validate_artifacts_rejects_malformed_wheel_archive(tmp_path: Path) -> None:
    malformed_wheel = tmp_path / "malformed.whl"
    malformed_wheel.write_bytes(b"not a wheel")
    valid_directory = tmp_path / "valid"
    valid_directory.mkdir()
    valid_sdist = _write_artifacts(valid_directory, PACKAGE_VERSION, PACKAGE_VERSION)[1]
    with raises(ValueError, match="Invalid wheel archive"):
        validate_artifacts([malformed_wheel, valid_sdist], PACKAGE_VERSION)
