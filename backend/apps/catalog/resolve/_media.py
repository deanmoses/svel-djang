"""Resolution logic for media_attachment claims → EntityMedia rows."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import cast

from django.contrib.contenttypes.models import ContentType

from apps.core.models import MediaSupported
from apps.media.models import EntityMedia, MediaAsset
from apps.provenance.models import Claim
from apps.provenance.typing import HasEffectivePriority

from ._helpers import _annotate_priority

logger = logging.getLogger(__name__)


def resolve_media_attachments(
    *,
    content_type_id: int | None = None,
    entity_ids: set[int] | None = None,
) -> None:
    """Bulk-resolve ``media_attachment`` claims into :class:`EntityMedia` rows.

    Both parameters are optional.  Passing neither resolves all media across
    all entity types.  Passing both scopes to a single entity.
    """
    # -- Fetch active claims, pick winners ----------------------------------

    claims_qs = _annotate_priority(Claim.objects.filter(field_name="media_attachment"))
    if content_type_id is not None:
        claims_qs = claims_qs.filter(content_type_id=content_type_id)
    if entity_ids is not None:
        claims_qs = claims_qs.filter(object_id__in=entity_ids)
    claims = claims_qs.order_by(
        "content_type_id",
        "object_id",
        "claim_key",
        "-effective_priority",
        "-created_at",
    )

    # Winner per (content_type_id, object_id, claim_key).
    # Keep priority + created_at for primary enforcement.
    winners_by_entity: dict[tuple[int, int], list[Claim]] = {}
    seen: set[tuple[int, int, str]] = set()
    for claim in claims:
        key = (claim.content_type_id, claim.object_id, claim.claim_key)
        if key not in seen:
            seen.add(key)
            entity_key = (claim.content_type_id, claim.object_id)
            winners_by_entity.setdefault(entity_key, []).append(claim)

    # -- Validate winners & build desired state -----------------------------

    valid_asset_pks = set(MediaAsset.objects.values_list("pk", flat=True))

    # Cache content_type → (model_class, is_media_supported, categories)
    _ct_cache: dict[int, tuple[type | None, bool, list[str]]] = {}

    def _ct_info(ct_id: int) -> tuple[type | None, bool, list[str]]:
        if ct_id not in _ct_cache:
            ct = ContentType.objects.get_for_id(ct_id)
            model_class = ct.model_class()
            is_supported = model_class is not None and issubclass(
                model_class, MediaSupported
            )
            categories = (
                cast(list[str], getattr(model_class, "MEDIA_CATEGORIES", []))
                if is_supported
                else []
            )
            _ct_cache[ct_id] = (model_class, is_supported, categories)
        return _ct_cache[ct_id]

    # Desired: {(ct_id, obj_id): {asset_pk: (category, is_primary)}}
    # Also track claim priority/created_at for primary enforcement.
    desired_by_entity: dict[tuple[int, int], dict[int, tuple[str | None, bool]]] = {}
    # For primary enforcement: {(ct_id, obj_id, category): [(asset_pk, priority, created_at)]}
    primary_candidates: dict[
        tuple[int, int, str | None], list[tuple[int, int, datetime]]
    ] = defaultdict(list)
    # For auto-promotion: all attachments per (entity, category) with timestamps
    all_attachments: dict[tuple[int, int, str | None], list[tuple[int, datetime]]] = (
        defaultdict(list)
    )

    for entity_key, claims_list in winners_by_entity.items():
        ct_id, obj_id = entity_key
        _model_class, is_supported, allowed_cats = _ct_info(ct_id)

        if not is_supported:
            logger.warning(
                "media_attachment claim on non-MediaSupported entity "
                "(content_type_id=%s, object_id=%s) — skipping",
                ct_id,
                obj_id,
            )
            continue

        desired: dict[int, tuple[str | None, bool]] = {}
        for claim in claims_list:
            val = claim.value
            if not val.get("exists", True):
                continue

            asset_pk = val.get("media_asset")
            if asset_pk not in valid_asset_pks:
                logger.warning(
                    "Unresolved media_asset pk %r in claim "
                    "(content_type_id=%s, object_id=%s)",
                    asset_pk,
                    ct_id,
                    obj_id,
                )
                continue

            category = val.get("category")
            if category is not None and (
                not allowed_cats or category not in allowed_cats
            ):
                logger.warning(
                    "Invalid category %r in media_attachment claim "
                    "(content_type_id=%s, object_id=%s) — skipping",
                    category,
                    ct_id,
                    obj_id,
                )
                continue

            is_primary = bool(val.get("is_primary", False))
            desired[asset_pk] = (category, is_primary)

            all_attachments[(ct_id, obj_id, category)].append(
                (asset_pk, claim.created_at)
            )
            if is_primary:
                effective_priority = cast(HasEffectivePriority, claim)
                primary_candidates[(ct_id, obj_id, category)].append(
                    (asset_pk, effective_priority.effective_priority, claim.created_at)
                )

        desired_by_entity[entity_key] = desired

    # -- Primary enforcement ------------------------------------------------
    # Within each (entity, category) group, at most one primary.
    # Highest priority wins; ties broken by most recent created_at.

    for group_key, candidates in primary_candidates.items():
        if len(candidates) <= 1:
            continue
        ct_id, obj_id, category = group_key
        entity_key = (ct_id, obj_id)
        if entity_key not in desired_by_entity:
            continue
        desired = desired_by_entity[entity_key]

        # Sort: highest priority first, then most recent
        candidates.sort(key=lambda c: (c[1], c[2]), reverse=True)
        winner_asset_pk = candidates[0][0]

        for asset_pk, _prio, _ts in candidates:
            if asset_pk != winner_asset_pk:
                old_cat, _old_primary = desired[asset_pk]
                desired[asset_pk] = (old_cat, False)

    # -- Auto-promotion ----------------------------------------------------
    # If no attachment in a (entity, category) group is primary, promote the
    # oldest (first uploaded) so there's always a primary per category.

    for group_key, attachments in all_attachments.items():
        ct_id, obj_id, category = group_key
        entity_key = (ct_id, obj_id)
        if entity_key not in desired_by_entity:
            continue
        desired = desired_by_entity[entity_key]

        has_primary = any(
            primary for asset_pk, (cat, primary) in desired.items() if cat == category
        )
        if has_primary:
            continue

        # Oldest first
        attachments.sort(key=lambda a: a[1])
        winner_asset_pk = attachments[0][0]
        old_cat, _ = desired[winner_asset_pk]
        desired[winner_asset_pk] = (old_cat, True)

    # -- Fetch existing EntityMedia rows ------------------------------------

    existing_qs = EntityMedia.objects.all()
    if content_type_id is not None:
        existing_qs = existing_qs.filter(content_type_id=content_type_id)
    if entity_ids is not None:
        existing_qs = existing_qs.filter(object_id__in=entity_ids)

    # {(ct_id, obj_id): {asset_pk: (row_pk, category, is_primary)}}
    existing_by_entity: dict[
        tuple[int, int], dict[int, tuple[int, str | None, bool]]
    ] = {}
    for row in existing_qs.values_list(
        "pk", "content_type_id", "object_id", "asset_id", "category", "is_primary"
    ):
        pk, ct_id, obj_id, asset_id, category, is_primary = row
        existing_by_entity.setdefault((ct_id, obj_id), {})[asset_id] = (
            pk,
            category,
            is_primary,
        )

    # -- Three-way diff -----------------------------------------------------

    to_create: list[EntityMedia] = []
    to_delete_pks: list[int] = []
    to_update: list[tuple[int, str | None, bool]] = []  # (pk, category, is_primary)

    # Process entities that have desired state (from claims).
    all_entity_keys = set(desired_by_entity) | set(existing_by_entity)

    for entity_key in all_entity_keys:
        desired = desired_by_entity.get(entity_key, {})
        existing = existing_by_entity.get(entity_key, {})
        ct_id, obj_id = entity_key

        for asset_pk, (cat, primary) in desired.items():
            if asset_pk not in existing:
                to_create.append(
                    EntityMedia(
                        content_type_id=ct_id,
                        object_id=obj_id,
                        asset_id=asset_pk,
                        category=cat,
                        is_primary=primary,
                    )
                )
            else:
                row_pk, existing_cat, existing_primary = existing[asset_pk]
                if existing_cat != cat or existing_primary != primary:
                    to_update.append((row_pk, cat, primary))

        for asset_pk, (row_pk, _cat, _primary) in existing.items():
            if asset_pk not in desired:
                to_delete_pks.append(row_pk)

    # -- Apply --------------------------------------------------------------

    if to_delete_pks:
        EntityMedia.objects.filter(pk__in=to_delete_pks).delete()
    if to_create:
        EntityMedia.objects.bulk_create(to_create, batch_size=2000)
    if to_update:
        rows = EntityMedia.objects.in_bulk([pk for pk, _, _ in to_update])
        for pk, cat, primary in to_update:
            row = rows[pk]
            row.category = cat
            row.is_primary = primary
        EntityMedia.objects.bulk_update(
            list(rows.values()), ["category", "is_primary"], batch_size=2000
        )
