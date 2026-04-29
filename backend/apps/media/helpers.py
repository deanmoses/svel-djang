"""Helpers for reading prefetched EntityMedia off catalog entities."""

from __future__ import annotations

from typing import cast

from django.db import models

from .models import EntityMedia


def all_media(entity: models.Model) -> list[EntityMedia]:
    """Return all ready EntityMedia rows prefetched onto *entity*.

    Raises AssertionError if the queryset wasn't set up with
    ``media_prefetch()`` (to_attr="all_media").
    """
    media = getattr(entity, "all_media", None)
    if media is None:
        raise AssertionError(
            f"{type(entity).__name__} was not loaded with media_prefetch()"
        )
    return cast(list[EntityMedia], media)


def primary_media(entity: models.Model) -> list[EntityMedia]:
    """Return primary EntityMedia rows prefetched onto *entity*.

    Raises AssertionError if the queryset wasn't set up with a Prefetch
    using to_attr="primary_media".
    """
    media = getattr(entity, "primary_media", None)
    if media is None:
        raise AssertionError(
            f"{type(entity).__name__} was not loaded with a primary_media prefetch"
        )
    return cast(list[EntityMedia], media)
