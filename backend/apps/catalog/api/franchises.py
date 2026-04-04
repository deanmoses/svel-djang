"""Franchises router — list, detail, and claims endpoints."""

from __future__ import annotations

from typing import Optional

from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404

from apps.core.models import active_status_q
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.security import django_auth

from .edit_claims import execute_claims
from apps.provenance.helpers import build_sources, claims_prefetch

from .helpers import (
    _build_rich_text,
    _extract_image_urls,
)
from .schemas import ClaimPatchSchema, ClaimSchema, RichTextSchema


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TitleRefSchema(Schema):
    name: str
    slug: str
    abbreviations: list[str] = []
    machine_count: int = 0
    manufacturer_name: Optional[str] = None  # display-only, no paired slug
    year: Optional[int] = None
    thumbnail_url: Optional[str] = None


class FranchiseListSchema(Schema):
    name: str
    slug: str
    title_count: int = 0


class FranchiseDetailSchema(Schema):
    name: str
    slug: str
    description: RichTextSchema = RichTextSchema()
    titles: list[TitleRefSchema]
    sources: list[ClaimSchema] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_title_list(title) -> dict:
    thumbnail_url = None
    manufacturer_name = None
    year = None
    machines = list(title.machine_models.all())
    if machines:
        thumbnail_url, _ = _extract_image_urls(machines[0].extra_data or {})
        first = machines[0]
        manufacturer_name = (
            first.corporate_entity.manufacturer.name
            if first.corporate_entity and first.corporate_entity.manufacturer
            else None
        )
        year = first.year
    return {
        "name": title.name,
        "slug": title.slug,
        "abbreviations": [a.value for a in title.abbreviations.all()],
        "machine_count": title.machine_count,
        "manufacturer_name": manufacturer_name,
        "year": year,
        "thumbnail_url": thumbnail_url,
    }


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

franchises_router = Router(tags=["franchises"])


@franchises_router.get("/all/", response=list[FranchiseListSchema])
@decorate_view(cache_control(no_cache=True))
def list_all_franchises(request):
    """Return every franchise with title count (no pagination)."""
    from ..models import Franchise

    qs = (
        Franchise.objects.active()
        .annotate(title_count=Count("titles", filter=active_status_q("titles")))
        .order_by("name")
    )
    return [
        {
            "name": f.name,
            "slug": f.slug,
            "title_count": f.title_count,
        }
        for f in qs
    ]


def _franchise_titles_qs():
    from ..models import MachineModel, Title

    return (
        Title.objects.active()
        .annotate(
            machine_count=Count(
                "machine_models",
                filter=Q(machine_models__variant_of__isnull=True)
                & active_status_q("machine_models"),
            )
        )
        .prefetch_related(
            "abbreviations",
            Prefetch(
                "machine_models",
                queryset=MachineModel.objects.active()
                .filter(variant_of__isnull=True)
                .select_related("corporate_entity__manufacturer")
                .order_by("year", "name"),
            ),
        )
    )


@franchises_router.get("/{slug}", response=FranchiseDetailSchema)
@decorate_view(cache_control(no_cache=True))
def get_franchise(request, slug: str):
    from ..models import Franchise

    franchise = get_object_or_404(
        Franchise.objects.active().prefetch_related(
            Prefetch("titles", queryset=_franchise_titles_qs()), claims_prefetch()
        ),
        slug=slug,
    )
    return {
        "name": franchise.name,
        "slug": franchise.slug,
        "description": _build_rich_text(
            franchise, "description", getattr(franchise, "active_claims", [])
        ),
        "titles": [_serialize_title_list(t) for t in franchise.titles.all()],
        "sources": build_sources(getattr(franchise, "active_claims", [])),
    }


@franchises_router.patch(
    "/{slug}/claims/",
    auth=django_auth,
    response=FranchiseDetailSchema,
    tags=["private"],
)
def patch_franchise_claims(request, slug: str, data: ClaimPatchSchema):
    """Assert per-field claims from the authenticated user, then re-resolve."""
    from ..models import Franchise
    from .edit_claims import plan_scalar_field_claims

    franchise = get_object_or_404(Franchise.objects.active(), slug=slug)
    specs = plan_scalar_field_claims(Franchise, data.fields, entity=franchise)

    execute_claims(franchise, specs, user=request.user)

    franchise = get_object_or_404(
        Franchise.objects.active().prefetch_related(
            Prefetch("titles", queryset=_franchise_titles_qs()), claims_prefetch()
        ),
        slug=franchise.slug,
    )
    return {
        "name": franchise.name,
        "slug": franchise.slug,
        "description": _build_rich_text(
            franchise, "description", getattr(franchise, "active_claims", [])
        ),
        "titles": [_serialize_title_list(t) for t in franchise.titles.all()],
        "sources": build_sources(getattr(franchise, "active_claims", [])),
    }
