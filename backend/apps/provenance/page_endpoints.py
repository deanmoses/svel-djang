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

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.responses import Status

from apps.core.entity_types import get_linkable_model
from apps.core.types import EntityKey

from .entity_resolution import batch_resolve_entities
from .evidence import build_cited_changesets
from .helpers import active_claims, build_sources, claims_prefetch
from .history import build_edit_history
from .schemas import (
    ChangeSetBaseSchema,
    ChangeSetSchema,
    CitationLinkSchema,
    ClaimSchema,
    FieldChangeSchema,
    RetractionSchema,
)


class ChangeSetWithEntitySchema(ChangeSetBaseSchema):
    """Adds the entity-link fields shown on the changes page list/detail."""

    is_ingest: bool = False
    source_name: str | None = None
    entity_href: str
    entity_name: str
    entity_type_label: str


class ChangeSetSummarySchema(ChangeSetWithEntitySchema):
    changes_count: int
    retractions_count: int


class ChangeSetListSchema(Schema):
    items: list[ChangeSetSummarySchema]
    next_cursor: str | None = None


class ChangeSetDetailSchema(ChangeSetWithEntitySchema):
    changes: list[FieldChangeSchema]
    retractions: list[RetractionSchema]


class CitedChangeSetCitationSchema(Schema):
    source_name: str
    source_type: str
    author: str
    year: int | None = None
    locator: str
    links: list[CitationLinkSchema] = []


class CitedChangeSetSchema(ChangeSetBaseSchema):
    fields: list[str]
    citations: list[CitedChangeSetCitationSchema]


class SourcesPageSchema(Schema):
    """Page model for the per-entity Sources subroute.

    Bundles the sources list (grouped claims) with the cited-edit evidence
    so the page renders from a single fetch.
    """

    sources: list[ClaimSchema]
    evidence: list[CitedChangeSetSchema]


type ErrorPayload = dict[str, str]


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
    "/edit-history/{entity_type}/{path:public_id}/",
    response={200: list[ChangeSetSchema], 404: dict},
)
@decorate_view(cache_control(no_cache=True))
def edit_history_page(
    request: HttpRequest,
    entity_type: str,
    public_id: str,
) -> list[ChangeSetSchema] | Status[ErrorPayload]:
    """Return changeset-grouped edit history for any catalog entity.

    Accepts soft-deleted entities so the provenance record remains
    inspectable after deletion — matches ``sources_page``.

    The ``:path`` URL converter accepts multi-segment ids without affecting
    single-segment models (their ``public_id`` simply has no slashes).
    """
    _ = request
    try:
        model_class = get_linkable_model(entity_type)
    except ValueError:
        return Status(404, {"detail": f"Unknown entity type: {entity_type}"})
    entity = get_object_or_404(model_class, **{model_class.public_id_field: public_id})
    return build_edit_history(entity)


@pages_router.get(
    "/sources/{entity_type}/{path:public_id}/",
    response={200: SourcesPageSchema, 404: dict},
)
@decorate_view(cache_control(no_cache=True))
def sources_page(
    request: HttpRequest,
    entity_type: str,
    public_id: str,
) -> SourcesPageSchema | Status[ErrorPayload]:
    """Return the sources page model: grouped claims + cited evidence.

    Accepts soft-deleted entities so the provenance record remains
    inspectable after deletion — matches ``edit_history_page``.
    """
    try:
        model_class = get_linkable_model(entity_type)
    except ValueError:
        return Status(404, {"detail": f"Unknown entity type: {entity_type}"})

    _ = request
    entity = get_object_or_404(
        model_class._default_manager.prefetch_related(claims_prefetch()),
        **{model_class.public_id_field: public_id},
    )
    claims = active_claims(entity)
    sources = build_sources(claims)
    evidence = [
        CitedChangeSetSchema(
            id=row["id"],
            user_display=row["user_display"],
            note=row["note"],
            created_at=row["created_at"],
            fields=row["fields"],
            citations=[
                CitedChangeSetCitationSchema(
                    source_name=c["source_name"],
                    source_type=c["source_type"],
                    author=c["author"],
                    year=c["year"],
                    locator=c["locator"],
                    links=[CitationLinkSchema(**link) for link in c["links"]],
                )
                for c in row["citations"]
            ],
        )
        for row in build_cited_changesets(claims)
    ]
    return SourcesPageSchema(
        sources=sources,
        evidence=evidence,
    )


