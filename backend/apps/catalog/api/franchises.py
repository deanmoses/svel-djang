"""Franchises router — list and detail endpoints."""

from __future__ import annotations

from typing import Optional

from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view

from .helpers import _build_rich_text, _claims_prefetch, _extract_image_urls
from .schemas import RichTextSchema


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TitleRefSchema(Schema):
    name: str
    slug: str
    abbreviations: list[str] = []
    machine_count: int = 0
    manufacturer_name: Optional[str] = None
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
@decorate_view(cache_control(public=True, max_age=300))
def list_all_franchises(request):
    """Return every franchise with title count (no pagination)."""
    from ..models import Franchise

    qs = Franchise.objects.annotate(title_count=Count("titles")).order_by("name")
    return [
        {
            "name": f.name,
            "slug": f.slug,
            "title_count": f.title_count,
        }
        for f in qs
    ]


@franchises_router.get("/{slug}", response=FranchiseDetailSchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_franchise(request, slug: str):
    from ..models import Franchise, MachineModel, Title

    titles_qs = Title.objects.annotate(
        machine_count=Count(
            "machine_models",
            filter=Q(machine_models__variant_of__isnull=True),
        )
    ).prefetch_related(
        "abbreviations",
        Prefetch(
            "machine_models",
            queryset=MachineModel.objects.filter(variant_of__isnull=True)
            .select_related("corporate_entity__manufacturer")
            .order_by("year", "name"),
        ),
    )
    franchise = get_object_or_404(
        Franchise.objects.prefetch_related(
            Prefetch("titles", queryset=titles_qs), _claims_prefetch()
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
    }
