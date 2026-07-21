"""Typed account session models and model-access validation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypeAlias, TypeVar

from pydantic import BaseModel, ConfigDict, Field, computed_field

from perplexity_webui_scraper._internal.exceptions import FileAccessError, ModelAccessError


if TYPE_CHECKING:
    from perplexity_webui_scraper.models.types import Model, ModelTier


AccountTier: TypeAlias = Literal["free", "pro", "max", "unknown"]
"""Normalized Perplexity account tier."""

T = TypeVar("T")

TIER_RANK: dict[str, int] = {
    "unknown": -1,
    "free": 0,
    "pro": 1,
    "max": 2,
}


class AccountUser(BaseModel):
    """Authenticated user details returned by ``/api/auth/session``."""

    model_config = ConfigDict(extra="allow")

    email: str | None = None
    id: str | None = None
    image: str | None = None
    name: str | None = None
    org_role: str | None = None
    org_uuid: str | None = None
    payment_tier: str | None = None
    subscription_source: str | None = None
    subscription_status: str | None = None
    subscription_tier: str | None = None
    username: str | None = None

    @computed_field
    @property
    def account_tier(self) -> AccountTier:
        """Normalize Perplexity's account/payment fields to ``free``/``pro``/``max``."""
        subscription_tier = (self.subscription_tier or "").lower()
        payment_tier = (self.payment_tier or "").lower()
        subscription_status = (self.subscription_status or "").lower()

        return normalize_account_tier(
            subscription_tier=subscription_tier,
            payment_tier=payment_tier,
            subscription_status=subscription_status,
            subscription_source=self.subscription_source,
        )


class AccountSession(BaseModel):
    """Authenticated account session returned by ``/api/auth/session``."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    expires: str | None = None
    prevent_username_redirect: bool | None = Field(default=None, alias="preventUsernameRedirect")
    user: AccountUser | None = None

    @computed_field
    @property
    def account_tier(self) -> AccountTier:
        """Return the normalized tier for this session."""
        if self.user is None:
            return "unknown"

        return self.user.account_tier


class AccountSettings(BaseModel):
    """Relevant user settings returned by ``/rest/user/settings``.

    The endpoint returns a large object. Unknown fields are retained by Pydantic
    so callers can still inspect newly added Perplexity settings.
    """

    model_config = ConfigDict(extra="allow")

    stripe_status: str | None = None
    revenuecat_status: str | None = None
    revenuecat_source: str | None = None
    subscription_status: str | None = None
    subscription_source: str | None = None
    subscription_tier: str | None = None
    default_model: str | None = None
    query_count: int | None = None
    query_count_copilot: int | None = None
    query_count_mobile: int | None = None
    is_verified: bool | None = None

    @computed_field
    @property
    def account_tier(self) -> AccountTier:
        """Normalize settings subscription fields to ``free``/``pro``/``max``."""
        return normalize_account_tier(
            subscription_tier=self.subscription_tier,
            payment_tier=None,
            subscription_status=self.subscription_status,
            subscription_source=self.subscription_source,
        )


class AccountProfile(BaseModel):
    """Combined typed account data from session and optional settings endpoints."""

    session: AccountSession
    settings: AccountSettings | None = None

    @computed_field
    @property
    def account_tier(self) -> AccountTier:
        """Return the most precise known account tier."""
        if self.session.account_tier != "unknown":
            return self.session.account_tier

        if self.settings is not None:
            return self.settings.account_tier

        return "unknown"


def normalize_account_tier(
    *,
    subscription_tier: str | None,
    payment_tier: str | None,
    subscription_status: str | None,
    subscription_source: str | None,
) -> AccountTier:
    """Normalize Perplexity subscription fields to a stable account tier."""
    tier = (subscription_tier or "").lower()
    payment = (payment_tier or "").lower()
    status = (subscription_status or "").lower()
    source = (subscription_source or "").lower()

    if tier == "max" or payment == "max":
        return "max"

    if tier == "pro":
        return "pro"

    if status in {"active", "trialing"} and payment and not payment.startswith("free"):
        return "pro"

    if tier == "free" or payment.startswith("free") or status == "none" or source == "none":
        return "free"

    return "unknown"


def ensure_model_access(session: AccountSession, model: Model) -> None:
    """Raise if *session* cannot access *model* based on its minimum tier."""
    account_tier = session.account_tier
    required_tier: ModelTier | None = model.min_tier

    if required_tier is None:
        return

    if TIER_RANK.get(account_tier, -1) < TIER_RANK[required_tier]:
        raise ModelAccessError(model.id, required_tier, account_tier)


def model_for_account(model: Model, account_tier: AccountTier) -> Model:
    """Return a model copy with tier-specific internal fields applied."""
    identifier = _select_tier_value(model.identifier_by_tier, account_tier) or model.identifier
    mode = _select_tier_value(model.mode_by_tier, account_tier) or model.mode

    if identifier == model.identifier and mode == model.mode:
        return model

    return model.model_copy(update={"identifier": identifier, "mode": mode})


def _select_tier_value(values_by_tier: dict[ModelTier, T], account_tier: AccountTier) -> T | None:
    """Select the highest eligible tier-specific value."""
    account_rank = TIER_RANK.get(account_tier, -1)
    candidates = ((TIER_RANK[tier], value) for tier, value in values_by_tier.items() if TIER_RANK[tier] <= account_rank)
    best = max(candidates, default=None, key=lambda item: item[0])

    if best is None:
        return None

    return best[1]


def ensure_file_access(account_tier: AccountTier, has_files: bool) -> None:
    """Raise if file attachments are not available for *account_tier*."""
    if has_files and account_tier == "free":
        raise FileAccessError(account_tier)
