"""API endpoints for the provenance app.

Routers: sources, claims, changesets, pages, review, citation-instances.
Auto-discovered via the ``routers`` list convention in config/api.py.
"""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router
from ninja.decorators import decorate_view
from ninja.errors import HttpError
from ninja.responses import Status
from ninja.security import django_auth

from apps.citation.models import CitationSource
from apps.core.api_helpers import authed_user
from apps.core.schemas import ErrorDetailSchema

from .models import CitationInstance, ClaimControlledModel, Source
from .page_endpoints import pages_router
from .schemas import (
    CitationInstanceBatchSchema,
    CitationInstanceCreateSchema,
    CitationInstanceSchema,
    CitationLinkSchema,
    CitationSourceSchema,
    RevertNoteSchema,
    ReviewClaimSchema,
    UndoChangeSetSchema,
    UndoResultSchema,
)

sources_router = Router(tags=["sources", "private"])
review_router = Router(tags=["review", "private"])


@sources_router.get("/", response=list[CitationSourceSchema])
@decorate_view(cache_control(no_cache=True))
def list_sources(request: HttpRequest) -> list[Source]:
    return list(Source.objects.all())


def _build_claim_review_context(claim) -> tuple[list[dict], str | None]:
    """Build review links and title slug for a group claim flagged for review.

    Returns (links, title_slug).
    """
    from apps.catalog.models import Title

    links: list[dict] = []
    value = str(claim.value) if claim.value else ""

    # The claim value is a title's public_id (slug, for Title) — look it up.
    try:
        title = Title.objects.get(**{Title.public_id_field: value})
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
        links.append({"label": rt.name, "url": rt.get_absolute_url()})
        links.append(
            {
                "label": f"OPDB {rt.opdb_id}",
                "url": f"https://opdb.org/machines/{rt.opdb_id}",
            }
        )

    return links, title.public_id


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
                # ``model_class()`` is ``type[Model] | None`` and ``.entity_type``
                # belongs to the deferred LinkableModel contract tracked in
                # docs/plans/types/MypyFixing.md. Cleared when that lands.
                "subject_type": claim.content_type.model_class().entity_type,  # type: ignore[union-attr]
                "subject_name": subject_name,
                "subject_slug": subject_slug,
                "title_slug": title_slug,
                "review_links": review_links,
            }
        )
    return results


# ── Claim and ChangeSet mutations (revert, undo) ───────────────────


claims_router = Router(tags=["claims", "private"])
changesets_router = Router(tags=["changesets", "private"])


@claims_router.post(
    "/{claim_id}/revert/",
    auth=django_auth,
    response={
        204: None,
        403: ErrorDetailSchema,
        404: ErrorDetailSchema,
        422: ErrorDetailSchema,
    },
)
def revert_claim(
    request: HttpRequest, claim_id: int, data: RevertNoteSchema
) -> Status[None] | Status[ErrorDetailSchema]:
    """Revert (deactivate) a single user claim and re-resolve its entity.

    The claim carries its own entity reference (``content_type`` +
    ``object_id``), so we resolve the entity from the claim rather than
    requiring it in the URL.
    """
    from django.core.exceptions import ObjectDoesNotExist

    from .models import Claim
    from .revert import RevertError, execute_revert

    user = authed_user(request)
    try:
        claim = Claim.objects.select_related("content_type").get(pk=claim_id)
    except Claim.DoesNotExist:
        return Status(404, ErrorDetailSchema(detail="Claim not found."))

    try:
        entity = claim.content_type.get_object_for_this_type(pk=claim.object_id)
    except ObjectDoesNotExist:
        return Status(
            404, ErrorDetailSchema(detail="Entity for this claim no longer exists.")
        )

    # By construction, any entity carrying a Claim is a ClaimControlledModel.
    assert isinstance(entity, ClaimControlledModel)
    try:
        execute_revert(entity, claim_id=claim_id, user=user, note=data.note)
    except RevertError as exc:
        return Status(exc.status_code, ErrorDetailSchema(detail=str(exc)))
    return Status(204, None)


