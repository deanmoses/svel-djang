"""Taxonomy routers — technology generations and display types."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TechnologyGenerationSchema(Schema):
    name: str
    slug: str
    display_order: int
    description: str


class DisplayTypeSchema(Schema):
    name: str
    slug: str
    display_order: int
    description: str


# ---------------------------------------------------------------------------
# Technology Generations router
# ---------------------------------------------------------------------------

technology_generations_router = Router(tags=["technology-generations"])


@technology_generations_router.get("/", response=list[TechnologyGenerationSchema])
@decorate_view(cache_control(public=True, max_age=300))
def list_technology_generations(request):
    from ..models import TechnologyGeneration

    return list(TechnologyGeneration.objects.order_by("display_order"))


@technology_generations_router.get("/{slug}", response=TechnologyGenerationSchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_technology_generation(request, slug: str):
    from ..models import TechnologyGeneration

    return get_object_or_404(TechnologyGeneration, slug=slug)


# ---------------------------------------------------------------------------
# Display Types router
# ---------------------------------------------------------------------------

display_types_router = Router(tags=["display-types"])


@display_types_router.get("/", response=list[DisplayTypeSchema])
@decorate_view(cache_control(public=True, max_age=300))
def list_display_types(request):
    from ..models import DisplayType

    return list(DisplayType.objects.order_by("display_order"))


@display_types_router.get("/{slug}", response=DisplayTypeSchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_display_type(request, slug: str):
    from ..models import DisplayType

    return get_object_or_404(DisplayType, slug=slug)
