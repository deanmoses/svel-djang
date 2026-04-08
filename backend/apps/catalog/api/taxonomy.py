"""Taxonomy routers — technology generations, display types, and related lookups."""

from __future__ import annotations

from django.db.models import F, Prefetch
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.security import django_auth

from .edit_claims import execute_claims, plan_scalar_field_claims
from apps.provenance.helpers import build_sources, claims_prefetch

from ..models import (
    Cabinet,
    CreditRole,
    DisplaySubtype,
    DisplayType,
    GameFormat,
    MachineModel,
    RewardType,
    Tag,
    TechnologyGeneration,
    TechnologySubgeneration,
)
from apps.core.licensing import get_minimum_display_rank

from .helpers import _build_rich_text, _serialize_title_machine
from .schemas import ClaimPatchSchema, ClaimSchema, RichTextSchema, TitleMachineSchema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_taxonomy(obj) -> dict:
    return {
        "name": obj.name,
        "slug": obj.slug,
        "display_order": obj.display_order,
        "description": _build_rich_text(
            obj, "description", getattr(obj, "active_claims", [])
        ),
        "sources": build_sources(getattr(obj, "active_claims", [])),
    }


def _taxonomy_detail_qs(model_class):
    return model_class.objects.active().prefetch_related(claims_prefetch())


def _patch_taxonomy(request, model_class, slug, data):
    """Shared PATCH handler for all taxonomy entities."""
    obj = get_object_or_404(model_class.objects.active(), slug=slug)
    specs = plan_scalar_field_claims(model_class, data.fields, entity=obj)

    execute_claims(
        obj, specs, user=request.user, note=data.note, citation=data.citation
    )

    obj = get_object_or_404(_taxonomy_detail_qs(model_class), slug=obj.slug)
    return _serialize_taxonomy(obj)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TaxonomySchema(Schema):
    name: str
    slug: str
    display_order: int
    description: RichTextSchema = RichTextSchema()
    sources: list[ClaimSchema] = []


# ---------------------------------------------------------------------------
# Technology Generations router
# ---------------------------------------------------------------------------

technology_generations_router = Router(tags=["technology-generations"])


@technology_generations_router.get("/", response=list[TaxonomySchema])
@decorate_view(cache_control(no_cache=True))
def list_technology_generations(request):
    return [
        _serialize_taxonomy(t)
        for t in TechnologyGeneration.objects.active().order_by("display_order")
    ]


@technology_generations_router.patch(
    "/{slug}/claims/", auth=django_auth, response=TaxonomySchema, tags=["private"]
)
def patch_technology_generation(request, slug: str, data: ClaimPatchSchema):
    return _patch_taxonomy(request, TechnologyGeneration, slug, data)


# ---------------------------------------------------------------------------
# Display Types router
# ---------------------------------------------------------------------------

display_types_router = Router(tags=["display-types"])


@display_types_router.get("/", response=list[TaxonomySchema])
@decorate_view(cache_control(no_cache=True))
def list_display_types(request):
    return [
        _serialize_taxonomy(d)
        for d in DisplayType.objects.active().order_by("display_order")
    ]


@display_types_router.patch(
    "/{slug}/claims/", auth=django_auth, response=TaxonomySchema, tags=["private"]
)
def patch_display_type(request, slug: str, data: ClaimPatchSchema):
    return _patch_taxonomy(request, DisplayType, slug, data)


# ---------------------------------------------------------------------------
# Technology Subgenerations router
# ---------------------------------------------------------------------------

technology_subgenerations_router = Router(tags=["technology-subgenerations"])


@technology_subgenerations_router.get("/", response=list[TaxonomySchema])
@decorate_view(cache_control(no_cache=True))
def list_technology_subgenerations(request):
    return [
        _serialize_taxonomy(t)
        for t in TechnologySubgeneration.objects.active().order_by("display_order")
    ]


@technology_subgenerations_router.patch(
    "/{slug}/claims/", auth=django_auth, response=TaxonomySchema, tags=["private"]
)
def patch_technology_subgeneration(request, slug: str, data: ClaimPatchSchema):
    return _patch_taxonomy(request, TechnologySubgeneration, slug, data)


# ---------------------------------------------------------------------------
# Display Subtypes router
# ---------------------------------------------------------------------------

display_subtypes_router = Router(tags=["display-subtypes"])


@display_subtypes_router.get("/", response=list[TaxonomySchema])
@decorate_view(cache_control(no_cache=True))
def list_display_subtypes(request):
    return [
        _serialize_taxonomy(d)
        for d in DisplaySubtype.objects.active().order_by("display_order")
    ]


