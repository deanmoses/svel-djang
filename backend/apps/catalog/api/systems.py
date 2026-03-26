"""Systems router — list, detail, and claims endpoints."""

from __future__ import annotations

from typing import Optional

from django.db.models import Count, F, Max, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError
from ninja.security import django_auth

from .edit_claims import execute_claims, validate_scalar_fields
from .helpers import (
    _build_activity,
    _build_rich_text,
    _claims_prefetch,
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
    activity: list[ClaimSchema] = []


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
    from ..models import MachineModel, System

    system = get_object_or_404(
        System.objects.select_related("manufacturer").prefetch_related(
            _claims_prefetch(),
            Prefetch(
                "machine_models",
                queryset=MachineModel.objects.filter(variant_of__isnull=True)
                .select_related("corporate_entity__manufacturer", "title")
                .order_by(F("year").desc(nulls_last=True), "name"),
            ),
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
        "activity": _build_activity(getattr(system, "active_claims", [])),
    }


@systems_router.patch(
    "/{slug}/claims/", auth=django_auth, response=SystemDetailSchema, tags=["private"]
)
def patch_system_claims(request, slug: str, data: ClaimPatchSchema):
    """Assert per-field claims from the authenticated user, then re-resolve."""
    from ..models import System

    if not data.fields:
        raise HttpError(422, "No changes provided.")

    system = get_object_or_404(System, slug=slug)
    specs = validate_scalar_fields(System, data.fields)
    if not specs:
        raise HttpError(422, "No changes provided.")

    execute_claims(system, specs, user=request.user)

    system = get_object_or_404(
        System.objects.prefetch_related(_claims_prefetch()), slug=system.slug
    )
    return {
        "name": system.name,
        "slug": system.slug,
        "description": _build_rich_text(
            system, "description", getattr(system, "active_claims", [])
        ),
        "manufacturer": None,
        "titles": [],
        "sibling_systems": [],
        "activity": _build_activity(getattr(system, "active_claims", [])),
    }
