from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tarfile import TarInfo
from tarfile import open as open_tar
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request
from zipfile import ZipFile

from pytest import raises

from scripts.verify_pypi_uploads import fetch_published_files, missing_artifact_paths, verify_with_retries
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
    monkeypatch.setattr("scripts.verify_pypi_uploads.sleep", lambda _seconds: None)

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


def test_verify_pypi_uploads_retries_cdn_propagation_delays(tmp_path: Path) -> None:
    artifacts = _write_artifacts(tmp_path, PACKAGE_VERSION, PACKAGE_VERSION)
    hashes = {path.name: sha256(path.read_bytes()).hexdigest() for path in artifacts}
    sleep_calls: list[float] = []
    responses: list[dict[str, str] | BaseException] = [
        {},
        URLError("temporary edge failure"),
        {artifacts[0].name: hashes[artifacts[0].name]},
        hashes,
    ]

    with patch("scripts.verify_pypi_uploads.fetch_published_files", side_effect=responses) as fetch_mock:
        missing = verify_with_retries(
            artifacts,
            "package",
            PACKAGE_VERSION,
            max_attempts=5,
            delay_seconds=1.5,
            sleep_fn=sleep_calls.append,
        )

    assert missing == []
    assert fetch_mock.call_count == 4
    assert sleep_calls == [1.5, 1.5, 1.5]


def test_verify_pypi_uploads_fails_immediately_on_digest_mismatch(tmp_path: Path) -> None:
    artifacts = _write_artifacts(tmp_path, PACKAGE_VERSION, PACKAGE_VERSION)
    sleep_calls: list[float] = []
    mismatched = {artifacts[0].name: "0" * 64}

    with (
        patch("scripts.verify_pypi_uploads.fetch_published_files", return_value=mismatched) as fetch_mock,
        raises(ValueError, match="different SHA-256 digest"),
    ):
        verify_with_retries(
            artifacts,
            "package",
            PACKAGE_VERSION,
            max_attempts=5,
            delay_seconds=1.0,
            sleep_fn=sleep_calls.append,
        )

    assert fetch_mock.call_count == 1
    assert sleep_calls == []


def test_verify_pypi_uploads_main_writes_publish_output_and_succeeds(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    artifacts = _write_artifacts(dist_dir, PACKAGE_VERSION, PACKAGE_VERSION)
    hashes = {path.name: sha256(path.read_bytes()).hexdigest() for path in artifacts}
    output_file = tmp_path / "github_output.txt"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PACKAGE_NAME", "package")
    monkeypatch.setenv("VERSION", PACKAGE_VERSION)
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

    with patch("scripts.verify_pypi_uploads.fetch_published_files", return_value=hashes):
        assert check_pypi_artifacts(["--verify-only"]) == 0
        assert check_pypi_artifacts([]) == 0

    assert output_file.read_text(encoding="utf-8") == "publish=false\n"
