"""Tests for CI path classification."""

from pathlib import Path
from subprocess import run

from pytest import mark

from scripts.ci_changed_paths import _changed_paths, classify_paths


def test_python_changes_run_python_checks_and_documentation() -> None:
    """Source changes validate code, tests, package, and API documentation."""
    assert classify_paths(["src/perplexity_webui_scraper/models/types.py"]) == {
        "python": True,
        "documentation": False,
        "frontend": False,
        "workflows": False,
        "containers": False,
        "metadata": False,
    }


def test_removed_source_files_still_run_python_checks() -> None:
    """A source deletion cannot bypass the test and build jobs."""
    assert classify_paths(["src/perplexity_webui_scraper/legacy.py"])["python"]


def test_python_version_pin_runs_python_checks() -> None:
    """Changing the default interpreter pin must run Python validation."""
    result = classify_paths([".python-version"])

    assert result["python"]
    assert not result["metadata"]


def test_git_diff_includes_removed_files(tmp_path: Path) -> None:
    """Deleted files are included in the diff sent to the classifier."""
    run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)
    run(["git", "config", "user.email", "test@example.invalid"], cwd=tmp_path, check=True)
    source = tmp_path / "removed.py"
    source.write_text("pass\n", encoding="utf-8")
    run(["git", "add", "removed.py"], cwd=tmp_path, check=True)
    run(["git", "commit", "--quiet", "-m", "initial"], cwd=tmp_path, check=True)
    base = run(["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True, capture_output=True, text=True).stdout.strip()
    source.unlink()
    run(["git", "add", "--update"], cwd=tmp_path, check=True)
    run(["git", "commit", "--quiet", "-m", "remove"], cwd=tmp_path, check=True)
    head = run(["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True, capture_output=True, text=True).stdout.strip()

    assert _changed_paths(base, head, cwd=tmp_path) == ["removed.py"]


def test_workflow_only_changes_skip_python_checks() -> None:
    """Workflow maintenance has a focused validation path."""
    assert classify_paths([".github/workflows/ci.yml"]) == {
        "python": False,
        "documentation": False,
        "frontend": False,
        "workflows": True,
        "containers": False,
        "metadata": False,
    }


def test_readthedocs_configuration_runs_documentation_checks() -> None:
    """Read the Docs configuration changes must validate the documentation build."""
    assert classify_paths([".readthedocs.yaml"]) == {
        "python": False,
        "documentation": True,
        "frontend": False,
        "workflows": False,
        "containers": False,
        "metadata": False,
    }


def test_unclassified_metadata_still_receives_a_lightweight_check() -> None:
    """Repository policy and ownership files are not silently ignored."""
    assert classify_paths([".github/CODEOWNERS"]) == {
        "python": False,
        "documentation": False,
        "frontend": False,
        "workflows": False,
        "containers": False,
        "metadata": True,
    }


def test_container_changes_run_container_builds() -> None:
    """Container build inputs trigger image validation."""
    assert classify_paths(["Containerfile.mcp", ".dockerignore"]) == {
        "python": False,
        "documentation": False,
        "frontend": False,
        "workflows": False,
        "containers": True,
        "metadata": False,
    }


@mark.parametrize("path", ["Containerfile", "Containerfile.mcp", ".dockerignore"])
def test_each_container_input_is_classified(path: str) -> None:
    assert classify_paths([path])["containers"]


def test_publish_workflow_disables_uv_cache_without_checkout_or_dependencies() -> None:
    workflow = Path(".github/workflows/publish.yml").read_text(encoding="utf-8")

    publish_job = workflow.split("  publish_pypi:", maxsplit=1)[1].split("  publish_container:", maxsplit=1)[0]

    assert "enable-cache: false" in publish_job
    assert "uv publish dist/*.whl dist/*.tar.gz" in publish_job


def test_publish_workflow_verifies_pypi_artifact_hashes_before_resuming() -> None:
    workflow = Path(".github/workflows/publish.yml").read_text(encoding="utf-8")
    publish_job = workflow.split("  publish_pypi:", maxsplit=1)[1].split("  publish_container:", maxsplit=1)[0]

    assert "Check Existing PyPI Artifacts" in publish_job
    assert "python3 scripts/check_pypi_artifacts.py" in publish_job
    assert "steps.pypi_artifacts.outputs.publish == 'true'" in publish_job


def test_publish_job_checks_out_source_for_artifact_verifier() -> None:
    workflow = Path(".github/workflows/publish.yml").read_text(encoding="utf-8")
    publish_job = workflow.split("  publish_pypi:", maxsplit=1)[1].split("  publish_container:", maxsplit=1)[0]

    assert "uses: actions/checkout@" in publish_job
    assert "ref: ${{ github.sha }}" in publish_job


def test_publish_job_checks_out_source_before_downloading_artifacts() -> None:
    workflow = Path(".github/workflows/publish.yml").read_text(encoding="utf-8")
    publish_job = workflow.split("  publish_pypi:", maxsplit=1)[1].split("  publish_container:", maxsplit=1)[0]

    assert publish_job.index("name: Checkout Release Source") < publish_job.index("name: Download Package Artifacts")
