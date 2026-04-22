"""API endpoints for the provenance app.

Routers: sources, claims, changesets, pages, review, citation-instances.
Auto-discovered via the ``routers`` list convention in config/api.py.
"""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError
from ninja.responses import Status
from ninja.security import django_auth

from apps.citation.models import CitationSource

from .models import CitationInstance
from .page_endpoints import pages_router


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
    # Canonical hyphenated CatalogModel.entity_type, e.g. "manufacturer".
    subject_type: str
    subject_name: str
    subject_slug: str | None = None
    # Title that this claim created (for group claims).
    title_slug: str | None = None
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
                "subject_type": claim.content_type.model_class().entity_type,
                "subject_name": subject_name,
                "subject_slug": subject_slug,
                "title_slug": title_slug,
                "review_links": review_links,
            }
        )
    return results


# ── Claim and ChangeSet mutations (revert, undo) ───────────────────


class RevertNoteSchema(Schema):
    note: str


class UndoChangeSetSchema(Schema):
    note: str = ""


claims_router = Router(tags=["claims", "private"])
changesets_router = Router(tags=["changesets", "private"])


@claims_router.post(
    "/{claim_id}/revert/",
    auth=django_auth,
    response={200: dict, 403: dict, 404: dict, 422: dict},
)
def revert_claim(request, claim_id: int, data: RevertNoteSchema):
    """Revert (deactivate) a single user claim and re-resolve its entity.

    The claim carries its own entity reference (``content_type`` +
    ``object_id``), so we resolve the entity from the claim rather than
    requiring it in the URL.
    """
    from django.core.exceptions import ObjectDoesNotExist

    from .models import Claim
    from .revert import RevertError, execute_revert

    try:
        claim = Claim.objects.select_related("content_type").get(pk=claim_id)
    except Claim.DoesNotExist:
        return Status(404, {"detail": "Claim not found."})

    try:
        entity = claim.content_type.get_object_for_this_type(pk=claim.object_id)
    except ObjectDoesNotExist:
        return Status(404, {"detail": "Entity for this claim no longer exists."})

    try:
        execute_revert(entity, claim_id=claim_id, user=request.user, note=data.note)
    except RevertError as exc:
        return Status(exc.status_code, {"detail": str(exc)})
    return {"ok": True}


@changesets_router.post(
    "/{changeset_id}/undo/",
    auth=django_auth,
    response={200: dict, 403: dict, 404: dict, 422: dict},
)
def undo_changeset(request, changeset_id: int, data: UndoChangeSetSchema):
    """Atomically invert a DELETE ChangeSet (restore a soft-deleted tree).

    This powers the post-delete Undo toast. Scoped to delete ChangeSets
    authored by the caller; other scenarios use per-claim revert.
    """
    from .models import ChangeSet
    from .revert import UndoError, execute_undo_changeset

    try:
        changeset = ChangeSet.objects.get(pk=changeset_id)
    except ChangeSet.DoesNotExist:
        return Status(404, {"detail": "ChangeSet not found."})

    try:
        new_cs = execute_undo_changeset(changeset, user=request.user, note=data.note)
    except UndoError as exc:
        return Status(exc.status_code, {"detail": str(exc)})
    return {"ok": True, "changeset_id": new_cs.pk}


citation_instances_router = Router(tags=["citation-instances", "private"])


class CitationInstanceSchema(Schema):
    id: int
    citation_source_id: int
    citation_source_name: str
    claim_id: int | None = None
    locator: str
    created_at: str


@citation_instances_router.get(
    "/",
    response=list[CitationInstanceSchema],
    auth=django_auth,
)
def list_citation_instances(
    request, source: int | None = None, claim: int | None = None
):
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
        {
            "id": ci.pk,
            "citation_source_id": ci.citation_source_id,
            "citation_source_name": ci.citation_source.name,
            "claim_id": ci.claim_id,
            "locator": ci.locator,
            "created_at": ci.created_at.isoformat(),
        }
        for ci in qs
    ]


class BatchCitationLinkOut(Schema):
    url: str
    label: str


class BatchCitationInstanceOut(Schema):
    id: int
    source_name: str
    source_type: str
    author: str
    year: int | None = None
    locator: str
    links: list[BatchCitationLinkOut] = []


@citation_instances_router.get(
    "/batch/",
    response={200: list[BatchCitationInstanceOut], 422: dict},
)
def batch_citation_instances(request, ids: str = ""):
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
        {
            "id": ci.pk,
            "source_name": ci.citation_source.name,
            "source_type": ci.citation_source.source_type,
            "author": ci.citation_source.author,
            "year": ci.citation_source.year,
            "locator": ci.locator,
            "links": [
                {"url": link.url, "label": link.label}
                for link in ci.citation_source.links.all()
            ],
        }
        for ci in qs
    ]


class CitationInstanceCreateIn(Schema):
    citation_source_id: int
    locator: str = ""


@citation_instances_router.post(
    "/",
    response={201: CitationInstanceSchema},
    auth=django_auth,
)
def create_citation_instance(request, data: CitationInstanceCreateIn):
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
        {
            "id": instance.pk,
            "citation_source_id": instance.citation_source_id,
            "citation_source_name": source.name,
            "claim_id": None,
            "locator": instance.locator,
            "created_at": instance.created_at.isoformat(),
        },
    )


routers = [
    ("/sources/", sources_router),
    ("/claims/", claims_router),
    ("/changesets/", changesets_router),
    ("/pages/", pages_router),
    ("/review/", review_router),
    ("/citation-instances/", citation_instances_router),
]
