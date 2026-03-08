"""Cache keys and invalidation helpers for the catalog app."""

from __future__ import annotations

from django.core.cache import cache

MODELS_ALL_KEY = "catalog:models:all"
MANUFACTURERS_ALL_KEY = "catalog:manufacturers:all"
PEOPLE_ALL_KEY = "catalog:people:all"
TITLES_ALL_KEY = "catalog:titles:all"


def invalidate_all() -> None:
    """Delete all cached /all/ endpoint data."""
    cache.delete(MODELS_ALL_KEY)
    cache.delete(MANUFACTURERS_ALL_KEY)
    cache.delete(PEOPLE_ALL_KEY)
    cache.delete(TITLES_ALL_KEY)
