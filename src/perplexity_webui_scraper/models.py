class ModelBase:
    """Base class for all models"""

    _identifier: str
    _mode: str

    @classmethod
    def get_identifier(cls) -> str:
        return cls._identifier

    @classmethod
    def get_mode(cls) -> str:
        return cls._mode


class ModelType:
    """Available models"""

    class Pro:
        """3x more sources with powerful models, increased limits, and detailed answers"""

        class Best(ModelBase):
            """Selects the best model for each query"""

            _identifier = "pplx_pro"
            _mode = "copilot"

        class Sonar(ModelBase):
            """Perplexity's fast model"""

            _identifier = "experimental"
            _mode = "copilot"

        class Claude37Sonnet(ModelBase):
            """Anthropic's advanced model"""

            _identifier = "claude2"
            _mode = "copilot"

        class GPT41(ModelBase):
            """OpenAI's advanced model"""

            _identifier = "gpt41"
            _mode = "copilot"

        class Gemini25Pro(ModelBase):
            """Google's latest model"""

            _identifier = "gemini2flash"
            _mode = "copilot"

        class Grok3Beta(ModelBase):
            """xAI's latest model"""

            _identifier = "grok"
            _mode = "copilot"

        class Reasoning:
            """Advanced problem solving"""

            class R11776(ModelBase):
                """Perplexity's unbiased reasoning model"""

                _identifier = "r1"
                _mode = "copilot"

            class o4mini(ModelBase):
                """OpenAI's latest reasoning model"""

                _identifier = "o4mini"
                _mode = "copilot"

            class Claude37SonnetThinking(ModelBase):
                """Anthropic's reasoning model"""

                _identifier = "claude37sonnetthinking"
                _mode = "copilot"

    class Research(ModelBase):
        """Advanced analysis on any topic"""

        _identifier = "pplx_alpha"
        _mode = "copilot"
