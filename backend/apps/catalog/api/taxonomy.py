"""Taxonomy routers — technology generations, display types, and related lookups."""

from __future__ import annotations

from itertools import chain

from django.db.models import Count, F, Prefetch
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.security import django_auth

from apps.core.licensing import get_minimum_display_rank
from apps.core.models import active_status_q
from apps.provenance.helpers import claims_prefetch
from apps.provenance.schemas import RichTextSchema

from ..models import (
    Cabinet,
    Credit,
    CreditRole,
    DisplaySubtype,
    DisplayType,
    GameFormat,
    MachineModel,
    Person,
    RewardType,
    Tag,
    TechnologyGeneration,
    TechnologySubgeneration,
)
from ._counts import bulk_title_counts_via_models
from .edit_claims import execute_claims, plan_scalar_field_claims
from .entity_crud import (
    register_entity_create,
    register_entity_delete_restore,
)
from .helpers import _build_rich_text, _extract_image_urls, _serialize_title_machine
from .people import PersonGridSchema
from .schemas import (
    ClaimPatchSchema,
    TitleMachineSchema,
)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TaxonomySchema(Schema):
    name: str
    slug: str
    display_order: int
    description: RichTextSchema = RichTextSchema()
    aliases: list[str] = []


class TaxonomyWithTitleCountSchema(TaxonomySchema):
    title_count: int = 0


class DisplayTypeListSchema(TaxonomyWithTitleCountSchema):
    subtypes: list[TaxonomyWithTitleCountSchema] = []


class TechnologyGenerationListSchema(TaxonomyWithTitleCountSchema):
    subgenerations: list[TaxonomyWithTitleCountSchema] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_taxonomy(obj) -> dict:
    # Only RewardType among the shared-schema taxonomies carries aliases;
    # Tag / Cabinet / GameFormat / Tech* / Display* don't have an alias
    # model. ``hasattr`` on the class keeps the serializer uniform without
    # triggering a lookup query on the alias-less branches.
    aliases: list[str] = []
    if hasattr(type(obj), "aliases"):
        aliases = [a.value for a in obj.aliases.all()]
    return {
        "name": obj.name,
        "slug": obj.slug,
        "display_order": obj.display_order,
        "description": _build_rich_text(
            obj, "description", getattr(obj, "active_claims", [])
        ),
        "aliases": aliases,
    }


def _list_taxonomy_with_counts(
    model_class, mm_relation: str, *, sort_by_display_order: bool = False
) -> list[dict]:
    """Standard list response for flat (non-DAG) model-attached taxonomies.

    Default sort is title_count desc (popular first). Pass
    ``sort_by_display_order=True`` for small, chronologically-meaningful
    taxonomies (tech generations, game formats) where editorial order is
    more useful to users than popularity.
    """
    items = list(
        model_class.objects.active().prefetch_related(
            *(["aliases"] if hasattr(model_class, "aliases") else [])
        )
    )
    counts = bulk_title_counts_via_models([t.pk for t in items], mm_relation)
    if sort_by_display_order:
        items.sort(key=lambda t: (t.display_order, t.name.lower()))
    else:
        items.sort(key=lambda t: (-counts.get(t.pk, 0), t.name.lower()))
    return [
        {**_serialize_taxonomy(t), "title_count": counts.get(t.pk, 0)} for t in items
    ]


def _taxonomy_detail_qs(model_class):
    prefetches: list[object] = [claims_prefetch()]
    if hasattr(model_class, "aliases"):
        prefetches.append("aliases")
    return model_class.objects.active().prefetch_related(*prefetches)


def _patch_taxonomy(request, model_class, slug, data):
    """Shared PATCH handler for all taxonomy entities."""
    obj = get_object_or_404(model_class.objects.active(), slug=slug)
    specs = plan_scalar_field_claims(model_class, data.fields, entity=obj)

    execute_claims(
        obj, specs, user=request.user, note=data.note, citation=data.citation
    )

    obj = get_object_or_404(_taxonomy_detail_qs(model_class), slug=obj.slug)
    return _serialize_taxonomy(obj)


def _register_delete_restore(router: Router, model_cls, **kwargs) -> None:
    """Thin wrapper — auto-plumbs the standard taxonomy detail/serialize pair."""
    register_entity_delete_restore(
        router,
        model_cls,
        detail_qs=lambda cls=model_cls: _taxonomy_detail_qs(cls),
        serialize_detail=_serialize_taxonomy,
        response_schema=TaxonomySchema,
        **kwargs,
    )


