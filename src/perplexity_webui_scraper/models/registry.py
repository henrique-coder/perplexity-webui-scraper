"""Model registry — loads all AI model definitions from the static data file."""

from __future__ import annotations

from importlib.resources import files

from orjson import loads

from perplexity_webui_scraper.models.types import Model


class ModelRegistry:
    """Registry of all available Perplexity AI models.

    The registry is populated at instantiation time by reading ``models.json``
    from the ``_static`` package directory via ``importlib.resources``.  The
    singleton ``MODELS`` instance is created at module import time.

    Usage::

        from perplexity_webui_scraper.models import MODELS

        model = MODELS.resolve("perplexity/best")
        all_models = MODELS.list_all()
    """

    _models: dict[str, Model]

    def __init__(self) -> None:
        """Load models from the bundled ``models.json`` static asset."""
        self._models = {}
        static_pkg = files("perplexity_webui_scraper._static")
        models_file = static_pkg.joinpath("models.json")

        raw: bytes = models_file.read_bytes()  # type: ignore[arg-type]
        data: list[dict[str, object]] = loads(raw)

        for item in data:
            model = Model.model_validate(item)
            self._models[model.id] = model

    def resolve(self, model_id: str) -> Model:
        """Look up a model by its canonical string ID.

        Args:
            model_id: The model identifier, e.g. ``"perplexity/best"``.

        Returns:
            The matching :class:`Model` instance.

        Raises:
            ValueError: If ``model_id`` is not registered.
        """
        if model_id in self._models:
            return self._models[model_id]

        available = ", ".join(f'"{m}"' for m in self._models)
        raise ValueError(f"Unknown model {model_id!r}. Available models: {available}")

    def list_all(self) -> list[Model]:
        """Return all registered :class:`Model` instances in definition order.

        Returns:
            List of all models loaded from ``models.json``.
        """
        return list(self._models.values())


#: Singleton registry.  Import and use this directly.
#: ``MODELS.resolve("model-id")`` or ``MODELS.list_all()``.
MODELS: ModelRegistry = ModelRegistry()
