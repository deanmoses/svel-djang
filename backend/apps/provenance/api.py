"""API endpoints for the provenance app.

Routers: sources, review, recent_changes, edit_history.
Wired into the main NinjaAPI instance in config/api.py.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.responses import Status


class FieldChangeSchema(Schema):
    """A single field change within a ChangeSet (old → new)."""

    field_name: str
    claim_key: str
    old_value: Optional[object] = None
    new_value: object


class ChangeSetSchema(Schema):
    """A grouped edit session with per-field diffs."""

    id: int
    user_display: Optional[str] = None
    note: str
    created_at: str
    changes: list[FieldChangeSchema]


class SourceSchema(Schema):
    name: str
    slug: str
    source_type: str
    priority: int
    url: str
    description: str


class ReviewLinkSchema(Schema):
    label: str
    url: str


class ReviewClaimSchema(Schema):
    id: int
    source_name: str
    field_name: str
    value: object
    needs_review_notes: str
    created_at: str
    # Context about the subject (the entity this claim targets).
    subject_type: str  # e.g. "machinemodel"
    subject_name: str
    subject_slug: Optional[str] = None
    # Title that this claim created (for group claims).
    title_slug: Optional[str] = None
    review_links: list[ReviewLinkSchema] = []


sources_router = Router(tags=["sources", "private"])
review_router = Router(tags=["review", "private"])


@sources_router.get("/", response=list[SourceSchema])
@decorate_view(cache_control(no_cache=True))
def list_sources(request):
    from .models import Source

    return list(Source.objects.all())


def _build_claim_review_context(claim) -> tuple[list[dict], str | None]:
    """Build review links and title slug for a group claim flagged for review.

    Returns (links, title_slug).
    """
    from apps.catalog.models import Title

    links: list[dict] = []
    value = str(claim.value) if claim.value else ""

    # The claim value is a title slug — look it up.
    try:
        title = Title.objects.get(slug=value)
    except Title.DoesNotExist:
        return links, None

    # Related OPDB-backed titles by name match.
    base_name = re.sub(r"\s*\([^)]*\)\s*$", "", title.name).strip()
    related = (
        Title.objects.filter(Q(name__iexact=title.name) | Q(name__iexact=base_name))
        .exclude(pk=title.pk)
        .exclude(opdb_id__isnull=True)
    )
    for rt in related:
        links.append({"label": rt.name, "url": f"/titles/{rt.slug}"})
        links.append(
            {
                "label": f"OPDB {rt.opdb_id}",
                "url": f"https://opdb.org/machines/{rt.opdb_id}",
            }
        )

    return links, title.slug


@review_router.get("/claims/", response=list[ReviewClaimSchema])
@decorate_view(cache_control(no_cache=True))
def list_review_claims(request):
    """Return all active claims flagged for review."""
    from .models import Claim

    claims = (
        Claim.objects.filter(is_active=True, needs_review=True)
        .select_related("source", "content_type")
        .order_by("-created_at")
    )

    results = []
    for claim in claims:
        subject = claim.subject
        subject_name = str(subject) if subject else "Unknown"
        subject_slug = getattr(subject, "slug", None)
        if claim.field_name == "title":
            review_links, title_slug = _build_claim_review_context(claim)
        else:
            review_links, title_slug = [], None
        results.append(
            {
                "id": claim.pk,
                "source_name": claim.source.name if claim.source else "User",
                "field_name": claim.field_name,
                "value": claim.value,
                "needs_review_notes": claim.needs_review_notes,
                "created_at": claim.created_at.isoformat(),
                "subject_type": claim.content_type.model,
                "subject_name": subject_name,
                "subject_slug": subject_slug,
                "title_slug": title_slug,
                "review_links": review_links,
            }
        )
    return results


# ── Recent Changes ────────────────────────────────────────────────


class RecentChangeSetSchema(Schema):
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


class RecentChangesListSchema(Schema):
    items: list[RecentChangeSetSchema]
    next_cursor: Optional[str] = None


class RetractionSchema(Schema):
    field_name: str
    claim_key: str
    old_value: object


class RecentChangeSetDetailSchema(Schema):
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


recent_changes_router = Router(tags=["recent-changes"])


@recent_changes_router.get("/", response=RecentChangesListSchema)
@decorate_view(cache_control(no_cache=True))
def list_recent_changes(
    request,
    entity_type: str = "",
    after: str = "",
    before: str = "",
    include_ingest: bool = False,
    cursor: str = "",
    limit: int = 50,
):
    """Global feed of recent edits across all entities."""
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
            ct = ContentType.objects.get(app_label="catalog", model=entity_type)
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


@recent_changes_router.get(
    "/{changeset_id}/",
    response={200: RecentChangeSetDetailSchema, 404: dict},
)
def recent_change_detail(request, changeset_id: int):
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


# ── Edit History (generic, per-entity) ───────────────────────────

edit_history_router = Router(tags=["edit-history"])


@edit_history_router.get(
    "/{entity_type}/{slug}/",
    response={200: list[ChangeSetSchema], 404: dict},
)
@decorate_view(cache_control(no_cache=True))
def get_edit_history(request, entity_type: str, slug: str):
    """Return changeset-grouped edit history for any catalog entity."""
    from .history import build_edit_history

    try:
        ct = ContentType.objects.get(app_label="catalog", model=entity_type)
    except ContentType.DoesNotExist:
        return Status(404, {"detail": f"Unknown entity type: {entity_type}"})
    model_class = ct.model_class()
    if not model_class or not hasattr(model_class, "link_url_pattern"):
        return Status(404, {"detail": f"Unknown entity type: {entity_type}"})
    entity = get_object_or_404(model_class, slug=slug)
    return build_edit_history(entity)
