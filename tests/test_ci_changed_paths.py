"""Tests for CI path classification."""

from os import environ
from pathlib import Path
from subprocess import run
from sys import executable
from textwrap import dedent

from pytest import mark

from scripts.ci_changed_paths import _changed_paths, classify_paths


REPOSITORY = Path(__file__).resolve().parents[1]


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
    assert "uv publish --check-url https://pypi.org/simple/ --trusted-publishing always" in publish_job


def test_publish_release_notes_include_all_changelog_entries_until_previous_release(tmp_path: Path) -> None:
    workflow = (REPOSITORY / ".github" / "workflows" / "publish.yml").read_text(encoding="utf-8")
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "## [Unreleased]\n\n"
        "## [1.2.1] - 2026-10-20\n\n"
        "### Changed\n\n- Release recovery fix.\n\n"
        "## [1.2.0] - 2026-10-19\n\n"
        "### Fixed\n\n- Add the Responses API.\n\n"
        "## [1.1.10] - 2026-10-05\n\n"
        "### Changed\n\n- Update the model catalog.\n",
        encoding="utf-8",
    )
    step = workflow.split("      - name: Generate Release Notes from Changelog\n", maxsplit=1)[1]
    step = step.split("      - name: Create Immutable Tag and Release\n", maxsplit=1)[0]
    script = dedent(step.split("        run: |\n", maxsplit=1)[1])

    python_step = script.split("python3 - <<'PY'\n", maxsplit=1)[1].split("\nPY\n", maxsplit=1)[0]
    result = run(
        [executable, "-c", python_step],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        env={**environ, "VERSION": "1.2.1", "REPOSITORY": "owner/repo"},
    )

    assert result.returncode == 0, result.stderr
    release_notes = (tmp_path / "release_notes.md").read_text(encoding="utf-8")
    assert "- Release recovery fix." in release_notes
    assert "- Add the Responses API." in release_notes
    assert "- Update the model catalog." not in release_notes


def test_publish_workflow_verifies_pypi_artifact_hashes_before_resuming() -> None:
    workflow = Path(".github/workflows/publish.yml").read_text(encoding="utf-8")
    publish_job = workflow.split("  publish_pypi:\n", maxsplit=1)[1].split("  publish_container:\n", maxsplit=1)[0]

    assert "python3 scripts/check_pypi_artifacts.py" in publish_job
    assert "python3 scripts/check_pypi_artifacts.py --verify-only" in publish_job
    assert "uv publish --check-url https://pypi.org/simple/" in publish_job
    assert "steps.pypi_artifacts.outputs.publish == 'true'" not in publish_job


def test_publish_job_checks_out_source_for_artifact_verifier() -> None:
    workflow = Path(".github/workflows/publish.yml").read_text(encoding="utf-8")
    publish_job = workflow.split("  publish_pypi:\n", maxsplit=1)[1].split("  publish_container:\n", maxsplit=1)[0]
    checkout = publish_job.index("name: Checkout Release Source")
    artifact_download = publish_job.index("name: Download Package Artifacts")
    artifact_check = publish_job.index("name: Verify PyPI Artifact State")

    assert checkout < artifact_download < artifact_check


def test_publish_job_checks_out_source_before_downloading_artifacts() -> None:
    workflow = Path(".github/workflows/publish.yml").read_text(encoding="utf-8")
    publish_job = workflow.split("  publish_pypi:\n", maxsplit=1)[1].split("  publish_container:\n", maxsplit=1)[0]

    assert publish_job.index("name: Checkout Release Source") < publish_job.index("name: Download Package Artifacts")
