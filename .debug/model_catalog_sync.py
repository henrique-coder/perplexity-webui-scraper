# /// script
# requires-python = ">=3.11, <3.16"
# dependencies = [
#     "curl-cffi",
#     "orjson",
#     "perplexity-webui-scraper",
#     "pydantic",
#     "pydoll-python>=3.0.0",
#     "python-dotenv",
#     "typer",
# ]
# ///

"""Synchronize the local model catalog from Perplexity's v2 configuration and UI.

Model status is deliberately preserved from the local catalog. Availability
checks are performed separately by the status workflow and are not part of
this synchronizer.
"""

from __future__ import annotations

from copy import deepcopy
from os import environ
from pathlib import Path
from re import IGNORECASE, sub
from subprocess import run
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Annotated, Any, Literal

from curl_cffi.requests import Session
from dotenv import load_dotenv
from orjson import OPT_INDENT_2, JSONDecodeError, dumps, loads
from pydantic import BaseModel, ConfigDict, Field
from pydoll.playwright.sync_api import Page, sync_playwright
from typer import Exit, Option, Typer, echo

from perplexity_webui_scraper._internal.constants import API_BASE_URL, API_VERSION, SESSION_COOKIE_NAME


if TYPE_CHECKING:
    from collections.abc import Iterable


ROOT = Path(__file__).resolve().parents[1]
MODELS_FILE = ROOT / "src/perplexity_webui_scraper/_static/models.json"
DOC_RENDERER = ROOT / "scripts/render_model_docs.py"
MODELS_URL = f"{API_BASE_URL}/rest/models/config/v2"
MODEL_MODES = {"search", "research"}
MODEL_ENTRY_KEYS = frozenset(
    {
        "id",
        "name",
        "description",
        "identifier",
        "identifier_by_tier",
        "tool_name",
        "provider",
        "min_tier",
        "is_official",
        "mode",
        "mode_by_tier",
        "status",
        "last_tested_at",
    }
)


class EndpointModel(BaseModel):
    """One model family exposed by the WebUI picker configuration."""

    model_config = ConfigDict(extra="ignore")

    label: str
    description: str | None = None
    subscription_tier: str | None = None
    non_reasoning_model: str | None = None
    reasoning_model: str | None = None


class EndpointDetail(BaseModel):
    """Metadata for one internal model identifier."""

    model_config = ConfigDict(extra="ignore")

    label: str
    description: str | None = None
    mode: str | None = None
    provider: str | None = None


class EndpointCatalog(BaseModel):
    """Relevant portions of Perplexity's v2 model configuration."""

    model_config = ConfigDict(extra="ignore")

    models: dict[str, EndpointDetail]
    search_config: list[EndpointModel]
    default_models: dict[str, str] = Field(default_factory=dict)


class FamilyVariant(BaseModel):
    """A picker family variant and whether it uses reasoning mode."""

    identifier: str
    reasoning: bool


class ResolvedFamily(BaseModel):
    """A picker family resolved against the endpoint registry."""

    model: EndpointModel
    variants: list[FamilyVariant]


def _normalize(value: str) -> str:
    """Normalize UI labels for comparison without relying on model names."""
    value = sub(r"\s+thinking$", "", value.strip(), flags=IGNORECASE)
    return sub(r"[^a-z0-9]+", "", value.casefold())


def _slug(value: str) -> str:
    """Create a stable public slug from endpoint-provided display text."""
    return sub(r"[^a-z0-9.]+", "-", value.casefold()).strip("-")


def _provider_slug(provider: str | None) -> str | None:
    """Convert an endpoint provider enum to the project's readable slug."""
    if not provider:
        return None

    slug = provider.casefold().replace("_ai", "").replace("_", "-")
    if slug in {"xai", "zai"}:
        return f"{slug[0]}-{slug[1:]}"
    return slug


def _public_id(provider: str, label: str, reasoning: bool) -> str:
    """Build a new public ID from provider and endpoint label data."""
    slug = _slug(label)
    if reasoning and not slug.endswith("-thinking"):
        slug = f"{slug}-thinking"
    return f"{provider}/{slug}"


