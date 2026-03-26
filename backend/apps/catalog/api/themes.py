"""Themes router — list, detail, and claims endpoints."""

from __future__ import annotations

from django.db.models import F, Prefetch
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError
from ninja.security import django_auth

from .edit_claims import execute_claims, plan_parent_claims, validate_scalar_fields
from .helpers import (
    _build_activity,
    _build_edit_history,
    _build_rich_text,
    _claims_prefetch,
    _serialize_title_machine,
)
from .schemas import (
    ChangeSetSchema,
    ClaimSchema,
    HierarchyClaimPatchSchema,
    RichTextSchema,
    ThemeSchema,
    TitleMachineSchema,
)

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
    activity: list[ClaimSchema] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detail_qs():
    from ..models import MachineModel, Theme

    return Theme.objects.prefetch_related(
        "parents",
        "children",
        "aliases",
        _claims_prefetch(),
        Prefetch(
            "machine_models",
            queryset=MachineModel.objects.filter(variant_of__isnull=True)
            .select_related("corporate_entity__manufacturer", "technology_generation")
            .order_by(F("year").desc(nulls_last=True), "name"),
        ),
    )


def _serialize_detail(theme) -> dict:
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
        "machines": [_serialize_title_machine(pm) for pm in theme.machine_models.all()],
        "activity": _build_activity(getattr(theme, "active_claims", [])),
    }


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

themes_router = Router(tags=["themes"])


@themes_router.get("/", response=list[ThemeListSchema])
@decorate_view(cache_control(no_cache=True))
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
@decorate_view(cache_control(no_cache=True))
def get_theme(request, slug: str):
    theme = get_object_or_404(_detail_qs(), slug=slug)
    return _serialize_detail(theme)


@themes_router.patch(
    "/{slug}/claims/",
    auth=django_auth,
    response=ThemeDetailSchema,
    tags=["private"],
)
def patch_theme_claims(request, slug: str, data: HierarchyClaimPatchSchema):
    """Assert per-field claims from the authenticated user, then re-resolve."""
    from ..models import Theme
    from ..resolve._relationships import resolve_theme_parents

    if not data.fields and data.parents is None:
        raise HttpError(422, "No changes provided.")

    theme = get_object_or_404(Theme, slug=slug)

    specs = validate_scalar_fields(Theme, data.fields)

    resolvers = []
    if data.parents is not None:
        parent_specs = plan_parent_claims(
            theme,
            set(data.parents),
            model_class=Theme,
            claim_field_name="theme_parent",
        )
        specs.extend(parent_specs)
        if parent_specs:
            resolvers.append(resolve_theme_parents)

    if not specs:
        raise HttpError(422, "No changes provided.")

    execute_claims(theme, specs, user=request.user, note=data.note, resolvers=resolvers)

    theme = get_object_or_404(_detail_qs(), slug=theme.slug)
    return _serialize_detail(theme)


@themes_router.get("/{slug}/edit-history/", response=list[ChangeSetSchema])
@decorate_view(cache_control(no_cache=True))
def get_theme_edit_history(request, slug: str):
    """Return changeset-grouped edit history with old/new diffs."""
    from ..models import Theme

    theme = get_object_or_404(Theme, slug=slug)
    return _build_edit_history(theme)