@changesets_router.post(
    "/{changeset_id}/undo/",
    auth=django_auth,
    response={
        200: UndoResultSchema,
        403: ErrorDetailSchema,
        404: ErrorDetailSchema,
        422: ErrorDetailSchema,
    },
)
def undo_changeset(
    request: HttpRequest, changeset_id: int, data: UndoChangeSetSchema
) -> UndoResultSchema | Status[ErrorDetailSchema]:
    """Atomically invert a DELETE ChangeSet (restore a soft-deleted tree).

    This powers the post-delete Undo toast. Scoped to delete ChangeSets
    authored by the caller; other scenarios use per-claim revert.
    """
    from .models import ChangeSet
    from .revert import UndoError, execute_undo_changeset

    user = authed_user(request)
    try:
        changeset = ChangeSet.objects.get(pk=changeset_id)
    except ChangeSet.DoesNotExist:
        return Status(404, ErrorDetailSchema(detail="ChangeSet not found."))

    try:
        new_cs = execute_undo_changeset(changeset, user=user, note=data.note)
    except UndoError as exc:
        return Status(exc.status_code, ErrorDetailSchema(detail=str(exc)))
    return UndoResultSchema(changeset_id=new_cs.pk)


citation_instances_router = Router(tags=["citation-instances", "private"])


@citation_instances_router.get(
    "/",
    response=list[CitationInstanceSchema],
    auth=django_auth,
)
def list_citation_instances(
    request: HttpRequest, source: int | None = None, claim: int | None = None
) -> list[CitationInstanceSchema]:
    """List Citation Instances, filtered by source and/or claim."""
    if source is None and claim is None:
        raise HttpError(422, "Provide ?source= or ?claim= filter.")

    qs = CitationInstance.objects.select_related("citation_source")
    if source is not None:
        qs = qs.filter(citation_source_id=source)
    if claim is not None:
        qs = qs.filter(claim_id=claim)
    qs = qs.order_by("-created_at")

    return [
        CitationInstanceSchema(
            id=ci.pk,
            citation_source_id=ci.citation_source_id,
            citation_source_name=ci.citation_source.name,
            claim_id=ci.claim_id,
            locator=ci.locator,
            created_at=ci.created_at.isoformat(),
        )
        for ci in qs
    ]


@citation_instances_router.get(
    "/batch/",
    response={200: list[CitationInstanceBatchSchema], 422: ErrorDetailSchema},
)
def batch_citation_instances(
    request: HttpRequest, ids: str = ""
) -> list[CitationInstanceBatchSchema]:
    """Return citation instances by ID for tooltip rendering."""
    if not ids.strip():
        return []

    try:
        id_list = [int(x) for x in ids.split(",") if x.strip()]
    except ValueError as err:
        raise HttpError(422, "ids must be comma-separated integers.") from err

    if len(id_list) > 50:
        raise HttpError(422, "Maximum 50 IDs per request.")

    qs = (
        CitationInstance.objects.filter(pk__in=id_list)
        .select_related("citation_source")
        .prefetch_related("citation_source__links")
    )

    return [
        CitationInstanceBatchSchema(
            id=ci.pk,
            source_name=ci.citation_source.name,
            source_type=ci.citation_source.source_type,
            author=ci.citation_source.author,
            year=ci.citation_source.year,
            locator=ci.locator,
            links=[
                CitationLinkSchema(url=link.url, label=link.label)
                for link in ci.citation_source.links.all()
            ],
        )
        for ci in qs
    ]


@citation_instances_router.post(
    "/",
    response={201: CitationInstanceSchema, 422: ErrorDetailSchema},
    auth=django_auth,
)
def create_citation_instance(
    request: HttpRequest, data: CitationInstanceCreateSchema
) -> Status[CitationInstanceSchema]:
    """Create a new CitationInstance for use in ``[[cite:N]]`` markers."""
    source = get_object_or_404(CitationSource, pk=data.citation_source_id)

    instance = CitationInstance(
        citation_source_id=data.citation_source_id,
        locator=data.locator,
    )
    try:
        instance.full_clean()
        instance.save()
    except ValidationError as exc:
        raise HttpError(422, str(exc)) from exc
    except IntegrityError as exc:
        raise HttpError(422, str(exc)) from exc

    return Status(
        201,
        CitationInstanceSchema(
            id=instance.pk,
            citation_source_id=instance.citation_source_id,
            citation_source_name=source.name,
            claim_id=None,
            locator=instance.locator,
            created_at=instance.created_at.isoformat(),
        ),
    )


routers = [
    ("/sources/", sources_router),
    ("/claims/", claims_router),
    ("/changesets/", changesets_router),
    ("/pages/", pages_router),
    ("/review/", review_router),
    ("/citation-instances/", citation_instances_router),
]
