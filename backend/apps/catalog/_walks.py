"""Catalog-local helper for walking the model registry.

Single canonical idiom for "give me the concrete subclasses of ``base`` that
live in the catalog app." Built on Django's app registry rather than
``__subclasses__()`` so it stays correct when abstract intermediates are
introduced between ``base`` and its concrete descendants.

Cross-app discovery should call ``apps.get_models()`` directly; the catalog
helper exists because most catalog walks are catalog-scoped and the scoping
documents intent.
"""

from __future__ import annotations

from django.apps import apps
from django.db.models import Model


def catalog_app_subclasses[T: Model](base: type[T]) -> list[type[T]]:
    """Return concrete catalog-app models that subclass ``base``.

    Filters out abstract models. ``base`` itself is excluded — callers walk
    descendants, not the base. Must be called after the app registry is
    populated (i.e. from ``AppConfig.ready()`` or later, never at module
    import time).
    """
    return [
        cls
        for cls in apps.get_app_config("catalog").get_models()
        if cls is not base and issubclass(cls, base) and not cls._meta.abstract
    ]
