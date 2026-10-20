"""Regression tests for the manual production release workflow."""

from io import BytesIO
from pathlib import Path
from re import search
from subprocess import run
from sys import executable
from tarfile import TarInfo
from tarfile import open as open_tar
from tomllib import loads
from zipfile import ZipFile

from pytest import raises

from scripts.validate_release_artifacts import validate_artifacts


ROOT = Path(__file__).resolve().parents[1]
PUBLISH_WORKFLOW = ROOT / ".github" / "workflows" / "publish.yml"


def _job(workflow: str, name: str, next_job: str) -> str:
    """Return one workflow job block by its YAML key boundaries."""
    return workflow.split(f"  {name}:\n", maxsplit=1)[1].split(f"  {next_job}:\n", maxsplit=1)[0]


def _write_release_artifacts(directory: Path, wheel_version: str, sdist_version: str) -> list[Path]:
    """Create wheel and sdist fixtures with package metadata versions."""
    wheel = directory / f"perplexity_webui_scraper-{wheel_version}-py3-none-any.whl"
    sdist = directory / f"perplexity_webui_scraper-{sdist_version}.tar.gz"
    wheel_metadata = f"Metadata-Version: 2.4\nName: perplexity-webui-scraper\nVersion: {wheel_version}\n"
    with ZipFile(wheel, "w") as archive:
        archive.writestr(f"perplexity_webui_scraper-{wheel_version}.dist-info/METADATA", wheel_metadata)
    sdist_metadata = f"Metadata-Version: 2.4\nName: perplexity-webui-scraper\nVersion: {sdist_version}\n".encode()
    metadata = TarInfo(f"perplexity_webui_scraper-{sdist_version}/PKG-INFO")
    metadata.size = len(sdist_metadata)
    with open_tar(sdist, "w:gz") as archive:
        archive.addfile(metadata, BytesIO(sdist_metadata))
    return [wheel, sdist]


def test_pypi_publish_uses_uv_duplicate_check_and_no_unused_cache() -> None:
    workflow = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    job = _job(workflow, "publish_pypi", "publish_container")

    assert "enable-cache: false" in job
    assert "ignore-empty-workdir: true" in job
    assert "--check-url https://pypi.org/simple/" in job
    assert "--trusted-publishing always" in job
    assert "UV_TRUSTED_PUBLISHING: always" in job
    assert "python3 scripts/check_pypi_artifacts.py" in job
    assert "python3 scripts/check_pypi_artifacts.py --verify-only" in job


def test_pypi_artifact_validation_runs_before_upload() -> None:
    workflow = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    job = _job(workflow, "build_package", "publish_pypi")

    assert job.index("twine check dist/*.whl dist/*.tar.gz") < job.index("validate_release_artifacts.py")
    assert 'validate_release_artifacts.py \\\n            --version "$PROJECT_VERSION" dist/*.whl dist/*.tar.gz' in job


def test_release_jobs_are_gated_on_successful_registry_publication() -> None:
    workflow = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    container_job = _job(workflow, "publish_container", "create_github_release")
    release_job = workflow.split("  create_github_release:\n", maxsplit=1)[1]

    assert "needs.publish_pypi.result == 'success'" in container_job
    assert "needs.publish_container.result == 'success'" in release_job
    assert "needs.publish_pypi.result == 'success'" in release_job


def test_resume_publish_uses_uv_duplicate_check_not_custom_script() -> None:
    workflow = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    job = _job(workflow, "publish_pypi", "publish_container")

    assert "actions/download-artifact" in job
    assert "uv publish --check-url https://pypi.org/simple/" in job


def test_publish_job_checks_out_release_sha_before_artifacts() -> None:
    workflow = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    job = _job(workflow, "publish_pypi", "publish_container")

    assert "enable-cache: false" in job
    checkout = job.index("name: Checkout Release Source")
    artifact_download = job.index("name: Download Package Artifacts")
    artifact_check = job.index("name: Verify PyPI Artifact State")
    assert checkout < artifact_download < artifact_check
    assert "ref: ${{ github.sha }}" in job
    assert "persist-credentials: false" in job
    assert "id-token: write" in job


def test_release_version_is_synchronized_across_project_lock_and_changelog() -> None:
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    project_version = loads(project)["project"]["version"]
    lock_match = search(r'name = "perplexity-webui-scraper"\nversion = "([^"]+)"', lock)

    changelog_headings = [line for line in changelog.splitlines() if line.startswith("## [")]

    assert project_version == "1.2.1"
    assert lock_match is not None
    assert lock_match.group(1) == project_version
    assert changelog_headings[1] == f"## [{project_version}] - 2026-10-20"


def test_release_artifacts_validate_matching_project_version(tmp_path: Path) -> None:
    artifacts = _write_release_artifacts(tmp_path, "1.2.1", "1.2.1")

    validate_artifacts(artifacts, "1.2.1")


def test_release_artifacts_reject_partial_version_mismatch(tmp_path: Path) -> None:
    artifacts = _write_release_artifacts(tmp_path, "1.2.0", "1.2.1")

    with raises(ValueError, match="Artifact versions must match"):
        validate_artifacts(artifacts, "1.2.1")


def test_release_artifact_validator_cli_checks_and_reports_artifacts(tmp_path: Path) -> None:
    artifacts = _write_release_artifacts(tmp_path, "1.2.1", "1.2.1")
    script = ROOT / "scripts" / "validate_release_artifacts.py"

    result = run(
        [executable, str(script), "--version", "1.2.1", *(str(path) for path in artifacts)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Validated 2 release artifacts for 1.2.1" in result.stdout
