"""Themes router — list and detail endpoints."""

from __future__ import annotations

from django.db.models import F, Prefetch
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view

from apps.core.markdown import render_markdown_fields

from .helpers import _serialize_title_machine
from .schemas import TitleMachineSchema

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ThemeListSchema(Schema):
    name: str
    slug: str


class ThemeDetailSchema(Schema):
    name: str
    slug: str
    description: str = ""
    description_html: str = ""
    machines: list[TitleMachineSchema]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

themes_router = Router(tags=["themes"])


@themes_router.get("/", response=list[ThemeListSchema])
@decorate_view(cache_control(public=True, max_age=300))
def list_themes(request):
    from ..models import Theme

    return list(Theme.objects.order_by("name").values("name", "slug"))


@themes_router.get("/{slug}", response=ThemeDetailSchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_theme(request, slug: str):
    from ..models import MachineModel, Theme

    theme = get_object_or_404(
        Theme.objects.prefetch_related(
            Prefetch(
                "machine_models",
                queryset=MachineModel.objects.filter(variant_of__isnull=True)
                .select_related(
                    "corporate_entity__manufacturer", "technology_generation"
                )
                .order_by(F("year").desc(nulls_last=True), "name"),
            )
        ),
        slug=slug,
    )
    return {
        "name": theme.name,
        "slug": theme.slug,
        "description": theme.description,
        **render_markdown_fields(theme),
        "machines": [_serialize_title_machine(pm) for pm in theme.machine_models.all()],
    }