@display_subtypes_router.patch(
    "/{slug}/claims/", auth=django_auth, response=TaxonomySchema, tags=["private"]
)
def patch_display_subtype(request, slug: str, data: ClaimPatchSchema):
    return _patch_taxonomy(request, DisplaySubtype, slug, data)


# ---------------------------------------------------------------------------
# Cabinets router
# ---------------------------------------------------------------------------

cabinets_router = Router(tags=["cabinets"])


@cabinets_router.get("/", response=list[TaxonomySchema])
@decorate_view(cache_control(no_cache=True))
def list_cabinets(request):
    return [
        _serialize_taxonomy(c)
        for c in Cabinet.objects.active().order_by("display_order")
    ]


@cabinets_router.patch(
    "/{slug}/claims/", auth=django_auth, response=TaxonomySchema, tags=["private"]
)
def patch_cabinet(request, slug: str, data: ClaimPatchSchema):
    return _patch_taxonomy(request, Cabinet, slug, data)


# ---------------------------------------------------------------------------
# Game Formats router
# ---------------------------------------------------------------------------

game_formats_router = Router(tags=["game-formats"])


@game_formats_router.get("/", response=list[TaxonomySchema])
@decorate_view(cache_control(no_cache=True))
def list_game_formats(request):
    return [
        _serialize_taxonomy(g)
        for g in GameFormat.objects.active().order_by("display_order")
    ]


@game_formats_router.patch(
    "/{slug}/claims/", auth=django_auth, response=TaxonomySchema, tags=["private"]
)
def patch_game_format(request, slug: str, data: ClaimPatchSchema):
    return _patch_taxonomy(request, GameFormat, slug, data)


# ---------------------------------------------------------------------------
# Reward Types router
# ---------------------------------------------------------------------------


class RewardTypeDetailSchema(TaxonomySchema):
    machines: list[TitleMachineSchema] = []


reward_types_router = Router(tags=["reward-types"])


def _reward_type_detail_qs():
    return RewardType.objects.active().prefetch_related(
        claims_prefetch(),
        Prefetch(
            "machine_models",
            queryset=MachineModel.objects.active()
            .filter(variant_of__isnull=True)
            .select_related("corporate_entity__manufacturer", "technology_generation")
            .order_by(F("year").desc(nulls_last=True), "name"),
        ),
    )


def _serialize_reward_type_detail(rt) -> dict:
    min_rank = get_minimum_display_rank()
    return {
        **_serialize_taxonomy(rt),
        "machines": [
            _serialize_title_machine(pm, min_rank=min_rank)
            for pm in rt.machine_models.all()
        ],
    }


@reward_types_router.get("/", response=list[TaxonomySchema])
@decorate_view(cache_control(no_cache=True))
def list_reward_types(request):
    return [
        _serialize_taxonomy(rt)
        for rt in RewardType.objects.active().order_by("display_order", "name")
    ]


@reward_types_router.patch(
    "/{slug}/claims/",
    auth=django_auth,
    response=RewardTypeDetailSchema,
    tags=["private"],
)
def patch_reward_type(request, slug: str, data: ClaimPatchSchema):
    obj = get_object_or_404(RewardType.objects.active(), slug=slug)
    specs = plan_scalar_field_claims(RewardType, data.fields, entity=obj)

    execute_claims(
        obj, specs, user=request.user, note=data.note, citation=data.citation
    )

    rt = get_object_or_404(_reward_type_detail_qs(), slug=obj.slug)
    return _serialize_reward_type_detail(rt)


# ---------------------------------------------------------------------------
# Tags router
# ---------------------------------------------------------------------------

tags_router = Router(tags=["tags"])


@tags_router.get("/", response=list[TaxonomySchema])
@decorate_view(cache_control(no_cache=True))
def list_tags(request):
    return [
        _serialize_taxonomy(t) for t in Tag.objects.active().order_by("display_order")
    ]


@tags_router.patch(
    "/{slug}/claims/", auth=django_auth, response=TaxonomySchema, tags=["private"]
)
def patch_tag(request, slug: str, data: ClaimPatchSchema):
    return _patch_taxonomy(request, Tag, slug, data)


# ---------------------------------------------------------------------------
# Credit Roles router
# ---------------------------------------------------------------------------

credit_roles_router = Router(tags=["credit-roles"])


@credit_roles_router.get("/", response=list[TaxonomySchema])
@decorate_view(cache_control(no_cache=True))
def list_credit_roles(request):
    return [
        _serialize_taxonomy(c)
        for c in CreditRole.objects.active().order_by("display_order")
    ]


@credit_roles_router.get("/{slug}", response=TaxonomySchema)
@decorate_view(cache_control(no_cache=True))
def get_credit_role(request, slug: str):
    return _serialize_taxonomy(
        get_object_or_404(_taxonomy_detail_qs(CreditRole), slug=slug)
    )
