"""Systems router — list and detail endpoints."""

from __future__ import annotations

from typing import Optional

from django.db.models import Count, F, Max, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view

from .helpers import _extract_image_urls
from .schemas import RelatedTitleSchema

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SystemListSchema(Schema):
    name: str
    slug: str
    manufacturer_name: Optional[str] = None
    manufacturer_slug: Optional[str] = None
    machine_count: int = 0


class SiblingSystemSchema(Schema):
    name: str
    slug: str


class SystemDetailSchema(Schema):
    name: str
    slug: str
    description: str = ""
    description_html: str = ""
    manufacturer_name: Optional[str] = None
    manufacturer_slug: Optional[str] = None
    titles: list[RelatedTitleSchema]
    sibling_systems: list[SiblingSystemSchema] = []


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

systems_router = Router(tags=["systems"])


@systems_router.get("/all/", response=list[SystemListSchema])
@decorate_view(cache_control(public=True, max_age=300))
def list_all_systems(request):
    """Return every system with machine count (no pagination)."""
    from ..models import System

    qs = (
        System.objects.select_related("manufacturer")
        .annotate(
            machine_count=Count(
                "machine_models", filter=Q(machine_models__variant_of__isnull=True)
            )
        )
        .order_by("name")
    )
    return [
        {
            "name": s.name,
            "slug": s.slug,
            "manufacturer_name": s.manufacturer.name if s.manufacturer else None,
            "manufacturer_slug": s.manufacturer.slug if s.manufacturer else None,
            "machine_count": s.machine_count,
        }
        for s in qs
    ]


@systems_router.get("/{slug}", response=SystemDetailSchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_system(request, slug: str):
    from ..models import MachineModel, System

    system = get_object_or_404(
        System.objects.select_related("manufacturer").prefetch_related(
            Prefetch(
                "machine_models",
                queryset=MachineModel.objects.filter(variant_of__isnull=True)
                .select_related("corporate_entity__manufacturer", "title")
                .order_by(F("year").desc(nulls_last=True), "name"),
            )
        ),
        slug=slug,
    )
    titles: dict[str, dict] = {}
    for m in system.machine_models.all():
        if m.title is None:
            continue
        key = m.title.slug
        if key not in titles:
            thumbnail_url = _extract_image_urls(m.extra_data or {})[0]
            titles[key] = {
                "name": m.title.name,
                "slug": m.title.slug,
                "year": m.year,
                "manufacturer_name": (
                    m.corporate_entity.manufacturer.name
                    if m.corporate_entity and m.corporate_entity.manufacturer
                    else None
                ),
                "thumbnail_url": thumbnail_url,
            }
        elif titles[key]["thumbnail_url"] is None:
            thumbnail_url = _extract_image_urls(m.extra_data or {})[0]
            if thumbnail_url:
                titles[key]["thumbnail_url"] = thumbnail_url
    sibling_systems = []
    if system.manufacturer:
        sibling_systems = list(
            System.objects.filter(manufacturer=system.manufacturer)
            .exclude(pk=system.pk)
            .annotate(latest_year=Max("machine_models__year"))
            .order_by(F("latest_year").desc(nulls_last=True), "name")
            .values("name", "slug")
        )

    from apps.core.markdown import render_markdown_fields

    return {
        "name": system.name,
        "slug": system.slug,
        "description": system.description,
        **render_markdown_fields(system),
        "manufacturer_name": system.manufacturer.name if system.manufacturer else None,
        "manufacturer_slug": system.manufacturer.slug if system.manufacturer else None,
        "titles": list(titles.values()),
        "sibling_systems": sibling_systems,
    }
