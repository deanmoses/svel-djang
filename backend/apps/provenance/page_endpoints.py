"""Page-oriented endpoints for provenance.

These endpoints live under /api/pages/ and are tagged "private" so they
stay out of the public API docs.  They return page-model responses shaped
for specific SvelteKit routes.

The ``pages_router`` is imported by api.py and included in its ``routers``
list for autodiscovery.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.shortcuts import get_object_or_404
from apps.core.entity_types import resolve_entity_type
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.responses import Status

from .evidence import build_cited_changesets
from .helpers import claims_prefetch
from .schemas import FieldChangeSchema, RetractionSchema


class ChangeSetSummarySchema(Schema):
    id: int
    user_display: Optional[str] = None
    is_ingest: bool = False
    source_name: Optional[str] = None
    note: str
    created_at: str
    changes_count: int
    retractions_count: int
    entity_href: str
    entity_name: str
    entity_type_label: str


class ChangesListSchema(Schema):
    items: list[ChangeSetSummarySchema]
    next_cursor: Optional[str] = None


class ChangeSetDetailSchema(Schema):
    id: int
    user_display: Optional[str] = None
    is_ingest: bool = False
    source_name: Optional[str] = None
    note: str
    created_at: str
    entity_href: str
    entity_name: str
    entity_type_label: str
    changes: list[FieldChangeSchema]
    retractions: list[RetractionSchema]


class EvidenceLinkSchema(Schema):
    url: str
    label: str


class CitedChangeSetCitationSchema(Schema):
    source_name: str
    source_type: str
    author: str
    year: Optional[int] = None
    locator: str
    links: list[EvidenceLinkSchema] = []


class CitedChangeSetSchema(Schema):
    id: int
    user_display: Optional[str] = None
    note: str
    created_at: str
    fields: list[str]
    citations: list[CitedChangeSetCitationSchema]


def _parse_aware_datetime(value: str) -> datetime | None:
    """Parse an ISO datetime string, ensuring timezone awareness."""
    from django.utils import timezone as tz

    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = tz.make_aware(dt)
    return dt


pages_router = Router(tags=["private"])


@pages_router.get(
    "/evidence/{entity_type}/{slug}/",
    response={200: list[CitedChangeSetSchema], 404: dict},
)
def cited_edit_evidence(request, entity_type: str, slug: str):
    """Return active cited user edits for the requested entity."""
    model_name = resolve_entity_type(entity_type)
    try:
        ct = ContentType.objects.get(app_label="catalog", model=model_name)
    except ContentType.DoesNotExist:
        return Status(404, {"detail": "Unknown entity type."})

    model_class = ct.model_class()
    entity = get_object_or_404(
        model_class.objects.active().prefetch_related(claims_prefetch()), slug=slug
    )
    return build_cited_changesets(getattr(entity, "active_claims", []))


@pages_router.get("/changes/", response=ChangesListSchema)
@decorate_view(cache_control(no_cache=True))
def list_changes(
    request,
    entity_type: str = "",
    after: str = "",
    before: str = "",
    include_ingest: bool = False,
    cursor: str = "",
    limit: int = 50,
):
    """Global feed of edits across all entities."""
    from django.db.models import Prefetch

    from .entity_resolution import batch_resolve_entities
    from .models import ChangeSet, Claim
    from .pagination import cursor_paginate

    limit = max(1, min(limit, 100))

    qs = ChangeSet.objects.select_related(
        "user", "ingest_run__source"
    ).prefetch_related(
        Prefetch(
            "claims",
            queryset=Claim.objects.only(
                "content_type_id",
                "object_id",
                "field_name",
            ),
        ),
        Prefetch(
            "retracted_claims",
            queryset=Claim.objects.only(
                "content_type_id",
                "object_id",
            ),
        ),
    )

    if not include_ingest:
        qs = qs.filter(user__isnull=False)

    if entity_type:
        try:
            ct = ContentType.objects.get(
                app_label="catalog", model=resolve_entity_type(entity_type)
            )
        except ContentType.DoesNotExist:
            return {"items": [], "next_cursor": None}
        qs = qs.filter(
            Q(claims__content_type_id=ct.pk)
            | Q(retracted_claims__content_type_id=ct.pk)
        ).distinct()

    if after:
        after_dt = _parse_aware_datetime(after)
        if after_dt:
            qs = qs.filter(created_at__gte=after_dt)
    if before:
        before_dt = _parse_aware_datetime(before)
        if before_dt:
            qs = qs.filter(created_at__lte=before_dt)

    changesets, next_cursor = cursor_paginate(qs, cursor, limit)

    # Batch-resolve entity metadata.
    entity_refs: list[dict] = []
    cs_entity_map: dict[int, tuple[int, int]] = {}
    for cs in changesets:
        claims = cs.claims.all()
        retracted = cs.retracted_claims.all()
        first = next(iter(claims), None) or next(iter(retracted), None)
        if first:
            key = (first.content_type_id, first.object_id)
            cs_entity_map[cs.pk] = key
            entity_refs.append({"content_type_id": key[0], "object_id": key[1]})

    resolved = batch_resolve_entities(entity_refs)

    items = []
    for cs in changesets:
        ref = cs_entity_map.get(cs.pk)
        if not ref:
            continue
        meta = resolved.get(ref)
        if not meta:
            continue

        claims = cs.claims.all()
        retracted = cs.retracted_claims.all()
        retractions_count = len(retracted)

        items.append(
            {
                "id": cs.pk,
                "user_display": cs.user.username if cs.user else None,
                "is_ingest": cs.ingest_run_id is not None,
                "source_name": (
                    cs.ingest_run.source.name if cs.ingest_run_id else None
                ),
                "note": cs.note,
                "created_at": cs.created_at.isoformat(),
                "changes_count": len(claims) + retractions_count,
                "retractions_count": retractions_count,
                "entity_href": meta["href"],
                "entity_name": meta["name"],
                "entity_type_label": meta["type_label"],
            }
        )

    return {"items": items, "next_cursor": next_cursor}


@pages_router.get(
    "/changes/{changeset_id}/",
    response={200: ChangeSetDetailSchema, 404: dict},
)
def change_detail(request, changeset_id: int):
    """Detail view for a single changeset with full field diffs."""
    from .entity_resolution import batch_resolve_entities
    from .models import ChangeSet, Claim

    cs = get_object_or_404(
        ChangeSet.objects.select_related("user", "ingest_run__source").prefetch_related(
            "claims", "retracted_claims"
        ),
        pk=changeset_id,
    )

    claims = list(cs.claims.all())
    retracted = list(cs.retracted_claims.all())
    first = next(iter(claims), None) or next(iter(retracted), None)
    if not first:
        return Status(404, {"detail": "Changeset has no claims."})

    ct_id = first.content_type_id
    obj_id = first.object_id

    # Resolve entity metadata.
    meta_map = batch_resolve_entities([{"content_type_id": ct_id, "object_id": obj_id}])
    meta = meta_map.get((ct_id, obj_id))
    if not meta:
        return Status(404, {"detail": "Entity no longer exists."})

    # Build diffs: fetch all claims for this entity with matching claim_keys.
    claim_keys = {c.claim_key for c in claims}
    if claim_keys:
        history_claims = list(
            Claim.objects.filter(
                content_type_id=ct_id,
                object_id=obj_id,
                claim_key__in=claim_keys,
            ).order_by("claim_key", "-created_at", "-pk")
        )
    else:
        history_claims = []

    # Group by claim_key for O(1) lookup.
    by_key: dict[str, list] = defaultdict(list)
    for c in history_claims:
        by_key[c.claim_key].append(c)

    changes = []
    for claim in claims:
        old_value = None
        chain = by_key.get(claim.claim_key, [])
        for c in chain:
            before_this = c.created_at < claim.created_at or (
                c.created_at == claim.created_at and c.pk < claim.pk
            )
            if before_this:
                old_value = c.value
                break
        changes.append(
            {
                "field_name": claim.field_name,
                "claim_key": claim.claim_key,
                "old_value": old_value,
                "new_value": claim.value,
            }
        )

    retractions = [
        {
            "claim_id": c.pk,
            "field_name": c.field_name,
            "claim_key": c.claim_key,
            "old_value": c.value,
        }
        for c in retracted
    ]

    return {
        "id": cs.pk,
        "user_display": cs.user.username if cs.user else None,
        "is_ingest": cs.ingest_run_id is not None,
        "source_name": cs.ingest_run.source.name if cs.ingest_run_id else None,
        "note": cs.note,
        "created_at": cs.created_at.isoformat(),
        "entity_href": meta["href"],
        "entity_name": meta["name"],
        "entity_type_label": meta["type_label"],
        "changes": changes,
        "retractions": retractions,
    }
