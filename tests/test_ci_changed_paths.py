"""Tests for CI path classification."""

from os import environ
from pathlib import Path
from re import search
from subprocess import run
from sys import executable, platform
from textwrap import dedent

from pytest import mark

from scripts.classify_ci_paths import _changed_paths, classify_paths


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


def test_container_build_inputs_trigger_image_validation() -> None:
    """All configured container inputs trigger image validation."""
    for path in ("Containerfile", "Containerfile.mcp", ".dockerignore"):
        assert classify_paths([path])["containers"]


def test_release_policy_checks_run_only_for_internal_dev_to_prod_pull_requests() -> None:
    workflow = (REPOSITORY / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    required_job = workflow.split("  required:\n", maxsplit=1)[1]

    assert "github.event_name == 'pull_request'" in workflow
    assert "github.base_ref == 'prod'" in workflow
    assert "HEAD_REF: ${{ github.event.pull_request.head.ref }}" in workflow
    assert "HEAD_REPOSITORY: ${{ github.event.pull_request.head.repo.full_name }}" in workflow
    assert "github.event.pull_request.head.repo.full_name == github.repository" in workflow
    assert "RELEASE_POLICY_RESULT" in required_job
    assert '"$BUILD_RESULT" \\' in required_job
    assert '"$RELEASE_POLICY_RESULT";' in required_job
    assert 'if [ "$RELEASE_POLICY_RESULT" != "success" ]; then' in required_job
    assert (
        'if [ "$RELEASE_POLICY_RESULT" != "success" ] && [ "$RELEASE_POLICY_RESULT" != "skipped" ]; then'
        not in required_job
    )


@mark.skipif(platform == "win32", reason="Tests POSIX shell script in ubuntu-latest CI workflow")
def test_required_gate_rejects_skipped_release_policy_on_internal_promotion_pr() -> None:
    workflow = (REPOSITORY / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    required_job = workflow.split("  required:\n", maxsplit=1)[1]
    script = dedent(required_job.split("        run: |\n", maxsplit=1)[1])
    env = {
        **environ,
        "CHANGES_RESULT": "success",
        "PYTHON_QUALITY_RESULT": "success",
        "DOCUMENTATION_RESULT": "success",
        "FORMATTING_RESULT": "success",
        "WORKFLOW_LINT_RESULT": "success",
        "CONTAINERS_RESULT": "success",
        "TESTS_RESULT": "success",
        "BUILD_RESULT": "success",
        "RELEASE_POLICY_RESULT": "skipped",
        "EVENT_NAME": "pull_request",
        "BASE_REF": "prod",
        "HEAD_REF": "dev",
        "HEAD_REPOSITORY": "henrique-coder/perplexity-webui-scraper",
        "REPOSITORY": "henrique-coder/perplexity-webui-scraper",
    }

    result = run(["bash", "-c", script], cwd=REPOSITORY, env=env, check=False, capture_output=True, text=True)

    assert result.returncode != 0
    assert "production release policy must pass" in result.stdout


@mark.skipif(platform == "win32", reason="Tests POSIX shell script in ubuntu-latest CI workflow")
def test_required_gate_allows_skipped_release_policy_on_unrelated_push() -> None:
    workflow = (REPOSITORY / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    required_job = workflow.split("  required:\n", maxsplit=1)[1]
    script = dedent(required_job.split("        run: |\n", maxsplit=1)[1])
    env = {
        **environ,
        "CHANGES_RESULT": "success",
        "PYTHON_QUALITY_RESULT": "skipped",
        "DOCUMENTATION_RESULT": "skipped",
        "FORMATTING_RESULT": "success",
        "WORKFLOW_LINT_RESULT": "skipped",
        "CONTAINERS_RESULT": "skipped",
        "TESTS_RESULT": "skipped",
        "BUILD_RESULT": "skipped",
        "RELEASE_POLICY_RESULT": "skipped",
        "EVENT_NAME": "push",
        "BASE_REF": "",
        "HEAD_REF": "",
        "HEAD_REPOSITORY": "",
        "REPOSITORY": "henrique-coder/perplexity-webui-scraper",
    }

    result = run(["bash", "-c", script], cwd=REPOSITORY, env=env, check=False, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr


def test_publish_release_notes_stop_at_previous_minor_release(tmp_path: Path) -> None:
    workflow = (REPOSITORY / ".github" / "workflows" / "publish.yml").read_text(encoding="utf-8")
    changelog = tmp_path / "CHANGELOG.md"
    release_history = "## [3.4.5] - 2000-01-01\n\n"
    changelog.write_text(
        "## [Unreleased]\n\n" + release_history + "### Changed\n\n- Release recovery fix.\n\n"
        "## [3.4.4] - 2000-01-02\n\n"
        "### Fixed\n\n- Follow-up release fix.\n\n"
        "## [3.3.8] - 2000-01-03\n\n"
        "### Changed\n\n- Previous minor release.\n",
        encoding="utf-8",
    )
    step = workflow.split("      - name: Generate Release Notes from Changelog\n", maxsplit=1)[1]
    step = step.split("      - name: Create Immutable Tag and Release\n", maxsplit=1)[0]
    script = dedent(step.split("        run: |\n", maxsplit=1)[1])
    python_match = search(r'(?s)uv run --python "\$RELEASE_PYTHON" --no-project python - <<\'PY\'\n(.*?)\nPY\n', script)
    assert python_match is not None
    release_script = python_match.group(1)
    release_version = release_history.split("[", maxsplit=1)[1].split("]", maxsplit=1)[0]
    result = run(
        [executable, "-c", release_script],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        env={**environ, "VERSION": release_version, "REPOSITORY": "owner/repo"},
    )

    assert result.returncode == 0, result.stderr
    release_notes = (tmp_path / "release_notes.md").read_text(encoding="utf-8")

    assert "- Release recovery fix." in release_notes
    assert "- Follow-up release fix." in release_notes
    assert "- Previous minor release." not in release_notes
