"""Themes router — list, detail, and claims endpoints."""

from __future__ import annotations

from django.db.models import F, Prefetch
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError
from ninja.security import django_auth

from .edit_claims import (
    execute_claims,
    plan_alias_claims,
    plan_parent_claims,
    validate_scalar_fields,
)
from apps.provenance.helpers import build_sources, claims_prefetch

from .helpers import (
    _build_rich_text,
    _serialize_title_machine,
)
from .schemas import (
    ClaimSchema,
    HierarchyClaimPatchSchema,
    RichTextSchema,
    ThemeSchema,
    TitleMachineSchema,
)

from apps.core.licensing import get_minimum_display_rank

from ..models import MachineModel, Theme

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
    description: RichTextSchema = RichTextSchema()
    aliases: list[str] = []
    parents: list[ThemeSchema] = []
    children: list[ThemeSchema] = []
    machines: list[TitleMachineSchema]
    sources: list[ClaimSchema] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detail_qs():
    return Theme.objects.active().prefetch_related(
        Prefetch("parents", queryset=Theme.objects.active()),
        Prefetch("children", queryset=Theme.objects.active()),
        "aliases",
        claims_prefetch(),
        Prefetch(
            "machine_models",
            queryset=MachineModel.objects.active()
            .filter(variant_of__isnull=True)
            .select_related("corporate_entity__manufacturer", "technology_generation")
            .order_by(F("year").desc(nulls_last=True), "name"),
        ),
    )


def _serialize_detail(theme) -> dict:
    min_rank = get_minimum_display_rank()
    return {
        "name": theme.name,
        "slug": theme.slug,
        "description": _build_rich_text(
            theme, "description", getattr(theme, "active_claims", [])
        ),
        "aliases": [a.value for a in theme.aliases.all()],
        "parents": [{"name": t.name, "slug": t.slug} for t in theme.parents.all()],
        "children": [
            {"name": t.name, "slug": t.slug} for t in theme.children.order_by("name")
        ],
        "machines": [
            _serialize_title_machine(pm, min_rank=min_rank)
            for pm in theme.machine_models.all()
        ],
        "sources": build_sources(getattr(theme, "active_claims", [])),
    }


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

themes_router = Router(tags=["themes"])


@themes_router.get("/", response=list[ThemeListSchema])
@decorate_view(cache_control(no_cache=True))
def list_themes(request):
    themes = (
        Theme.objects.active()
        .prefetch_related(Prefetch("parents", queryset=Theme.objects.active()))
        .order_by("name")
    )
    return [
        {
            "name": t.name,
            "slug": t.slug,
            "parent_slugs": [p.slug for p in t.parents.all()],
        }
        for t in themes
    ]


@themes_router.patch(
    "/{slug}/claims/",
    auth=django_auth,
    response=ThemeDetailSchema,
    tags=["private"],
)
def patch_theme_claims(request, slug: str, data: HierarchyClaimPatchSchema):
    """Assert per-field claims from the authenticated user, then re-resolve."""
    if not data.fields and data.parents is None and data.aliases is None:
        raise HttpError(422, "No changes provided.")

    theme = get_object_or_404(Theme.objects.active(), slug=slug)

    specs = validate_scalar_fields(Theme, data.fields, entity=theme)

    if data.parents is not None:
        specs.extend(
            plan_parent_claims(
                theme,
                set(data.parents),
                model_class=Theme,
                claim_field_name="theme_parent",
            )
        )

    if data.aliases is not None:
        specs.extend(
            plan_alias_claims(
                theme,
                data.aliases,
                claim_field_name="theme_alias",
            )
        )

    if not specs:
        raise HttpError(422, "No changes provided.")

    execute_claims(
        theme, specs, user=request.user, note=data.note, citation=data.citation
    )

    theme = get_object_or_404(_detail_qs(), slug=theme.slug)
    return _serialize_detail(theme)
