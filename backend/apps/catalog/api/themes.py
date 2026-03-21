"""Themes router — list and detail endpoints."""

from __future__ import annotations

from django.db.models import F, Prefetch
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view

from apps.core.markdown import render_markdown_fields

from .helpers import _serialize_title_machine
from .schemas import ThemeSchema, TitleMachineSchema

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ThemeListSchema(Schema):
    name: str
    slug: str
    parent_slugs: list[str] = []


class ThemeDetailSchema(Schema):
    name: str
    slug: str
    description: str = ""
    description_html: str = ""
    aliases: list[str] = []
    parents: list[ThemeSchema] = []
    children: list[ThemeSchema] = []
    machines: list[TitleMachineSchema]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

themes_router = Router(tags=["themes"])


@themes_router.get("/", response=list[ThemeListSchema])
@decorate_view(cache_control(public=True, max_age=300))
def list_themes(request):
    from ..models import Theme

    themes = Theme.objects.prefetch_related("parents").order_by("name")
    return [
        {
            "name": t.name,
            "slug": t.slug,
            "parent_slugs": [p.slug for p in t.parents.all()],
        }
        for t in themes
    ]


@themes_router.get("/{slug}", response=ThemeDetailSchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_theme(request, slug: str):
    from ..models import MachineModel, Theme

    theme = get_object_or_404(
        Theme.objects.prefetch_related(
            "parents",
            "children",
            "aliases",
            Prefetch(
                "machine_models",
                queryset=MachineModel.objects.filter(variant_of__isnull=True)
                .select_related(
                    "corporate_entity__manufacturer", "technology_generation"
                )
                .order_by(F("year").desc(nulls_last=True), "name"),
            ),
        ),
        slug=slug,
    )
    return {
        "name": theme.name,
        "slug": theme.slug,
        "description": theme.description,
        **render_markdown_fields(theme),
        "aliases": [a.value for a in theme.aliases.all()],
        "parents": [{"name": t.name, "slug": t.slug} for t in theme.parents.all()],
        "children": [
            {"name": t.name, "slug": t.slug} for t in theme.children.order_by("name")
        ],
        "machines": [_serialize_title_machine(pm) for pm in theme.machine_models.all()],
    }
