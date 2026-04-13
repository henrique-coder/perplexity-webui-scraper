"""AI model definitions and registry."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Model(BaseModel):
    """Immutable metadata for a single Perplexity AI model."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description='Canonical string key used to select this model (e.g. "gpt-5.4").')
    name: str = Field(description="Human-readable display name.")
    description: str = Field(description="Short description of the model's characteristics.")
    identifier: str = Field(description="Internal Perplexity model identifier sent in the API payload.")
    tool_name: str = Field(description="MCP tool name used to register this model.")
    subscription_tier: str = Field(description='Minimum Perplexity subscription required: "pro" or "max".')
    mode: str = Field(default="copilot", description='API request mode (e.g. "copilot").')


class ModelRegistry(BaseModel):
    """Registry of all available Perplexity AI models. Access via attribute or ``MODELS.resolve("model-id")``."""

    model_config = ConfigDict(frozen=True)

    best: Model = Field(
        default=Model(
            id="best",
            identifier="default",
            name="Pro",
            description="Automatically selects the most responsive model based on the query",
            mode="search",
            subscription_tier="pro",
            tool_name="pplx_ask",
        ),
        description="Auto-selects the best available model for the query.",
    )
    deep_research: Model = Field(
        default=Model(
            id="deep-research",
            identifier="pplx_alpha",
            name="Deep research",
            description="Fast and thorough for routine research",
            mode="research",
            subscription_tier="pro",
            tool_name="pplx_deep_research",
        ),
        description="Fast, thorough research model.",
    )
    sonar: Model = Field(
        default=Model(
            id="sonar",
            identifier="experimental",
            name="Sonar",
            description="Perplexity's latest model",
            subscription_tier="pro",
            tool_name="pplx_sonar",
        ),
        description="Perplexity's own latest model.",
    )
    gpt_5_4: Model = Field(
        default=Model(
            id="gpt-5.4",
            identifier="gpt54",
            name="GPT-5.4",
            description="OpenAI's latest model",
            subscription_tier="pro",
            tool_name="pplx_gpt54",
        ),
        description="OpenAI GPT-5.4.",
    )
    gpt_5_4_thinking: Model = Field(
        default=Model(
            id="gpt-5.4-thinking",
            identifier="gpt54_thinking",
            name="GPT-5.4 Thinking",
            description="OpenAI's latest model with thinking",
            subscription_tier="pro",
            tool_name="pplx_gpt54_thinking",
        ),
        description="OpenAI GPT-5.4 with extended thinking.",
    )
    gemini_3_1_pro: Model = Field(
        default=Model(
            id="gemini-3.1-pro",
            identifier="gemini31pro_low",
            name="Gemini 3.1 Pro",
            description="Google's latest model",
            subscription_tier="pro",
            tool_name="pplx_gemini31_pro",
        ),
        description="Google Gemini 3.1 Pro.",
    )
    gemini_3_1_pro_thinking: Model = Field(
        default=Model(
            id="gemini-3.1-pro-thinking",
            identifier="gemini31pro_high",
            name="Gemini 3.1 Pro Thinking",
            description="Google's latest model with thinking",
            subscription_tier="pro",
            tool_name="pplx_gemini31_pro_think",
        ),
        description="Google Gemini 3.1 Pro with extended thinking.",
    )
    claude_sonnet_4_6: Model = Field(
        default=Model(
            id="claude-sonnet-4.6",
            identifier="claude46sonnet",
            name="Claude Sonnet 4.6",
            description="Anthropic's fast model",
            subscription_tier="pro",
            tool_name="pplx_claude_s46",
        ),
        description="Anthropic Claude Sonnet 4.6.",
    )
    claude_sonnet_4_6_thinking: Model = Field(
        default=Model(
            id="claude-sonnet-4.6-thinking",
            identifier="claude46sonnetthinking",
            name="Claude Sonnet 4.6 Thinking",
            description="Anthropic's newest reasoning model",
            subscription_tier="pro",
            tool_name="pplx_claude_s46_think",
        ),
        description="Anthropic Claude Sonnet 4.6 with extended thinking.",
    )
    claude_opus_4_6: Model = Field(
        default=Model(
            id="claude-opus-4.6",
            identifier="claude46opus",
            name="Claude Opus 4.6",
            description="Anthropic's most advanced model",
            subscription_tier="max",
            tool_name="pplx_claude_o46",
        ),
        description="Anthropic Claude Opus 4.6 (max tier).",
    )
    claude_opus_4_6_thinking: Model = Field(
        default=Model(
            id="claude-opus-4.6-thinking",
            identifier="claude46opusthinking",
            name="Claude Opus 4.6 Thinking",
            description="Anthropic's Opus reasoning model with thinking",
            subscription_tier="max",
            tool_name="pplx_claude_o46_think",
        ),
        description="Anthropic Claude Opus 4.6 with extended thinking (max tier).",
    )
    nv_nemotron_3_super_thinking: Model = Field(
        default=Model(
            id="nv-nemotron-3-super-thinking",
            identifier="nv_nemotron_3_super",
            name="Nemotron 3 Super Thinking",
            description="NVIDIA's Nemotron 3 Super 120B model with thinking",
            subscription_tier="pro",
            tool_name="pplx_nemotron3_super_think",
        ),
        description="NVIDIA Nemotron 3 Super 120B with extended thinking.",
    )

    def resolve(self, model_id: str) -> Model:
        """Look up a model by its string ID (e.g. ``"gpt-5.4"``). Raises ``ValueError`` if not found."""

        for model in self._all():
            if model.id == model_id:
                return model

        available = ", ".join(f'"{m.id}"' for m in self._all())
        msg = f"Unknown model {model_id!r}. Available models: {available}"

        raise ValueError(msg)

    def _all(self) -> list[Model]:
        """Return all registered Model instances in definition order."""

        return [getattr(self, field) for field in self.model_fields]


#: Singleton registry. Use ``MODELS.resolve("model-id")`` or access attributes directly (e.g. ``MODELS.gpt_5_4``).
MODELS: ModelRegistry = ModelRegistry()


def _resolve_model(model_id: str) -> Model:
    """Shim kept for internal callers. Prefer ``MODELS.resolve(model_id)``."""

    return MODELS.resolve(model_id)