def _tool_name(model_id: str) -> str:
    """Build a deterministic MCP tool name from a generated public ID."""
    slug = model_id.split("/", maxsplit=1)[-1]
    words: list[str] = []
    for word in slug.split("-"):
        normalized = word.replace(".", "")
        if normalized == "thinking":
            normalized = "think"
        if normalized.isdigit() and words:
            words[-1] += normalized
        else:
            words.append(normalized)
    return "pplx_" + "_".join(words)


def _read_models() -> list[dict[str, Any]]:
    """Read and validate the current local catalog."""
    if not MODELS_FILE.is_file():
        echo(f"Local catalog not found at {MODELS_FILE}; starting with defaults.")
        return []

    try:
        data = loads(MODELS_FILE.read_bytes())
    except (OSError, JSONDecodeError) as error:
        echo(f"Could not read {MODELS_FILE} ({error}); starting with defaults.")
        return []

    if not isinstance(data, list):
        echo(f"Ignoring invalid catalog at {MODELS_FILE}; starting with defaults.")
        return []

    entries: list[dict[str, Any]] = []
    skipped = 0
    for item in data:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("id"), str)
            or not isinstance(item.get("identifier"), str)
        ):
            skipped += 1
            continue
        entries.append({key: value for key, value in item.items() if key in MODEL_ENTRY_KEYS})
    if skipped:
        echo(f"Skipped {skipped} invalid local catalog entries.")
    return entries


