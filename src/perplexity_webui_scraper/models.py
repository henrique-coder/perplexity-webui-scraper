class ModelBase:
    """Base class for all models"""

    _identifier: str
    _mode: str

    @classmethod
    def _get_identifier(cls) -> str:
        return cls._identifier

    @classmethod
    def _get_mode(cls) -> str:
        return cls._mode


class ModelType:
    """Available models"""

    class Pro:
        """3x more sources with powerful models and increased limits"""

        class Best(ModelBase):
            """Selects the best model for each query"""

            _identifier = "pplx_pro"
            _mode = "copilot"

        class Sonar(ModelBase):
            """Perplexity's fast model"""

            _identifier = "experimental"
            _mode = "copilot"

        class Claude40Sonnet(ModelBase):
            """Anthropic's advanced model"""

            _identifier = "claude2"
            _mode = "copilot"

        class GPT41(ModelBase):
            """OpenAI's advanced model"""

            _identifier = "gpt41"
            _mode = "copilot"

        class Gemini25Pro0605(ModelBase):
            """Google's latest model"""

            _identifier = "gemini2flash"
            _mode = "copilot"

        class Reasoning:
            """Advanced problem solving"""

            class R11776(ModelBase):
                """Perplexity's unbiased reasoning model"""

                _identifier = "r1"
                _mode = "copilot"

            class Grok4(ModelBase):
                """xAI's latest, most powerful reasoning model"""

                _identifier = "grok4"
                _mode = "copilot"

            class o3(ModelBase):
                """OpenAI's reasoning model"""

                _identifier = "o3"
                _mode = "copilot"

            class Claude40SonnetThinking(ModelBase):
                """Anthropic's reasoning model"""

                _identifier = "claude37sonnetthinking"
                _mode = "copilot"

    class Research(ModelBase):
        """Deep research on any topic (in-depth reports with more sources, charts, and advanced reasoning)"""

        _identifier = "pplx_alpha"
        _mode = "copilot"
