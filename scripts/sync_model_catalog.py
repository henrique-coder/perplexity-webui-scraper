"""Synchronize the local model catalog from Perplexity's v2 configuration and UI.

Model status is deliberately preserved from the local catalog. Availability
checks are performed separately by ``probe_model_availability.py`` and are not
part of this synchronizer.
"""

from __future__ import annotations

from copy import deepcopy
from os import environ
from pathlib import Path
from re import IGNORECASE, sub
from subprocess import run
from sys import executable, version_info
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Annotated, Any, Final

from dotenv import dotenv_values
from orjson import OPT_INDENT_2, JSONDecodeError, dumps, loads
from pydantic import BaseModel, ConfigDict, Field
from typer import Exit, Option, Typer, echo

from perplexity_webui_scraper._internal.constants import (
    API_BASE_URL,
    API_SOURCE,
    API_VERSION,
    ENDPOINT_MODELS_CONFIG_V2,
    SESSION_COOKIE_PREFIX,
)
from perplexity_webui_scraper.auth.cookies import parse_session_credential
from perplexity_webui_scraper.http.client import HTTPClient
from perplexity_webui_scraper.models.types import Model, ModelMinTier, ModelMode


if version_info < (3, 15):
    from pydoll.playwright.sync_api import sync_playwright
else:
    sync_playwright = None


if TYPE_CHECKING:
    from collections.abc import Iterable


ROOT: Final[Path] = Path(__file__).resolve().parents[1]
MODELS_FILE: Final[Path] = ROOT / "src/perplexity_webui_scraper/_static/models.json"
DOC_GENERATOR: Final[Path] = ROOT / "scripts/generate_model_docs.py"
MODEL_MODES: Final[frozenset[str]] = frozenset({"search", "research"})
MODEL_ENTRY_KEYS: Final[frozenset[str]] = frozenset(Model.model_fields)

_WAIT_VISIBLE_MENU_JS: Final[str] = """
() => Array.from(document.querySelectorAll('[role="menuitemradio"], [role="menuitem"]')).some(
    (element) => {
        const style = window.getComputedStyle(element);
        return style.display !== 'none'
            && style.visibility !== 'hidden'
            && style.visibility !== 'collapse'
            && element.getClientRects().length > 0;
    }
)
""".strip()


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
    trimmed = sub(r"\s+thinking$", "", value.strip(), flags=IGNORECASE)

    return sub(r"[^a-z0-9]+", "", trimmed.casefold())


def _slug(value: str) -> str:
    """Create a stable public slug from endpoint-provided display text."""
    return sub(r"[^a-z0-9.]+", "-", value.casefold()).strip("-")


def _provider_slug(provider: str | None) -> str | None:
    """Convert an endpoint provider enum to the project's readable slug."""
    if not provider:
        return None

    lowered = provider.casefold()

    if lowered in {"xai", "x_ai"}:
        return "x-ai"

    if lowered in {"zai", "z_ai"}:
        return "z-ai"

    return lowered.replace("_ai", "").replace("_", "-")


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


def _read_session_token(env_file: Path) -> str:
    """Resolve and validate PERPLEXITY_SESSION_TOKEN from .env or environment."""
    file_token = (dotenv_values(env_file).get("PERPLEXITY_SESSION_TOKEN") or "").strip() if env_file.is_file() else ""
    token = file_token or environ.get("PERPLEXITY_SESSION_TOKEN", "").strip()

    if not token:
        raise RuntimeError("PERPLEXITY_SESSION_TOKEN is not set")

    parse_session_credential(token)

    return token


