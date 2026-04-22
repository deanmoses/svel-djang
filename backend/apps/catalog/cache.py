"""Cache keys and invalidation helpers for the catalog app."""

from __future__ import annotations

import json
from hashlib import md5
from typing import Any

from django.core.cache import cache
from django.http import HttpResponse

MODELS_ALL_KEY = "catalog:models:all"
MANUFACTURERS_ALL_KEY = "catalog:manufacturers:all"
PEOPLE_ALL_KEY = "catalog:people:all"
TITLES_ALL_KEY = "catalog:titles:all"
LOCATIONS_TREE_KEY = "catalog:locations:tree"


def get_cached_response(cache_key: str) -> HttpResponse | None:
    """Return a pre-built HttpResponse from cache, or None on miss.

    Cached values are ``(json_bytes, etag)`` tuples written by
    :func:`set_cached_response`.  The ETag is set on the response so
    ``ConditionalGetMiddleware`` can compare it with ``If-None-Match``
    and return 304 without any serialization or hashing.
    """
    cached = cache.get(cache_key)
    if not isinstance(cached, tuple):
        return None
    json_bytes, etag = cached
    response = HttpResponse(json_bytes, content_type="application/json")
    response["ETag"] = etag
    return response


def set_cached_response(
    cache_key: str, data: list[Any] | dict[str, Any]
) -> HttpResponse:
    """Serialize *data* to JSON, compute its ETag, cache both, and return
    an ``HttpResponse`` ready to send.
    """
    json_bytes = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
    etag = f'"{md5(json_bytes, usedforsecurity=False).hexdigest()}"'
    cache.set(cache_key, (json_bytes, etag), timeout=None)
    response = HttpResponse(json_bytes, content_type="application/json")
    response["ETag"] = etag
    return response


def invalidate_all() -> None:
    """Delete all cached /all/ endpoint data."""
    cache.delete(MODELS_ALL_KEY)
    cache.delete(MANUFACTURERS_ALL_KEY)
    cache.delete(PEOPLE_ALL_KEY)
    cache.delete(TITLES_ALL_KEY)
    cache.delete(LOCATIONS_TREE_KEY)
