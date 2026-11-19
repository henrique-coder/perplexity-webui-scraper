from os import environ, pathsep
from pathlib import Path
from shlex import quote
from subprocess import run
from sys import executable, platform

from pytest import mark, raises

from scripts.rewrite_pypi_readme import render_readme


ROOT = Path(__file__).resolve().parents[1]


def _logo_source() -> str:
    return (
        "![logo](https://raw.githubusercontent.com/henrique-coder/perplexity-webui-scraper/prod/docs/assets/icon.png)"
    )


def test_render_readme_uses_requested_reference_and_validates_logo_count() -> None:
    source = _logo_source()
    rendered = render_readme(source, "release-ref")

    assert "/release-ref/docs/assets/icon.png" in rendered
    assert "/prod/docs/assets/icon.png" not in rendered

    with raises(ValueError, match="revision"):
        render_readme(source, "../release")
    with raises(ValueError, match="exactly one"):
        render_readme("logo", "release-ref")
    with raises(ValueError, match="exactly one"):
        render_readme(f"{source}\n{source}", "release-ref")


def test_pypi_build_registers_readme_restoration_before_any_build_step() -> None:
    workflow = (ROOT / ".github" / "workflows" / "publish.yml").read_text(encoding="utf-8")
    build = workflow.split("      - name: Build and Validate Package\n", maxsplit=1)[1]
    backup = build.index('cp README.md "$README_BACKUP"')
    restore = build.index('cp "$README_BACKUP" README.md')
    trap = build.index("trap cleanup EXIT")
    render = build.index("scripts/rewrite_pypi_readme.py")
    build_package = build.index('uv build --python "$RELEASE_PYTHON"')

    assert backup < restore < trap < render < build_package


@mark.skipif(platform == "win32", reason="Tests POSIX shell trap in ubuntu-latest publish workflow")
def test_render_pypi_readme_restoration_trap_restores_source_after_failure(tmp_path: Path) -> None:
    workflow = (ROOT / ".github" / "workflows" / "publish.yml").read_text(encoding="utf-8")
    build = workflow.split("      - name: Build and Validate Package\n", maxsplit=1)[1]
    script = build.split("        run: |\n", maxsplit=1)[1]
    script = "\n".join(line.removeprefix("          ") for line in script.splitlines())
    script = script.split("\nsha256sum dist/* > dist/SHA256SUMS", maxsplit=1)[0]
    original = _logo_source()
    readme = tmp_path / "README.md"
    readme.write_text(original, encoding="utf-8")
    bin_directory = tmp_path / "bin"
    bin_directory.mkdir()
    render_script = ROOT / "scripts" / "rewrite_pypi_readme.py"
    uv_shim = bin_directory / "uv"
    uv_shim.write_text(
        "#!/bin/sh\n"
        'for arg in "$@"; do\n'
        '  if [ "$arg" = "scripts/rewrite_pypi_readme.py" ]; then\n'
        f'    exec {quote(executable)} {quote(str(render_script))} --reference "$GITHUB_SHA" --source README.md\n'
        "  fi\n"
        "done\n"
        "if grep -q 'release-ref/docs/assets/icon.png' README.md; then\n"
        "  : > rendered-before-build.marker\n"
        "fi\n"
        "exit 91\n",
        encoding="utf-8",
    )
    uv_shim.chmod(0o755)
    test_env = environ.copy()
    test_env["GITHUB_SHA"] = "release-ref"
    test_env["PATH"] = f"{bin_directory}{pathsep}{test_env.get('PATH', '')}"

    result = run(
        ["bash", "-e", "-c", script],
        cwd=tmp_path,
        env=test_env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 91
    assert (tmp_path / "rendered-before-build.marker").exists()
    assert readme.read_text(encoding="utf-8") == original
