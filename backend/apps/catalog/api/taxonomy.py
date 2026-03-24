"""Taxonomy routers — technology generations, display types, and related lookups."""

from __future__ import annotations

from django.db.models import F, Prefetch
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view

from .helpers import _build_rich_text
from .schemas import RichTextSchema, TitleMachineSchema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_taxonomy(obj) -> dict:
    return {
        "name": obj.name,
        "slug": obj.slug,
        "display_order": obj.display_order,
        "description": _build_rich_text(obj, "description"),
    }


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TaxonomySchema(Schema):
    name: str
    slug: str
    display_order: int
    description: RichTextSchema = RichTextSchema()


# ---------------------------------------------------------------------------
# Technology Generations router
# ---------------------------------------------------------------------------

technology_generations_router = Router(tags=["technology-generations"])


@technology_generations_router.get("/", response=list[TaxonomySchema])
@decorate_view(cache_control(public=True, max_age=300))
def list_technology_generations(request):
    from ..models import TechnologyGeneration

    return [
        _serialize_taxonomy(t)
        for t in TechnologyGeneration.objects.order_by("display_order")
    ]


@technology_generations_router.get("/{slug}", response=TaxonomySchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_technology_generation(request, slug: str):
    from ..models import TechnologyGeneration

    return _serialize_taxonomy(get_object_or_404(TechnologyGeneration, slug=slug))


# ---------------------------------------------------------------------------
# Display Types router
# ---------------------------------------------------------------------------

display_types_router = Router(tags=["display-types"])


@display_types_router.get("/", response=list[TaxonomySchema])
@decorate_view(cache_control(public=True, max_age=300))
def list_display_types(request):
    from ..models import DisplayType

    return [
        _serialize_taxonomy(d) for d in DisplayType.objects.order_by("display_order")
    ]


@display_types_router.get("/{slug}", response=TaxonomySchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_display_type(request, slug: str):
    from ..models import DisplayType

    return _serialize_taxonomy(get_object_or_404(DisplayType, slug=slug))


# ---------------------------------------------------------------------------
# Technology Subgenerations router
# ---------------------------------------------------------------------------

technology_subgenerations_router = Router(tags=["technology-subgenerations"])


@technology_subgenerations_router.get("/", response=list[TaxonomySchema])
@decorate_view(cache_control(public=True, max_age=300))
def list_technology_subgenerations(request):
    from ..models import TechnologySubgeneration

    return [
        _serialize_taxonomy(t)
        for t in TechnologySubgeneration.objects.order_by("display_order")
    ]


@technology_subgenerations_router.get("/{slug}", response=TaxonomySchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_technology_subgeneration(request, slug: str):
    from ..models import TechnologySubgeneration

    return _serialize_taxonomy(get_object_or_404(TechnologySubgeneration, slug=slug))


# ---------------------------------------------------------------------------
# Display Subtypes router
# ---------------------------------------------------------------------------

display_subtypes_router = Router(tags=["display-subtypes"])


@display_subtypes_router.get("/", response=list[TaxonomySchema])
@decorate_view(cache_control(public=True, max_age=300))
def list_display_subtypes(request):
    from ..models import DisplaySubtype

    return [
        _serialize_taxonomy(d) for d in DisplaySubtype.objects.order_by("display_order")
    ]


@display_subtypes_router.get("/{slug}", response=TaxonomySchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_display_subtype(request, slug: str):
    from ..models import DisplaySubtype

    return _serialize_taxonomy(get_object_or_404(DisplaySubtype, slug=slug))


# ---------------------------------------------------------------------------
# Cabinets router
# ---------------------------------------------------------------------------

cabinets_router = Router(tags=["cabinets"])


@cabinets_router.get("/", response=list[TaxonomySchema])
@decorate_view(cache_control(public=True, max_age=300))
def list_cabinets(request):
    from ..models import Cabinet

    return [_serialize_taxonomy(c) for c in Cabinet.objects.order_by("display_order")]


@cabinets_router.get("/{slug}", response=TaxonomySchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_cabinet(request, slug: str):
    from ..models import Cabinet

    return _serialize_taxonomy(get_object_or_404(Cabinet, slug=slug))


# ---------------------------------------------------------------------------
# Game Formats router
# ---------------------------------------------------------------------------

game_formats_router = Router(tags=["game-formats"])


@game_formats_router.get("/", response=list[TaxonomySchema])
@decorate_view(cache_control(public=True, max_age=300))
def list_game_formats(request):
    from ..models import GameFormat

    return [
        _serialize_taxonomy(g) for g in GameFormat.objects.order_by("display_order")
    ]


@game_formats_router.get("/{slug}", response=TaxonomySchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_game_format(request, slug: str):
    from ..models import GameFormat

    return _serialize_taxonomy(get_object_or_404(GameFormat, slug=slug))


# ---------------------------------------------------------------------------
# Reward Types router
# ---------------------------------------------------------------------------


class RewardTypeDetailSchema(TaxonomySchema):
    machines: list[TitleMachineSchema] = []


reward_types_router = Router(tags=["reward-types"])


@reward_types_router.get("/", response=list[TaxonomySchema])
@decorate_view(cache_control(public=True, max_age=300))
def list_reward_types(request):
    from ..models import RewardType

    return [
        _serialize_taxonomy(rt)
        for rt in RewardType.objects.order_by("display_order", "name")
    ]


@reward_types_router.get("/{slug}", response=RewardTypeDetailSchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_reward_type(request, slug: str):
    from ..models import MachineModel, RewardType
    from .helpers import _serialize_title_machine

    rt = get_object_or_404(
        RewardType.objects.prefetch_related(
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
        **_serialize_taxonomy(rt),
        "machines": [_serialize_title_machine(pm) for pm in rt.machine_models.all()],
    }


# ---------------------------------------------------------------------------
# Tags router
# ---------------------------------------------------------------------------

tags_router = Router(tags=["tags"])


@tags_router.get("/", response=list[TaxonomySchema])
@decorate_view(cache_control(public=True, max_age=300))
def list_tags(request):
    from ..models import Tag

    return [_serialize_taxonomy(t) for t in Tag.objects.order_by("display_order")]


@tags_router.get("/{slug}", response=TaxonomySchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_tag(request, slug: str):
    from ..models import Tag

    return _serialize_taxonomy(get_object_or_404(Tag, slug=slug))


# ---------------------------------------------------------------------------
# Credit Roles router
# ---------------------------------------------------------------------------

credit_roles_router = Router(tags=["credit-roles"])


@credit_roles_router.get("/", response=list[TaxonomySchema])
@decorate_view(cache_control(public=True, max_age=300))
def list_credit_roles(request):
    from ..models import CreditRole

    return [
        _serialize_taxonomy(c) for c in CreditRole.objects.order_by("display_order")
    ]


@credit_roles_router.get("/{slug}", response=TaxonomySchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_credit_role(request, slug: str):
    from ..models import CreditRole

    return _serialize_taxonomy(get_object_or_404(CreditRole, slug=slug))
