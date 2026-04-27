"""Shared helpers for resolving catalog entity metadata from content-type refs.

Used by the user-profile endpoint and the recent-changes feed.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import TypedDict

from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.core.types import EntityKey


class ResolvedEntityMeta(TypedDict):
    href: str
    name: str
    type_label: str


def resolve_entity_href(
    model_class: type[models.Model], entity: models.Model
) -> str | None:
    """Build the frontend URL for a catalog entity from its link_url_pattern."""
    pattern = getattr(model_class, "link_url_pattern", None)
    public_id = getattr(entity, "public_id", None)
    if not isinstance(pattern, str) or not isinstance(public_id, str):
        return None
    return pattern.format(public_id=public_id)


def batch_resolve_entities(
    entity_keys: Sequence[EntityKey],
) -> dict[EntityKey, ResolvedEntityMeta]:
    """Resolve entity metadata from a sequence of ``EntityKey`` refs.

    Returns a dict mapping each ``EntityKey`` to its resolved metadata,
    skipping entries whose content type or object cannot be resolved.
    """
    # Group by content_type_id, deduplicating object_ids
    by_ct: dict[int, set[int]] = defaultdict(set)
    for key in entity_keys:
        by_ct[key.content_type_id].add(key.object_id)

    resolved: dict[EntityKey, ResolvedEntityMeta] = {}
    for ct_id, obj_ids in by_ct.items():
        ct = ContentType.objects.get_for_id(ct_id)
        model_class = ct.model_class()
        if not model_class:
            continue
        entities = model_class._default_manager.in_bulk(list(obj_ids))
        type_label = str(model_class._meta.verbose_name).title()
        for obj_id, entity in entities.items():
            href = resolve_entity_href(model_class, entity)
            if href is None:
                continue
            name = getattr(entity, "name", None)
            resolved[EntityKey(ct_id, obj_id)] = {
                "href": href,
                "name": name if isinstance(name, str) else str(entity),
                "type_label": type_label,
            }
    return resolved
