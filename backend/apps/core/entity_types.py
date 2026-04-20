"""Public entity_type → linkable model class resolution.

Every linkable entity declares a hyphenated canonical public identifier via
``LinkableModel.entity_type``. This module is the single adapter from that
public string to the concrete model class. Callers that need Django's
concatenated ``_meta.model_name`` or a ContentType use the returned class
directly.

Unknown (or concatenated / Django-internal) entity_type strings raise
``ValueError``; callers translate to HTTP 404.
"""

from __future__ import annotations

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured

from apps.core.models import LinkableModel

_ENTITY_TYPE_MAP: dict[str, type[LinkableModel]] | None = None


def _build_map() -> dict[str, type[LinkableModel]]:
    # Ensure all apps are loaded so every LinkableModel subclass is imported.
    apps.check_apps_ready()
    result: dict[str, type[LinkableModel]] = {}

    def walk(cls: type[LinkableModel]) -> None:
        for subclass in cls.__subclasses__():
            walk(subclass)
            meta = getattr(subclass, "_meta", None)
            if meta is None or meta.abstract:
                continue
            key = subclass.entity_type
            if key in result:
                raise ImproperlyConfigured(
                    f"Duplicate entity_type {key!r}: "
                    f"{result[key].__name__} and {subclass.__name__}"
                )
            result[key] = subclass

    walk(LinkableModel)
    return result


def get_linkable_model(entity_type: str) -> type[LinkableModel]:
    """Return the linkable model class for a canonical entity_type string.

    Raises ``ValueError`` if the entity_type is unknown — including
    Django-internal concatenated forms like ``'corporateentity'`` or
    ``'machinemodel'``.
    """
    global _ENTITY_TYPE_MAP
    if _ENTITY_TYPE_MAP is None:
        _ENTITY_TYPE_MAP = _build_map()
    try:
        return _ENTITY_TYPE_MAP[entity_type]
    except KeyError:
        raise ValueError(f"Unknown entity type: {entity_type}") from None
