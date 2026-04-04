"""Systems router — list, detail, and claims endpoints."""

from __future__ import annotations

from typing import Optional

from django.db.models import Count, F, Max, Prefetch, Q
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
from .schemas import (
    ClaimPatchSchema,
    ClaimSchema,
    Ref,
    RelatedTitleSchema,
    RichTextSchema,
)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SystemListSchema(Schema):
    name: str
    slug: str
    manufacturer: Optional[Ref] = None
    machine_count: int = 0


class SiblingSystemSchema(Schema):
    name: str
    slug: str


class SystemDetailSchema(Schema):
    name: str
    slug: str
    description: RichTextSchema = RichTextSchema()
    manufacturer: Optional[Ref] = None
    titles: list[RelatedTitleSchema]
    sibling_systems: list[SiblingSystemSchema] = []
    sources: list[ClaimSchema] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _system_detail_qs():
    from ..models import MachineModel, System

    return (
        System.objects.active()
        .select_related("manufacturer")
        .prefetch_related(
            claims_prefetch(),
            Prefetch(
                "machine_models",
                queryset=MachineModel.objects.active()
                .filter(variant_of__isnull=True)
                .select_related("corporate_entity__manufacturer", "title")
                .order_by(F("year").desc(nulls_last=True), "name"),
            ),
        )
    )


def _serialize_system_detail(system) -> dict:
    from ..models import System

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
            System.objects.active()
            .filter(manufacturer=system.manufacturer)
            .exclude(pk=system.pk)
            .annotate(latest_year=Max("machine_models__year"))
            .order_by(F("latest_year").desc(nulls_last=True), "name")
            .values("name", "slug")
        )

    return {
        "name": system.name,
        "slug": system.slug,
        "description": _build_rich_text(
            system, "description", getattr(system, "active_claims", [])
        ),
        "manufacturer": (
            {"name": system.manufacturer.name, "slug": system.manufacturer.slug}
            if system.manufacturer
            else None
        ),
        "titles": list(titles.values()),
        "sibling_systems": sibling_systems,
        "sources": build_sources(getattr(system, "active_claims", [])),
    }


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

systems_router = Router(tags=["systems"])


@systems_router.get("/all/", response=list[SystemListSchema])
@decorate_view(cache_control(no_cache=True))
def list_all_systems(request):
    """Return every system with machine count (no pagination)."""
    from ..models import System

    qs = (
        System.objects.active()
        .select_related("manufacturer")
        .annotate(
            machine_count=Count(
                "machine_models",
                filter=Q(machine_models__variant_of__isnull=True)
                & active_status_q("machine_models"),
            )
        )
        .order_by("name")
    )
    return [
        {
            "name": s.name,
            "slug": s.slug,
            "manufacturer": (
                {"name": s.manufacturer.name, "slug": s.manufacturer.slug}
                if s.manufacturer
                else None
            ),
            "machine_count": s.machine_count,
        }
        for s in qs
    ]


@systems_router.get("/{slug}", response=SystemDetailSchema)
@decorate_view(cache_control(no_cache=True))
def get_system(request, slug: str):
    system = get_object_or_404(_system_detail_qs(), slug=slug)
    return _serialize_system_detail(system)


@systems_router.patch(
    "/{slug}/claims/", auth=django_auth, response=SystemDetailSchema, tags=["private"]
)
def patch_system_claims(request, slug: str, data: ClaimPatchSchema):
    """Assert per-field claims from the authenticated user, then re-resolve."""
    from ..models import System
    from .edit_claims import plan_scalar_field_claims

    system = get_object_or_404(System.objects.active(), slug=slug)
    specs = plan_scalar_field_claims(System, data.fields, entity=system)

    execute_claims(system, specs, user=request.user)

    system = get_object_or_404(_system_detail_qs(), slug=system.slug)
    return _serialize_system_detail(system)
