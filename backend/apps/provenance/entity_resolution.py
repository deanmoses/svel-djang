"""Shared helpers for resolving catalog entity metadata from content-type refs.

Used by the user-profile endpoint and the recent-changes feed.
"""

from __future__ import annotations

from collections import defaultdict

from django.contrib.contenttypes.models import ContentType


def resolve_entity_href(model_class, entity) -> str | None:
    """Build the frontend URL for a catalog entity from its link_url_pattern."""
    pattern = getattr(model_class, "link_url_pattern", None)
    if not pattern or not hasattr(entity, "slug"):
        return None
    return pattern.format(slug=entity.slug)


def batch_resolve_entities(entity_rows):
    """Resolve entity metadata from (content_type_id, object_id) pairs.

    Returns a dict mapping (content_type_id, object_id) to
    {"href": str, "name": str, "type_label": str}, skipping unresolvable
    entities.
    """
    # Group by content_type_id, deduplicating object_ids
    by_ct: dict[int, set[int]] = defaultdict(set)
    for row in entity_rows:
        by_ct[row["content_type_id"]].add(row["object_id"])

    resolved: dict[tuple[int, int], dict] = {}
    for ct_id, obj_ids in by_ct.items():
        ct = ContentType.objects.get_for_id(ct_id)
        model_class = ct.model_class()
        if not model_class:
            continue
        entities = model_class.objects.in_bulk(list(obj_ids))
        type_label = str(model_class._meta.verbose_name).title()
        for obj_id, entity in entities.items():
            href = resolve_entity_href(model_class, entity)
            if href is None:
                continue
            resolved[(ct_id, obj_id)] = {
                "href": href,
                "name": getattr(entity, "name", str(entity)),
                "type_label": type_label,
            }
    return resolved
