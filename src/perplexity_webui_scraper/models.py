# Third-party modules
from pydantic import BaseModel, Field


class Model(BaseModel):
    """AI model configuration"""

    identifier: str = Field(..., description="Model identifier used by API")
    mode: str = Field(default="copilot", description="Model execution mode")

    class Config:
        frozen = True


class Models:
    """Available AI models with their configurations"""

    RESEARCH = Model(identifier="pplx_alpha", mode="copilot")
    """Deep research on any topic (in-depth reports with more sources, charts, and advanced reasoning)"""

    LABS = Model(identifier="pplx_beta", mode="copilot")
    """Create projects from scratch (turn your ideas into completed docs, slides, dashboards, and more)"""

    BEST = Model(identifier="pplx_pro", mode="copilot")
    """Selects the best model for each query"""

    SONAR = Model(identifier="experimental", mode="copilot")
    """Perplexity's fast model"""

    GPT5 = Model(identifier="gpt5", mode="copilot")
    """OpenAI's latest model"""

    GPT5_THINKING = Model(identifier="gpt5_thinking", mode="copilot")
    """OpenAI's latest model with thinking"""

    CLAUDE45_SONNET = Model(identifier="claude45sonnet", mode="copilot")
    """Anthropic's newest advanced model"""

    CLAUDE45_SONNET_THINKING = Model(identifier="claude45sonnetthinking", mode="copilot")
    """Anthropic's newest reasoning model"""

    GEMINI25_PRO = Model(identifier="gemini2flash", mode="copilot")
    """Google's latest model"""

    GROK4 = Model(identifier="grok4nonthinking", mode="copilot")
    """xAI's advanced model"""

    GROK4_THINKING = Model(identifier="grok4", mode="copilot")
    """xAI's reasoning model"""