def _register_create(router: Router, model_cls, **kwargs) -> None:
    register_entity_create(
        router,
        model_cls,
        detail_qs=lambda cls=model_cls: _taxonomy_detail_qs(cls),
        serialize_detail=_serialize_taxonomy,
        response_schema=TaxonomySchema,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Technology Generations router
# ---------------------------------------------------------------------------

technology_generations_router = Router(tags=["technology-generations"])


@technology_generations_router.get("/", response=list[TechnologyGenerationListSchema])
@decorate_view(cache_control(no_cache=True))
def list_technology_generations(request):
    gens = list(TechnologyGeneration.objects.active())
    subgens = list(TechnologySubgeneration.objects.active())

    gen_counts = bulk_title_counts_via_models(
        [g.pk for g in gens], "technology_generation"
    )
    subgen_counts = _bulk_title_counts_for_subgenerations([s.pk for s in subgens])

    subgens_by_gen: dict[int, list[TechnologySubgeneration]] = {}
    for s in subgens:
        subgens_by_gen.setdefault(s.technology_generation_id, []).append(s)
    for group in subgens_by_gen.values():
        group.sort(key=lambda s: (s.display_order, s.name.lower()))

    gens.sort(key=lambda g: (g.display_order, g.name.lower()))

    return [
        {
            **_serialize_taxonomy(g),
            "title_count": gen_counts.get(g.pk, 0),
            "subgenerations": [
                {
                    **_serialize_taxonomy(s),
                    "title_count": subgen_counts.get(s.pk, 0),
                }
                for s in subgens_by_gen.get(g.pk, [])
            ],
        }
        for g in gens
    ]


def _bulk_title_counts_for_subgenerations(
    subgen_pks: list[int],
) -> dict[int, int]:
    """Count titles under each subgeneration, mirroring the OR semantics
    of the ``/api/models/?subgeneration=...`` filter: a machine counts
    toward a subgen if its own FK references it OR its ``system``'s FK
    references it. Without the inherited branch, subgens whose machines
    carry the attribution only through ``system`` show ``0 titles`` while
    the detail page lists many — see ``machine_models._build_model_list_qs``.
    """
    if not subgen_pks:
        return {}

    base = (
        MachineModel.objects.active()
        .filter(variant_of__isnull=True)
        .filter(active_status_q("title"))
    )
    direct = base.filter(technology_subgeneration__in=subgen_pks).values_list(
        "technology_subgeneration_id", "title_id"
    )
    inherited = base.filter(
        system__technology_subgeneration__in=subgen_pks
    ).values_list("system__technology_subgeneration_id", "title_id")

    titles_by_subgen: dict[int, set[int]] = {}
    for sg_id, title_id in chain(direct, inherited):
        if sg_id is None or title_id is None:
            continue
        titles_by_subgen.setdefault(sg_id, set()).add(title_id)

    return {pk: len(titles_by_subgen.get(pk, ())) for pk in subgen_pks}


@technology_generations_router.patch(
    "/{slug}/claims/", auth=django_auth, response=TaxonomySchema, tags=["private"]
)
def patch_technology_generation(request, slug: str, data: ClaimPatchSchema):
    return _patch_taxonomy(request, TechnologyGeneration, slug, data)


# ---------------------------------------------------------------------------
# Display Types router
# ---------------------------------------------------------------------------

display_types_router = Router(tags=["display-types"])


@display_types_router.get("/", response=list[DisplayTypeListSchema])
@decorate_view(cache_control(no_cache=True))
def list_display_types(request):
    types = list(DisplayType.objects.active())
    subtypes = list(DisplaySubtype.objects.active())

    type_counts = bulk_title_counts_via_models([t.pk for t in types], "display_type")
    subtype_counts = bulk_title_counts_via_models(
        [s.pk for s in subtypes], "display_subtype"
    )

    subtypes_by_type: dict[int, list[DisplaySubtype]] = {}
    for s in subtypes:
        subtypes_by_type.setdefault(s.display_type_id, []).append(s)
    for group in subtypes_by_type.values():
        group.sort(key=lambda s: (s.display_order, s.name.lower()))

    types.sort(key=lambda t: (t.display_order, t.name.lower()))

    return [
        {
            **_serialize_taxonomy(t),
            "title_count": type_counts.get(t.pk, 0),
            "subtypes": [
                {
                    **_serialize_taxonomy(s),
                    "title_count": subtype_counts.get(s.pk, 0),
                }
                for s in subtypes_by_type.get(t.pk, [])
            ],
        }
        for t in types
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


@technology_subgenerations_router.patch(
    "/{slug}/claims/", auth=django_auth, response=TaxonomySchema, tags=["private"]
)
def patch_technology_subgeneration(request, slug: str, data: ClaimPatchSchema):
    return _patch_taxonomy(request, TechnologySubgeneration, slug, data)


# ---------------------------------------------------------------------------
# Display Subtypes router
# ---------------------------------------------------------------------------

display_subtypes_router = Router(tags=["display-subtypes"])


@display_subtypes_router.patch(
    "/{slug}/claims/", auth=django_auth, response=TaxonomySchema, tags=["private"]
)
def patch_display_subtype(request, slug: str, data: ClaimPatchSchema):
    return _patch_taxonomy(request, DisplaySubtype, slug, data)


# ---------------------------------------------------------------------------
# Cabinets router
# ---------------------------------------------------------------------------

cabinets_router = Router(tags=["cabinets"])


@cabinets_router.get("/", response=list[TaxonomyWithTitleCountSchema])
@decorate_view(cache_control(no_cache=True))
def list_cabinets(request):
    return _list_taxonomy_with_counts(Cabinet, "cabinet")


@cabinets_router.patch(
    "/{slug}/claims/", auth=django_auth, response=TaxonomySchema, tags=["private"]
)
def patch_cabinet(request, slug: str, data: ClaimPatchSchema):
    return _patch_taxonomy(request, Cabinet, slug, data)


# ---------------------------------------------------------------------------
# Game Formats router
# ---------------------------------------------------------------------------

game_formats_router = Router(tags=["game-formats"])


@game_formats_router.get("/", response=list[TaxonomyWithTitleCountSchema])
@decorate_view(cache_control(no_cache=True))
def list_game_formats(request):
    return _list_taxonomy_with_counts(
        GameFormat, "game_format", sort_by_display_order=True
    )


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


@reward_types_router.get("/", response=list[TaxonomyWithTitleCountSchema])
@decorate_view(cache_control(no_cache=True))
def list_reward_types(request):
    return _list_taxonomy_with_counts(RewardType, "reward_types")


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


@tags_router.get("/", response=list[TaxonomyWithTitleCountSchema])
@decorate_view(cache_control(no_cache=True))
def list_tags(request):
    return _list_taxonomy_with_counts(Tag, "tags")


@tags_router.patch(
    "/{slug}/claims/", auth=django_auth, response=TaxonomySchema, tags=["private"]
)
def patch_tag(request, slug: str, data: ClaimPatchSchema):
    return _patch_taxonomy(request, Tag, slug, data)


# ---------------------------------------------------------------------------
# Credit Roles router
# ---------------------------------------------------------------------------


class CreditRoleDetailSchema(TaxonomySchema):
    people: list[PersonGridSchema] = []


credit_roles_router = Router(tags=["credit-roles"])


def _credit_role_people(cr: CreditRole) -> list[dict]:
    """Rank Persons by distinct active Titles credited in *cr*.

    Titles roll up all MachineModels (parent + variants) so a person credited
    only on an LE/Pro/Premium still counts toward the title exactly once.
    Series credits are intentionally excluded from the public rendering; the
    delete-blocker path covers series via ``soft_delete_usage_blockers``.

    Implemented Credit-side and then fanned out to Person so the SQL stays
    legible — the Person-side equivalent needs matching ``filter=`` subclauses
    on outer and annotation scopes, and tends to drift.
    """
    ranked = list(
        Credit.objects.filter(
            role=cr,
            model__isnull=False,
        )
        .filter(active_status_q("model"))
        .filter(active_status_q("model__title"))
        .filter(active_status_q("person"))
        .values("person")
        .annotate(credit_count=Count("model__title", distinct=True))
        .order_by("-credit_count")
    )
    if not ranked:
        return []

    # Preserve rank order while fetching Person rows with alias prefetch.
    person_ids = [r["person"] for r in ranked]
    count_by_id = {r["person"]: r["credit_count"] for r in ranked}
    people_by_id = {
        p.pk: p
        for p in Person.objects.filter(pk__in=person_ids).prefetch_related("aliases")
    }

    # Batch thumbnail per person — newest credited *active* model in this
    # role with extra_data. Active filters mirror the ranking query so a
    # person whose only active credit is on a low-profile machine doesn't
    # end up with a thumbnail from a deleted sibling.
    person_thumb_model: dict[int, int] = {}
    for person_id, model_id in (
        Credit.objects.filter(
            role=cr,
            person_id__in=person_ids,
            model__isnull=False,
            model__extra_data__isnull=False,
        )
        .filter(active_status_q("model"))
        .filter(active_status_q("model__title"))
        .order_by(F("model__year").desc(nulls_last=True))
        .values_list("person_id", "model_id")
    ):
        if person_id not in person_thumb_model:
            person_thumb_model[person_id] = model_id
    thumb_models = {
        m.pk: m
        for m in MachineModel.objects.filter(
            id__in=set(person_thumb_model.values())
        ).only("id", "extra_data")
    }

    min_rank = get_minimum_display_rank()
    out: list[dict] = []
    for pid in person_ids:
        person = people_by_id.get(pid)
        if person is None:
            continue
        thumbnail = None
        tm_id = person_thumb_model.get(pid)
        tm = thumb_models.get(tm_id) if tm_id else None
        if tm and tm.extra_data:
            t, _ = _extract_image_urls(tm.extra_data, min_rank=min_rank)
            if t:
                thumbnail = t
        out.append(
            {
                "name": person.name,
                "slug": person.slug,
                "aliases": [a.value for a in person.aliases.all()],
                "credit_count": count_by_id[pid],
                "thumbnail_url": thumbnail,
            }
        )
    return out


def _credit_role_detail_qs():
    # CreditRole has no alias relation — prefetch claims only.
    return CreditRole.objects.active().prefetch_related(claims_prefetch())


def _serialize_credit_role_detail(cr: CreditRole) -> dict:
    return {
        **_serialize_taxonomy(cr),
        "people": _credit_role_people(cr),
    }


def _serialize_credit_role_detail_no_people(cr: CreditRole) -> dict:
    # Used by the create response: a just-created role has no credits yet,
    # so the aggregate query is guaranteed empty. Skip it.
    return {**_serialize_taxonomy(cr), "people": []}


@credit_roles_router.get("/", response=list[TaxonomySchema])
@decorate_view(cache_control(no_cache=True))
def list_credit_roles(request):
    return [
        _serialize_taxonomy(c) for c in CreditRole.objects.active().order_by("name")
    ]


@credit_roles_router.get("/{slug}", response=CreditRoleDetailSchema)
@decorate_view(cache_control(no_cache=True))
def get_credit_role(request, slug: str):
    return _serialize_credit_role_detail(
        get_object_or_404(_credit_role_detail_qs(), slug=slug)
    )


@credit_roles_router.patch(
    "/{slug}/claims/",
    auth=django_auth,
    response=CreditRoleDetailSchema,
    tags=["private"],
)
def patch_credit_role(request, slug: str, data: ClaimPatchSchema):
    obj = get_object_or_404(CreditRole.objects.active(), slug=slug)
    specs = plan_scalar_field_claims(CreditRole, data.fields, entity=obj)

    execute_claims(
        obj, specs, user=request.user, note=data.note, citation=data.citation
    )

    cr = get_object_or_404(_credit_role_detail_qs(), slug=obj.slug)
    return _serialize_credit_role_detail(cr)


# ---------------------------------------------------------------------------
# Create / delete / restore wiring
# ---------------------------------------------------------------------------

# Delete / restore / preview — every target entity on its own router.
_register_delete_restore(
    technology_generations_router,
    TechnologyGeneration,
    child_related_name="subgenerations",
)
_register_delete_restore(
    technology_subgenerations_router,
    TechnologySubgeneration,
    parent_field="technology_generation",
)
_register_delete_restore(
    display_types_router,
    DisplayType,
    child_related_name="subtypes",
)
_register_delete_restore(
    display_subtypes_router,
    DisplaySubtype,
    parent_field="display_type",
)
_register_delete_restore(cabinets_router, Cabinet)
_register_delete_restore(game_formats_router, GameFormat)
_register_delete_restore(tags_router, Tag)
_register_delete_restore(reward_types_router, RewardType)
register_entity_delete_restore(
    credit_roles_router,
    CreditRole,
    detail_qs=_credit_role_detail_qs,
    serialize_detail=_serialize_credit_role_detail,
    response_schema=CreditRoleDetailSchema,
)

# Create — parentless entities on their own router.
_register_create(technology_generations_router, TechnologyGeneration)
_register_create(display_types_router, DisplayType)
_register_create(cabinets_router, Cabinet)
_register_create(game_formats_router, GameFormat)
_register_create(tags_router, Tag)
_register_create(reward_types_router, RewardType)
register_entity_create(
    credit_roles_router,
    CreditRole,
    detail_qs=_credit_role_detail_qs,
    serialize_detail=_serialize_credit_role_detail_no_people,
    response_schema=CreditRoleDetailSchema,
)

# Create — parented entities nested under the parent's router.
_register_create(
    technology_generations_router,
    TechnologySubgeneration,
    parent_field="technology_generation",
    parent_model=TechnologyGeneration,
    route_suffix="subgenerations",
)
_register_create(
    display_types_router,
    DisplaySubtype,
    parent_field="display_type",
    parent_model=DisplayType,
    route_suffix="subtypes",
)
