"""Encrypted token and configuration storage for the CLI.

Stores the Perplexity session token (encrypted with Fernet) and user
preferences in the platform-specific config directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from orjson import dumps, loads
from platformdirs import user_config_dir


_APP_NAME: str = "perplexity-webui-scraper"
_CONFIG_DIR: Path = Path(user_config_dir(_APP_NAME, ensure_exists=True))
_KEY_FILE: Path = _CONFIG_DIR / ".key"
_CONFIG_FILE: Path = _CONFIG_DIR / "config.json"


def _get_or_create_key() -> bytes:
    """Return the Fernet encryption key, creating one if it doesn't exist."""
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes()

    key = Fernet.generate_key()
    _KEY_FILE.write_bytes(key)
    _KEY_FILE.chmod(0o600)
    return key


def _get_fernet() -> Fernet:
    """Return a Fernet instance with the stored key."""
    return Fernet(_get_or_create_key())


def _load_config() -> dict[str, Any]:
    """Load the config file, returning empty dict if missing or corrupt."""
    if not _CONFIG_FILE.exists():
        return {}

    try:
        return dict(loads(_CONFIG_FILE.read_bytes()))
    except Exception:
        return {}


def _save_config(config: dict[str, Any]) -> None:
    """Persist the config dict to disk."""
    _CONFIG_FILE.write_bytes(dumps(config))
    _CONFIG_FILE.chmod(0o600)


def save_token(token: str) -> None:
    """Encrypt and save the session token."""
    fernet = _get_fernet()
    encrypted = fernet.encrypt(token.encode()).decode()

    config = _load_config()
    config["token"] = encrypted
    _save_config(config)


def load_token() -> str | None:
    """Load and decrypt the saved session token, or ``None`` if unavailable."""
    config = _load_config()
    encrypted = config.get("token")

    if not encrypted:
        return None

    try:
        fernet = _get_fernet()
        return fernet.decrypt(encrypted.encode()).decode()
    except InvalidToken:
        return None


def delete_token() -> None:
    """Remove the saved session token."""
    config = _load_config()
    config.pop("token", None)
    _save_config(config)


def get_default_model() -> str:
    """Return the user's default model, falling back to ``perplexity/best``."""
    config = _load_config()
    return str(config.get("default_model", "perplexity/best"))


def set_default_model(model: str) -> None:
    """Save the user's preferred default model."""
    config = _load_config()
    config["default_model"] = model
    _save_config(config)


def is_configured() -> bool:
    """Return ``True`` if a token has been saved."""
    return load_token() is not None


def get_config_dir() -> Path:
    """Return the path to the config directory."""
    return _CONFIG_DIR
