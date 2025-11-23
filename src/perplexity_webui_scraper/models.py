from pydantic import BaseModel, Field


class Model(BaseModel):
    """AI model configuration"""

    identifier: str = Field(..., description="Model identifier used by API")
    mode: str = Field(default="copilot", description="Model execution mode")

    class Config:
        frozen = True


class Models:
    """Available AI models with their configurations"""

    LABS = Model(identifier="pplx_beta", mode="copilot")
    """Create projects from scratch (turn your ideas into completed docs, slides, dashboards, and more)"""

    RESEARCH = Model(identifier="pplx_alpha", mode="copilot")
    """Deep research on any topic (in-depth reports with more sources, charts, and advanced reasoning)"""

    BEST = Model(identifier="pplx_pro", mode="copilot")
    """Automatically selects the best model based on the query"""

    SONAR = Model(identifier="experimental", mode="copilot")
    """Perplexity's fast model"""

    GPT_51 = Model(identifier="gpt51", mode="copilot")
    """OpenAI's latest model"""

    GPT_51_THINKING = Model(identifier="gpt51_thinking", mode="copilot")
    """OpenAI's latest model with reasoning"""

    CLAUDE_45_SONNET = Model(identifier="claude45sonnet", mode="copilot")
    """Anthropic's newest advanced model"""

    CLAUDE_45_SONNET_THINKING = Model(identifier="claude45sonnetthinking", mode="copilot")
    """Anthropic's newest advanced model with reasoning"""

    GEMINI_3_PRO_THINKING = Model(identifier="gemini30pro", mode="copilot")
    """Google's newest reasoning model"""

    GROK_41 = Model(identifier="grok41nonreasoning", mode="copilot")
    """xAI's latest advanced model"""

    KIMI_K2_THINKING = Model(identifier="kimik2thinking", mode="copilot")
    """"Moonshot's AI's latest reasoning model (hosted in the US)"""