def _read_models(catalog_path: Path = MODELS_FILE) -> list[dict[str, Any]]:
    """Read and validate the current local catalog."""
    if not catalog_path.is_file():
        echo(f"Local catalog not found at {catalog_path}; starting with defaults.")

        return []

    try:
        data = loads(catalog_path.read_bytes())
    except (OSError, JSONDecodeError) as error:
        echo(f"Could not read {catalog_path} ({type(error).__name__}); starting with defaults.")

        return []

    if not isinstance(data, list):
        echo(f"Ignoring invalid catalog at {catalog_path}; starting with defaults.")

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
    """Read visible model family names from the authenticated picker using pydoll."""
    if sync_playwright is None:
        raise RuntimeError(
            "scripts/sync_model_catalog.py requires Python >=3.11, <3.15 "
            "(run with: uv run --isolated --python 3.11 --no-dev --group scripts python scripts/sync_model_catalog.py)"
        )

    credential = parse_session_credential(token)
    account_uuid = credential.name.removeprefix(SESSION_COOKIE_PREFIX)
    names: list[str] = []

    def collect(page: Any) -> None:
        page.wait_for_load_state("domcontentloaded")
        button = page.get_by_role("button", name="Model", exact=True)
        button.wait_for(state="visible", timeout=15_000)
        button.click()

        items = page.locator('[role="menuitemradio"], [role="menuitem"]')
        # Pydoll's Playwright compatibility layer omits CSS :visible pseudo-class support.
        page.wait_for_function(_WAIT_VISIBLE_MENU_JS, timeout=10_000)

        visible_items = [item for item in items.all() if item.is_visible()]
        visible_names = [
            name for item in visible_items for name in item.locator('span[translate="no"]').all_text_contents()
        ]
        names.extend(dict.fromkeys(name.strip() for name in visible_names if name.strip()))

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        try:
            context = browser.new_context()
            context.add_cookies(
                [
                    {
                        "name": credential.name,
                        "value": credential.value,
                        "url": f"{API_BASE_URL}/",
                        "secure": True,
                        "httpOnly": True,
                        "sameSite": "Lax",
                    },
                    {
                        "name": "__Host-pplx-last-active-account",
                        "value": account_uuid,
                        "url": f"{API_BASE_URL}/",
                        "secure": True,
                        "httpOnly": False,
                        "sameSite": "Lax",
                    },
                ]
            )
            page = context.new_page()
            page.goto(f"{API_BASE_URL}/", wait_until="domcontentloaded")
            collect(page)
        except Exception as error:
            raise RuntimeError("Failed to read the authenticated Perplexity model picker") from error
        finally:
            browser.close()

    if not names:
        raise RuntimeError("The Perplexity model picker returned no model names")

    return names


def _fetch_endpoint(token: str) -> EndpointCatalog:
    """Fetch and validate Perplexity's current v2 model configuration."""
    client = HTTPClient(token, timeout=30)

    try:
        response = client.get(
            ENDPOINT_MODELS_CONFIG_V2,
            params={"version": API_VERSION, "source": API_SOURCE},
        )
    finally:
        client.close()

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
        normalized = _normalize(name)
        candidates = groups.get(normalized, [])

        if not candidates:
            if normalized not in default_labels:
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
    identifier: str,
    detail: EndpointDetail,
    family: EndpointModel | None,
    reasoning: bool,
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
    raw_tier = family.subscription_tier if family else None
    min_tier: ModelMinTier = raw_tier if raw_tier in ("free", "pro", "max") else "unknown"
    mode: ModelMode = "research" if detail.mode == "research" else "copilot"

    entry: dict[str, Any] = {
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
    Model.model_validate(entry)

    return entry


def _synchronize(
    local: list[dict[str, Any]],
    endpoint: EndpointCatalog,
    webui_names: list[str],
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
        Model.model_validate(entry)

    rank = {identifier: index for index, identifier in enumerate(dict.fromkeys(ordered_identifiers))}

    def official_key(entry: dict[str, Any]) -> tuple[int, int]:
        entry_rank = min(
            (rank.get(identifier, len(rank)) for identifier in _entry_identifiers(entry)),
            default=len(rank),
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


app = Typer(
    name="sync-model-catalog",
    help="Synchronize the model catalog from Perplexity's v2 configuration and WebUI picker.",
    add_completion=False,
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.command()
def main(
    apply: Annotated[
        bool,
        Option("--apply/--no-apply", help="Write models.json and regenerate model documentation."),
    ] = True,
    check: Annotated[
        bool,
        Option("--check", help="Exit 1 when generated metadata differs from models.json."),
    ] = False,
) -> None:
    """Synchronize catalog metadata and optionally write files."""
    token = _read_session_token(ROOT / ".env")
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
    run([executable, str(DOC_GENERATOR)], cwd=ROOT, check=True)
    echo(f"Applied catalog synchronization to {MODELS_FILE}")


if __name__ == "__main__":
    app()
