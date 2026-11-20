"""Regression tests for the manual production release workflow."""

from io import BytesIO
from pathlib import Path
from re import fullmatch, search
from subprocess import run
from sys import executable
from tarfile import TarInfo
from tarfile import open as open_tar
from tomllib import loads
from zipfile import ZipFile

from pytest import raises

from scripts.verify_release_policy import validate_release_policy


ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
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
    assert 'uv run --python "$RELEASE_PYTHON" --no-project python scripts/verify_pypi_uploads.py' in job
    assert 'uv run --python "$RELEASE_PYTHON" --no-project python scripts/verify_pypi_uploads.py --verify-only' in job


def test_workflows_use_uv_instead_of_bare_python3() -> None:
    assert "python3" not in CI_WORKFLOW.read_text(encoding="utf-8")
    assert "python3" not in PUBLISH_WORKFLOW.read_text(encoding="utf-8")


def test_release_verifies_all_pypi_hashes_before_publishing_containers() -> None:
    workflow = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    job = _job(workflow, "publish_pypi", "publish_container")
    validation = job.index("name: Verify PyPI Artifact State")
    publish = job.index("name: Publish Distributions to PyPI")
    confirmation = job.index("name: Confirm PyPI Publication State")

    assert validation < publish < confirmation
    assert "sha256" in (ROOT / "scripts" / "verify_pypi_uploads.py").read_text(encoding="utf-8")
    assert "different SHA-256 digest" in (ROOT / "scripts" / "verify_pypi_uploads.py").read_text(encoding="utf-8")


def test_pypi_artifact_validation_runs_before_upload() -> None:
    workflow = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    job = _job(workflow, "build_package", "publish_pypi")

    assert job.index("twine check dist/*.whl dist/*.tar.gz") < job.index("verify_release_artifacts.py")
    assert 'verify_release_artifacts.py \\\n            --version "$PROJECT_VERSION" dist/*.whl dist/*.tar.gz' in job


def test_release_jobs_are_gated_on_successful_registry_publication() -> None:
    workflow = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    container_job = _job(workflow, "publish_container", "create_github_release")
    release_job = workflow.split("  create_github_release:\n", maxsplit=1)[1]

    assert "needs.publish_pypi.result == 'success'" in container_job
    assert "needs.publish_container.result == 'success'" in release_job
    assert "needs.publish_pypi.result == 'success'" in release_job


def test_publish_job_checks_out_release_sha_before_verifying_artifacts() -> None:
    workflow = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    job = _job(workflow, "publish_pypi", "publish_container")

    assert "enable-cache: false" in job
    checkout = job.index("name: Checkout Release Source")
    artifact_download = job.index("name: Download Package Artifacts")
    artifact_check = job.index("name: Verify PyPI Artifact State")
    assert checkout < artifact_download < artifact_check
    assert "ref: ${{ github.sha }}" in job
    assert "id-token: write" in job


def test_release_version_is_synchronized_across_project_lock_and_changelog() -> None:
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    project_version = loads(project)["project"]["version"]
    lock_match = search(r'name = "perplexity-webui-scraper"\nversion = "([^"]+)"', lock)
    changelog_headings = [line for line in changelog.splitlines() if line.startswith("## [")]

    assert project_version == "2.0.0"
    assert lock_match is not None
    assert lock_match.group(1) == project_version
    assert changelog_headings
    assert fullmatch(r"## \[2\.0\.0\] - (Unreleased|\d{4}-\d{2}-\d{2})", changelog_headings[0]) is not None


def test_unreleased_changelog_version_matches_project_metadata() -> None:
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    project_version = loads(project)["project"]["version"]
    top_heading = next(line for line in changelog.splitlines() if line.startswith("## ["))

    assert fullmatch(rf"## \[{project_version}\] - (Unreleased|\d{{4}}-\d{{2}}-\d{{2}})", top_heading) is not None


def test_changelog_2_0_0_contains_changes_not_release_planning_copy() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    top_heading = next(line for line in changelog.splitlines() if line.startswith("## [2.0.0] - "))
    release_notes = changelog.split(f"{top_heading}\n", maxsplit=1)[1].split("\n## [", maxsplit=1)[0]

    assert "Prepare the breaking release" not in release_notes
    assert "next release containing this breaking change" not in release_notes
    assert "`POST /v1/chat/completions`" in release_notes
    assert "`POST /v1/responses`" in release_notes
    assert "`wsk_`" in release_notes


def test_release_workflow_prevents_credentials_from_persisting_after_checkout() -> None:
    workflow = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    job = _job(workflow, "publish_pypi", "publish_container")

    checkout = job.index("name: Checkout Release Source")
    disable_credentials = job.index("persist-credentials: false", checkout)
    artifact_download = job.index("name: Download Package Artifacts", disable_credentials)

    assert checkout < disable_credentials < artifact_download


def test_release_artifact_validator_cli_checks_and_reports_artifacts(tmp_path: Path) -> None:
    version = loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    artifacts = _write_release_artifacts(tmp_path, version, version)
    script = ROOT / "scripts" / "verify_release_artifacts.py"

    result = run(
        [executable, str(script), "--version", version, *(str(path) for path in artifacts)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert f"Validated 2 release artifacts for {version}" in result.stdout


def test_release_policy_gate_rejects_unreleased_and_invalid_headings_and_accepts_dated(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "perplexity-webui-scraper"\nversion = "2.0.0"\n')
    (tmp_path / "uv.lock").write_text('[[package]]\nname = "perplexity-webui-scraper"\nversion = "2.0.0"\n')

    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## [2.0.0] - Unreleased\n\n- Changes\n")
    with raises(ValueError, match="Unreleased"):
        validate_release_policy(tmp_path)

    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## [2.0.0] - 2026-99-99\n\n- Changes\n")
    with raises(ValueError, match="invalid release date"):
        validate_release_policy(tmp_path)

    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## [1.9.0] - 2026-11-18\n\n- Changes\n")
    with raises(ValueError, match=r"does not match pyproject\.toml"):
        validate_release_policy(tmp_path)

    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## [2.0.0] - 2026-11-18\n\n- Changes\n")
    assert validate_release_policy(tmp_path, expected_version="2.0.0") == "2.0.0"

    ci_workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    publish_workflow = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    release_policy_job = _job(ci_workflow, "release_policy", "required")
    validate_job = _job(publish_workflow, "validate", "build_package")

    assert "scripts/verify_release_policy.py" in release_policy_job
    assert "scripts/verify_release_policy.py" in validate_job
    assert "GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in validate_job
