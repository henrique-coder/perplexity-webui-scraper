"""Typing contract for conversation file inputs."""

from __future__ import annotations

from os import PathLike


FileInput = str | PathLike[str] | bytes | tuple[bytes, str] | tuple[bytes, str, str]
"""Local path, bytes, or bytes with a filename and optional MIME type."""


__all__ = ["FileInput"]
