"""API endpoints for the provenance app.

Routers: sources, review.
Wired into the main NinjaAPI instance in config/api.py.
"""

from __future__ import annotations

import re
from typing import Optional

from django.db.models import Q
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view


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
@decorate_view(cache_control(public=True, max_age=300))
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

    # IPDB link from synthetic group ID.
    if value.startswith("ipdb:"):
        ipdb_id = value.split(":")[1]
        links.append(
            {
                "label": f"IPDB #{ipdb_id}",
                "url": f"https://www.ipdb.org/machine.cgi?id={ipdb_id}",
            }
        )

    # Find the synthetic title to get its slug and name for related-title lookup.
    try:
        title = Title.objects.get(opdb_id=value)
    except Title.DoesNotExist:
        return links, None

    # Related OPDB-backed titles by name match.
    base_name = re.sub(r"\s*\([^)]*\)\s*$", "", title.name).strip()
    related = (
        Title.objects.filter(Q(name__iexact=title.name) | Q(name__iexact=base_name))
        .exclude(pk=title.pk)
        .exclude(opdb_id__startswith="ipdb:")
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
@decorate_view(cache_control(public=True, max_age=60))
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