def _atomic_write(path: Path, value: object) -> None:
    """Write JSON atomically so a failed sync cannot leave a partial catalog."""
    with NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(dumps(value, option=OPT_INDENT_2))
        handle.write(b"\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def _fetch_webui_models(token: str) -> list[str]:
    """Read visible model family names from the authenticated picker."""
    names: list[str] = []
    error: Exception | None = None

    def collect(page: Page) -> None:
        nonlocal error
        try:
            page.wait_for_load_state("domcontentloaded")
            button = page.get_by_role("button", name="Model", exact=True)
            button.wait_for(state="visible", timeout=15_000)
            button.click()
            items = page.locator('[role="menuitemradio"], [role="menuitem"]')
            # Pydoll's Playwright layer does not implement Playwright's CSS :visible pseudo-class.
            page.wait_for_function(
                """() => Array.from(document.querySelectorAll('[role="menuitemradio"], [role="menuitem"]')).some(
                    (element) => {
                        const style = window.getComputedStyle(element);
                        return style.display !== 'none'
                            && style.visibility !== 'hidden'
                            && style.visibility !== 'collapse'
                            && element.getClientRects().length > 0;
                    }
                )""",
                timeout=10_000,
            )
            visible_items = [item for item in items.all() if item.is_visible()]
            visible_names = [
                name for item in visible_items for name in item.locator('span[translate="no"]').all_text_contents()
            ]
            names.extend(dict.fromkeys(name.strip() for name in visible_names if name.strip()))
        except Exception as exc:
            error = exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            context.add_cookies(
                [
                    {
                        "name": SESSION_COOKIE_NAME,
                        "value": token,
                        "url": f"{API_BASE_URL}/",
                        "secure": True,
                        "httpOnly": True,
                        "sameSite": "Lax",
                    }
                ]
            )
            page = context.new_page()
            page.goto(f"{API_BASE_URL}/", wait_until="domcontentloaded")
            collect(page)
        finally:
            browser.close()

    if error:
        raise RuntimeError("Failed to read the authenticated Perplexity model picker") from error
    if not names:
        raise RuntimeError("The Perplexity model picker returned no model names")
    return names


def _fetch_endpoint(token: str) -> EndpointCatalog:
    """Fetch and validate Perplexity's current v2 configuration."""
    with Session(impersonate="chrome") as session:
        response = session.get(
            MODELS_URL,
            params={"version": API_VERSION, "source": "default"},
            cookies={SESSION_COOKIE_NAME: token},
            headers={
                "Accept": "application/json",
                "Referer": f"{API_BASE_URL}/",
                "X-App-ApiClient": "default",
                "X-App-ApiVersion": API_VERSION,
            },
            timeout=30,
        )
    response.raise_for_status()
    return EndpointCatalog.model_validate(loads(response.content))


def _variants(model: EndpointModel) -> list[FamilyVariant]:
    """Return endpoint-provided non-reasoning and reasoning variants."""
    variants: list[FamilyVariant] = []
    if model.non_reasoning_model:
        variants.append(FamilyVariant(identifier=model.non_reasoning_model, reasoning=False))
    if model.reasoning_model:
        variants.append(FamilyVariant(identifier=model.reasoning_model, reasoning=True))
    return variants


def _uses_default_namespace(model: EndpointModel, defaults: Iterable[str]) -> bool:
    """Identify browser/default selector entries when labels collide."""
    identifiers = (model.non_reasoning_model, model.reasoning_model)
    return any(
        identifier and any(identifier == default or identifier.startswith(f"{default}_") for default in defaults)
        for identifier in identifiers
    )


def _resolve_families(endpoint: EndpointCatalog, webui_names: list[str]) -> list[ResolvedFamily]:
    """Resolve visible UI families to unique endpoint picker entries."""
    groups: dict[str, list[EndpointModel]] = {}
    for model in endpoint.search_config:
        groups.setdefault(_normalize(model.label), []).append(model)

    default_identifiers = set(endpoint.default_models.values())
    default_labels = {
        _normalize(endpoint.models[identifier].label)
        for identifier in default_identifiers
        if identifier in endpoint.models
    }
    families: list[ResolvedFamily] = []
    unmatched: list[str] = []

    for name in dict.fromkeys(webui_names):
        candidates = groups.get(_normalize(name), [])
        if not candidates:
            if _normalize(name) not in default_labels:
                unmatched.append(name)
            continue

        preferred = [model for model in candidates if not _uses_default_namespace(model, default_identifiers)]
        resolved = preferred or candidates
        if len(resolved) != 1:
            labels = ", ".join(model.label for model in resolved)
            raise RuntimeError(f"Ambiguous UI model {name!r}; candidates: {labels}")
        families.append(ResolvedFamily(model=resolved[0], variants=_variants(resolved[0])))

    if unmatched:
        raise RuntimeError(f"UI model names without endpoint matches: {', '.join(unmatched)}")
    if not families:
        raise RuntimeError("No current WebUI model families were resolved")
    return families


def _default_order(endpoint: EndpointCatalog, webui_names: list[str]) -> list[str]:
    """Return default model identifiers represented by the current catalog."""
    picker_labels = {_normalize(model.label) for model in endpoint.search_config}
    ui_labels = {_normalize(name) for name in webui_names if _normalize(name) not in picker_labels}
    identifiers: list[str] = []
    for identifier, model in endpoint.models.items():
        if (
            _normalize(model.label) in ui_labels
            and model.provider
            and model.mode in MODEL_MODES
            and identifier not in identifiers
        ):
            identifiers.append(identifier)

    for identifier in endpoint.default_models.values():
        model = endpoint.models.get(identifier)
        if model and model.provider and model.mode in MODEL_MODES and identifier not in identifiers:
            identifiers.append(identifier)
    return identifiers


def _entry_identifiers(entry: dict[str, Any]) -> set[str]:
    """Return the primary and tier-specific internal IDs for a local entry."""
    identifiers = {str(entry["identifier"])}
    overrides = entry.get("identifier_by_tier", {})
    if isinstance(overrides, dict):
        identifiers.update(str(value) for value in overrides.values())
    return identifiers


def _new_entry(
    identifier: str, detail: EndpointDetail, family: EndpointModel | None, reasoning: bool
) -> dict[str, Any]:
    """Create a new unverified entry entirely from endpoint metadata."""
    provider = _provider_slug(detail.provider)
    if provider is None:
        raise RuntimeError(f"Cannot generate a public model entry without provider: {identifier}")
    model_id = _public_id(provider, detail.label, reasoning)
    name = detail.label
    if reasoning and not name.casefold().endswith("thinking"):
        name = f"{name} Thinking"
    description = detail.description or f"{name} model."
    tier = family.subscription_tier if family else None
    min_tier = tier if tier in {"free", "pro", "max"} else None
    mode: Literal["copilot", "search", "research"] = "research" if detail.mode == "research" else "copilot"
    return {
        "id": model_id,
        "name": name,
        "description": description,
        "identifier": identifier,
        "tool_name": _tool_name(model_id),
        "min_tier": min_tier,
        "mode": mode,
        "provider": provider,
        "status": "unknown",
        "last_tested_at": None,
        "is_official": True,
    }


def _synchronize(
    local: list[dict[str, Any]], endpoint: EndpointCatalog, webui_names: list[str]
) -> list[dict[str, Any]]:
    """Merge current official models into the local catalog without deleting history."""
    families = _resolve_families(endpoint, webui_names)
    default_ids = _default_order(endpoint, webui_names)
    family_by_identifier: dict[str, tuple[EndpointModel | None, bool]] = {}
    ordered_identifiers = list(default_ids)
    for family in families:
        for variant in family.variants:
            family_by_identifier[variant.identifier] = (family.model, variant.reasoning)
            ordered_identifiers.append(variant.identifier)

    official_identifiers = set(ordered_identifiers)
    by_identifier: dict[str, dict[str, Any]] = {}
    for entry in local:
        for identifier in _entry_identifiers(entry):
            by_identifier[identifier] = entry

    additions: list[dict[str, Any]] = []
    for identifier in ordered_identifiers:
        if identifier in by_identifier:
            continue
        detail = endpoint.models.get(identifier)
        if detail is None:
            raise RuntimeError(f"Endpoint default or UI identifier is missing from models: {identifier}")
        family, reasoning = family_by_identifier.get(identifier, (None, False))
        additions.append(_new_entry(identifier, detail, family, reasoning))
        by_identifier[identifier] = additions[-1]

    all_entries = [*(deepcopy(entry) for entry in local), *additions]
    original_positions = {id(entry): index for index, entry in enumerate(all_entries)}
    for entry in all_entries:
        entry["is_official"] = bool(_entry_identifiers(entry) & official_identifiers)

    rank = {identifier: index for index, identifier in enumerate(dict.fromkeys(ordered_identifiers))}

    def official_key(entry: dict[str, Any]) -> tuple[int, int]:
        entry_rank = min(
            (rank.get(identifier, len(rank)) for identifier in _entry_identifiers(entry)), default=len(rank)
        )
        return entry_rank, original_positions[id(entry)]

    official = sorted((entry for entry in all_entries if entry["is_official"]), key=official_key)
    historical = [entry for entry in all_entries if not entry["is_official"]]
    return [*official, *historical]


def _summary(current: list[dict[str, Any]], candidate: list[dict[str, Any]]) -> None:
    """Print a concise synchronization summary."""
    current_ids = {entry["id"] for entry in current}
    candidate_ids = {entry["id"] for entry in candidate}
    available = sum(entry.get("status") == "available" for entry in candidate)
    unknown = sum(entry.get("status") == "unknown" for entry in candidate)
    unavailable = sum(entry.get("status") == "unavailable" for entry in candidate)
    echo(f"Current entries: {len(current)}; generated entries: {len(candidate)}")
    echo(f"Official: {sum(bool(entry.get('is_official')) for entry in candidate)}")
    echo(f"Status preserved: {available} available, {unknown} unknown, {unavailable} unavailable")
    echo(f"Added: {sorted(candidate_ids - current_ids) or 'none'}")
    echo(f"Removed: {sorted(current_ids - candidate_ids) or 'none'}")
    if current != candidate:
        echo("Catalog differs from the local file.")
    else:
        echo("Generated catalog is byte-for-byte equivalent after JSON normalization.")


app = Typer(add_completion=False, no_args_is_help=False)


@app.command()
def main(
    apply: Annotated[
        bool, Option("--apply/--no-apply", help="Write models.json and regenerate model documentation")
    ] = True,
    check: Annotated[bool, Option("--check", help="Exit 1 when generated metadata differs from models.json")] = False,
) -> None:
    """Synchronize catalog metadata and optionally write files."""
    load_dotenv(ROOT / ".env")
    token = environ.get("PERPLEXITY_SESSION_TOKEN", "").strip()
    if not token:
        raise RuntimeError("PERPLEXITY_SESSION_TOKEN is not set")

    current = _read_models()
    webui_names = _fetch_webui_models(token)
    endpoint = _fetch_endpoint(token)
    candidate = _synchronize(current, endpoint, webui_names)

    _summary(current, candidate)
    if check:
        raise Exit(code=int(current != candidate))
    if not apply:
        return

    _atomic_write(MODELS_FILE, candidate)
    run(["uv", "run", "--no-dev", str(DOC_RENDERER)], cwd=ROOT, check=True)
    echo(f"Applied catalog synchronization to {MODELS_FILE}")


if __name__ == "__main__":
    app()
