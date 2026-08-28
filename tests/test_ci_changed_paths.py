"""Tests for CI path classification."""

from pathlib import Path
from subprocess import run

from scripts.ci_changed_paths import _changed_paths, classify_paths


def test_python_changes_run_python_checks_and_documentation() -> None:
    """Source changes validate code, tests, package, and API documentation."""
    assert classify_paths(["src/perplexity_webui_scraper/models/types.py"]) == {
        "python": True,
        "documentation": False,
        "frontend": False,
        "workflows": False,
        "metadata": False,
    }


def test_removed_source_files_still_run_python_checks() -> None:
    """A source deletion cannot bypass the test and build jobs."""
    assert classify_paths(["src/perplexity_webui_scraper/legacy.py"])["python"]


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
        "metadata": False,
    }


def test_readthedocs_configuration_runs_documentation_checks() -> None:
    """Read the Docs configuration changes must validate the documentation build."""
    assert classify_paths([".readthedocs.yaml"]) == {
        "python": False,
        "documentation": True,
        "frontend": False,
        "workflows": False,
        "metadata": False,
    }


def test_unclassified_metadata_still_receives_a_lightweight_check() -> None:
    """Repository policy and ownership files are not silently ignored."""
    assert classify_paths([".github/CODEOWNERS"]) == {
        "python": False,
        "documentation": False,
        "frontend": False,
        "workflows": False,
        "metadata": True,
    }
