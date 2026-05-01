"""Perplexity top-level client class."""

from __future__ import annotations

from perplexity_webui_scraper._internal.logging import configure_logging, get_logger
from perplexity_webui_scraper.config.client import ClientConfig
from perplexity_webui_scraper.config.conversation import ConversationConfig
from perplexity_webui_scraper.core.conversation import Conversation
from perplexity_webui_scraper.http.client import HTTPClient


logger = get_logger(__name__)


class Perplexity:
    """Web scraper client for Perplexity AI conversations.

    The primary entry point. Create a single instance per session token and reuse it
    to share the underlying HTTP session and rate limiter.

    Example:
        ```python
        with Perplexity(session_token="...") as client:
            conversation = client.create_conversation()
            conversation.ask("Hello, world!")
            print(conversation.answer)
        ```

    Args:
        session_token: The ``__Secure-next-auth.session-token`` cookie value.
            Obtained via the ``get-session-token`` CLI tool.
        config: Optional client settings (timeouts, retries, logging).

    Raises:
        ValueError: If ``session_token`` is empty.
    """

    __slots__ = ("_http",)

    def __init__(
        self,
        session_token: str,
        config: ClientConfig | None = None,
    ) -> None:
        if not session_token or not session_token.strip():
            raise ValueError("session_token cannot be empty")

        cfg = config or ClientConfig()
        configure_logging(level=cfg.logging_level, log_file=cfg.log_file)

        self._http = HTTPClient(
            session_token,
            timeout=cfg.timeout,
            impersonate=cfg.impersonate,
            max_retries=cfg.max_retries,
            retry_base_delay=cfg.retry_base_delay,
            retry_max_delay=cfg.retry_max_delay,
            retry_jitter=cfg.retry_jitter,
            requests_per_second=cfg.requests_per_second,
            rotate_fingerprint=cfg.rotate_fingerprint,
            max_init_query_length=cfg.max_init_query_length,
        )

        logger.info("Perplexity client initialized")

    def create_conversation(
        self,
        config: ConversationConfig | None = None,
    ) -> Conversation:
        """Create and return a new :class:`~perplexity_webui_scraper.Conversation`.

        Args:
            config: Optional per-conversation settings.  Defaults to
                :class:`~perplexity_webui_scraper.config.ConversationConfig`
                defaults.

        Returns:
            A new :class:`~perplexity_webui_scraper.Conversation` instance
            ready to receive queries.
        """
        return Conversation(self._http, config or ConversationConfig())

    def close(self) -> None:
        """Close the HTTP session and release all underlying resources."""
        self._http.close()

    def __enter__(self) -> Perplexity:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
