from pytest import raises

from scripts.render_pypi_readme import render_readme


def test_render_readme_uses_immutable_release_reference() -> None:
    source = '<img src="https://raw.githubusercontent.com/henrique-coder/perplexity-webui-scraper/prod/docs/assets/icon.png">'

    rendered = render_readme(source, "abc123")
    expected_url = (
        "https://raw.githubusercontent.com/henrique-coder/perplexity-webui-scraper/abc123/docs/assets/icon.png"
    )

    assert expected_url in rendered
    assert "/prod/docs/assets/icon.png" not in rendered


def test_render_readme_rejects_unsafe_reference() -> None:
    with raises(ValueError, match="revision"):
        render_readme("logo", "../prod")


def test_render_readme_requires_one_logo_url() -> None:
    with raises(ValueError, match="exactly one"):
        render_readme("logo", "abc123")
