"""Typed models for the Perplexity user settings endpoint."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field


type AccountTier = Literal["free", "pro", "max", "unknown"]
"""Normalized account tier inferred from Perplexity user settings."""


class SourceLimit(BaseModel):
    """Monthly limit and remaining quota for a single source."""

    model_config = ConfigDict(extra="allow")

    monthly_limit: int | None = None
    remaining: int | None = None


class SourceLimits(BaseModel):
    """Source quota block returned by user settings."""

    model_config = ConfigDict(extra="allow")

    source_to_limit: dict[str, SourceLimit] = Field(default_factory=dict)


class RepositoryTypeLimit(BaseModel):
    """File and folder limits for a repository type."""

    model_config = ConfigDict(extra="allow")

    max_files: int | None = None
    max_folders: int | None = None


class ConnectorLimits(BaseModel):
    """Connector and file upload limits."""

    model_config = ConfigDict(extra="allow")

    repo_type_limits: dict[str, RepositoryTypeLimit] = Field(default_factory=dict)
    global_file_count: int | None = None
    max_file_size_mb: int | None = None
    max_attachment_file_size_mb: int | None = None
    daily_attachment_limit: int | None = None
    weekly_attachment_limit: int | None = None
    daily_attachment_limit_non_priority_country: int | None = None


class CouponMetadata(BaseModel):
    """Subscription coupon or partner metadata."""

    model_config = ConfigDict(extra="allow")

    accent_color: str | None = None
    coupon_amount: int | None = None
    coupon_duration: str | None = None
    coupon_duration_days: int | None = None
    coupon_id: str | None = None
    coupon_percent: int | None = None
    default_locale: str | None = None
    expires_at: str | None = None
    has_custom_notifications: bool | None = None
    logo_dark_image_url: str | None = None
    logo_image_url: str | None = None
    name: str | None = None
    promo_code_id: str | None = None


class PickerCredentials(BaseModel):
    """Connector picker credentials returned by Perplexity."""

    model_config = ConfigDict(extra="allow")

    client_id: str | None = None
    api_key: str | None = None
    tenant_name: str | None = None
    expires_at: str | None = None
    account_identifier: str | None = None


class ConnectorCapabilities(BaseModel):
    """Known connector capability flags."""

    model_config = ConfigDict(extra="allow")

    direct_api_search: bool | None = None
    file_upload: bool | None = None
    high_precision_search: bool | None = None


class ConnectorSettings(BaseModel):
    """Single connected or available Perplexity connector."""

    model_config = ConfigDict(extra="allow")

    name: str
    auth_type: str | None = None
    connected: bool
    error: str | None = None
    picker_credentials: PickerCredentials | None = None
    connection_display_name: str | None = None
    connection_uuid: str | None = None
    has_required_scopes: bool | None = None
    source_id: str | None = None
    connection_type: str | None = None
    capabilities: ConnectorCapabilities = Field(default_factory=ConnectorCapabilities)
    disabled_capabilities: list[str] = Field(default_factory=list)


class ConnectorSettingsList(BaseModel):
    """Container for all connector settings."""

    model_config = ConfigDict(extra="allow")

    connectors: list[ConnectorSettings] = Field(default_factory=list)


class UserSettings(BaseModel):
    """Typed response from ``/rest/user/settings``.

    The endpoint returns both account metadata and feature limits.  Known
    fields are modelled explicitly and unknown future fields are preserved by
    Pydantic via ``extra="allow"``.
    """

    model_config = ConfigDict(extra="allow")

    pages_limit: int | None = None
    upload_limit: int | None = None
    create_limit: int | None = None
    article_image_upload_limit: int | None = None
    max_files_per_user: int | None = None
    max_files_per_repository: int | None = None
    connector_limits: ConnectorLimits | None = None
    sources: SourceLimits | None = None
    has_ai_profile: bool | None = None
    referral_code: str | None = None
    referral_num_success: int | None = None
    referral_num_coupons: int | None = None
    stripe_status: str | None = None
    revenuecat_status: str | None = None
    revenuecat_source: str | None = None
    subscription_status: str | None = None
    subscription_source: str | None = None
    subscription_tier: str | None = None
    coupon_metadata: CouponMetadata | None = None
    default_model: str | None = None
    default_image_generation_model: str | None = None
    default_video_generation_model: str | None = None
    query_count: int | None = None
    query_count_copilot: int | None = None
    query_count_mobile: int | None = None
    disable_training: bool | None = None
    is_sidebar_collapsed: bool | None = None
    default_copilot: bool | None = None
    notif_status: str | None = None
    email_status: str | None = None
    time_zone: str | None = None
    device_language: str | None = None
    discover_homepage_enabled: bool | None = None
    always_allow_browser_agent: bool | None = None
    always_use_extended_context: bool | None = None
    inline_visualizations_enabled: bool | None = None
    has_accepted_api_terms: bool | None = None
    last_visited_homepage_tab: str | None = None
    last_visited_homepage_tab_updated_at: str | None = None
    default_homepage_tab: str | None = None
    release_phase: str | None = None
    has_data_retention_warning: bool | None = None
    resolved_default_homepage_tab: str | None = None
    effective_default_ask_input_mode: str | None = None
    resolved_always_use_extended_context: bool | None = None
    resolved_always_use_extended_thinking: bool | None = None
    is_verified: bool | None = None
    allow_article_creation: bool | None = None
    connectors: ConnectorSettingsList | None = None

    @computed_field
    @property
    def account_tier(self) -> AccountTier:
        """Best-effort normalized account tier: ``free``, ``pro``, ``max``, or ``unknown``."""
        tier = (self.subscription_tier or "").lower()
        status = (self.subscription_status or "").lower()
        stripe_status = (self.stripe_status or "").lower()
        source = (self.subscription_source or self.revenuecat_source or "").lower()

        if tier in {"max", "enterprise"}:
            return "max"

        if tier in {"pro", "monthly", "yearly", "annual"}:
            return "pro"

        if (status in {"active", "trialing"} or stripe_status in {"active", "trialing"}) and source not in {
            "",
            "none",
            "free",
        }:
            return "pro"

        if status in {"inactive", "canceled", "none", "free"} or (not status and not tier):
            return "free"

        return "unknown"