@pages_router.get("/changesets/", response=ChangeSetListSchema)
@decorate_view(cache_control(no_cache=True))
def list_changes(
    request: HttpRequest,
    entity_type: str = "",
    after: str = "",
    before: str = "",
    include_ingest: bool = False,
    cursor: str = "",
    limit: int = 50,
) -> ChangeSetListSchema:
    """Global feed of edits across all entities."""
    from django.db.models import Prefetch

    from .models import ChangeSet, Claim
    from .pagination import cursor_paginate

    _ = request
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
            model_class = get_linkable_model(entity_type)
        except ValueError:
            return ChangeSetListSchema(items=[], next_cursor=None)
        ct = ContentType.objects.get_for_model(model_class)
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
    entity_keys: list[EntityKey] = []
    cs_entity_map: dict[int, EntityKey] = {}
    for cs in changesets:
        claims = cs.claims.all()
        retracted = cs.retracted_claims.all()
        first = next(iter(claims), None) or next(iter(retracted), None)
        if first:
            assert cs.pk is not None
            key = EntityKey(first.content_type_id, first.object_id)
            cs_entity_map[cs.pk] = key
            entity_keys.append(key)

    resolved = batch_resolve_entities(entity_keys)

    items: list[ChangeSetSummarySchema] = []
    for cs in changesets:
        assert cs.pk is not None
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
            ChangeSetSummarySchema(
                id=cs.pk,
                user_display=cs.user.username if cs.user else None,
                is_ingest=cs.ingest_run_id is not None,
                source_name=cs.ingest_run.source.name if cs.ingest_run_id else None,
                note=cs.note,
                created_at=cs.created_at.isoformat(),
                changes_count=len(claims) + retractions_count,
                retractions_count=retractions_count,
                entity_href=meta["href"],
                entity_name=meta["name"],
                entity_type_label=meta["type_label"],
            )
        )

    return ChangeSetListSchema(items=items, next_cursor=next_cursor)


@pages_router.get(
    "/changesets/{changeset_id}/",
    response={200: ChangeSetDetailSchema, 404: dict},
)
def change_detail(
    request: HttpRequest,
    changeset_id: int,
) -> ChangeSetDetailSchema | Status[ErrorPayload]:
    """Detail view for a single changeset with full field diffs."""
    from .models import ChangeSet, Claim

    _ = request
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
    entity_key = EntityKey(ct_id, obj_id)
    meta_map = batch_resolve_entities([entity_key])
    meta = meta_map.get(entity_key)
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
    by_key: dict[str, list[Claim]] = defaultdict(list)
    for c in history_claims:
        by_key[c.claim_key].append(c)

    changes: list[FieldChangeSchema] = []
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
            FieldChangeSchema(
                field_name=claim.field_name,
                claim_key=claim.claim_key,
                old_value=old_value,
                new_value=claim.value,
            )
        )

    retractions = [
        RetractionSchema(
            claim_id=c.pk,
            field_name=c.field_name,
            claim_key=c.claim_key,
            old_value=c.value,
        )
        for c in retracted
    ]

    ingest_run = cs.ingest_run
    assert cs.pk is not None
    return ChangeSetDetailSchema(
        id=cs.pk,
        user_display=cs.user.username if cs.user else None,
        is_ingest=ingest_run is not None,
        source_name=ingest_run.source.name if ingest_run is not None else None,
        note=cs.note,
        created_at=cs.created_at.isoformat(),
        entity_href=meta["href"],
        entity_name=meta["name"],
        entity_type_label=meta["type_label"],
        changes=changes,
        retractions=retractions,
    )
