"""Page-oriented endpoints for catalog entities.

These endpoints live under /api/pages/ and are tagged "private" so they
stay out of the public API docs.  They return page-model responses shaped
for specific SvelteKit SSR routes.

Auto-discovered via the ``routers`` list convention in config/api.py.
"""

from __future__ import annotations

from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router

from apps.catalog.models import (
    Cabinet,
    DisplaySubtype,
    DisplayType,
    GameFormat,
    Tag,
    TechnologyGeneration,
    TechnologySubgeneration,
)

from .corporate_entities import (
    CorporateEntityDetailSchema,
)
from .corporate_entities import (
    _detail_qs as _corp_entity_detail_qs,
)
from .corporate_entities import (
    _serialize_detail as _serialize_corp_entity_detail,
)
from .franchises import (
    FranchiseDetailSchema,
    _franchise_detail_qs,
    _serialize_franchise_detail,
)
from .gameplay_features import (
    GameplayFeatureDetailSchema,
)
from .gameplay_features import (
    _detail_qs as _gf_detail_qs,
)
from .gameplay_features import (
    _serialize_detail as _serialize_gf_detail,
)
from .machine_models import (
    MachineModelDetailSchema,
    _model_detail_qs,
    _serialize_model_detail,
)
from .manufacturers import (
    ManufacturerDetailSchema,
    _manufacturer_qs,
    _serialize_manufacturer_detail,
)
from .people import (
    PersonDetailSchema,
    _person_qs,
    _serialize_person_detail,
)
from .series import (
    SeriesDetailSchema,
    _serialize_series_detail,
    _series_detail_qs,
)
from .systems import (
    SystemDetailSchema,
    _serialize_system_detail,
    _system_detail_qs,
)
from .taxonomy import (
    CreditRoleDetailSchema,
    RewardTypeDetailSchema,
    TaxonomySchema,
    _credit_role_detail_qs,
    _reward_type_detail_qs,
    _serialize_credit_role_detail,
    _serialize_reward_type_detail,
    _serialize_taxonomy,
    _taxonomy_detail_qs,
)
from .themes import (
    ThemeDetailSchema,
)
from .themes import (
    _detail_qs as _theme_detail_qs,
)
from .themes import (
    _serialize_detail as _serialize_theme_detail,
)
from .titles import TitleDetailSchema, _detail_qs, _serialize_title_detail

pages_router = Router(tags=["private"])


# ---------------------------------------------------------------------------
# Already-converted entities
# ---------------------------------------------------------------------------


@pages_router.get("/title/{slug}", response=TitleDetailSchema)
def title_detail_page(request: HttpRequest, slug: str) -> TitleDetailSchema:
    title = get_object_or_404(_detail_qs(), slug=slug)
    return _serialize_title_detail(title)


@pages_router.get("/manufacturer/{slug}", response=ManufacturerDetailSchema)
def manufacturer_detail_page(
    request: HttpRequest, slug: str
) -> ManufacturerDetailSchema:
    mfr = get_object_or_404(_manufacturer_qs(), slug=slug)
    return _serialize_manufacturer_detail(mfr)


@pages_router.get("/model/{slug}", response=MachineModelDetailSchema)
def model_detail_page(request: HttpRequest, slug: str) -> MachineModelDetailSchema:
    pm = get_object_or_404(_model_detail_qs(), slug=slug)
    return _serialize_model_detail(pm)


# ---------------------------------------------------------------------------
# Dedicated-router entities
# ---------------------------------------------------------------------------


@pages_router.get("/person/{slug}", response=PersonDetailSchema)
def person_detail_page(request: HttpRequest, slug: str) -> PersonDetailSchema:
    person = get_object_or_404(_person_qs(), slug=slug)
    return _serialize_person_detail(person)


@pages_router.get("/series/{slug}", response=SeriesDetailSchema)
def series_detail_page(request: HttpRequest, slug: str) -> SeriesDetailSchema:
    s = get_object_or_404(_series_detail_qs(), slug=slug)
    return _serialize_series_detail(s)


@pages_router.get("/corporate-entity/{slug}", response=CorporateEntityDetailSchema)
def corporate_entity_detail_page(
    request: HttpRequest, slug: str
) -> CorporateEntityDetailSchema:
    ce = get_object_or_404(_corp_entity_detail_qs(), slug=slug)
    return _serialize_corp_entity_detail(ce)


@pages_router.get("/gameplay-feature/{slug}", response=GameplayFeatureDetailSchema)
def gameplay_feature_detail_page(
    request: HttpRequest, slug: str
) -> GameplayFeatureDetailSchema:
    gf = get_object_or_404(_gf_detail_qs(), slug=slug)
    return _serialize_gf_detail(gf)


@pages_router.get("/franchise/{slug}", response=FranchiseDetailSchema)
def franchise_detail_page(request: HttpRequest, slug: str) -> FranchiseDetailSchema:
    f = get_object_or_404(_franchise_detail_qs(), slug=slug)
    return _serialize_franchise_detail(f)


@pages_router.get("/theme/{slug}", response=ThemeDetailSchema)
def theme_detail_page(request: HttpRequest, slug: str) -> ThemeDetailSchema:
    theme = get_object_or_404(_theme_detail_qs(), slug=slug)
    return _serialize_theme_detail(theme)


@pages_router.get("/system/{slug}", response=SystemDetailSchema)
def system_detail_page(request: HttpRequest, slug: str) -> SystemDetailSchema:
    system = get_object_or_404(_system_detail_qs(), slug=slug)
    return _serialize_system_detail(system)


# ---------------------------------------------------------------------------
# Taxonomy entities
# ---------------------------------------------------------------------------


@pages_router.get("/tag/{slug}", response=TaxonomySchema)
def tag_detail_page(request: HttpRequest, slug: str) -> TaxonomySchema:
    return _serialize_taxonomy(get_object_or_404(_taxonomy_detail_qs(Tag), slug=slug))


@pages_router.get("/cabinet/{slug}", response=TaxonomySchema)
def cabinet_detail_page(request: HttpRequest, slug: str) -> TaxonomySchema:
    return _serialize_taxonomy(
        get_object_or_404(_taxonomy_detail_qs(Cabinet), slug=slug)
    )


@pages_router.get("/display-type/{slug}", response=TaxonomySchema)
def display_type_detail_page(request: HttpRequest, slug: str) -> TaxonomySchema:
    return _serialize_taxonomy(
        get_object_or_404(_taxonomy_detail_qs(DisplayType), slug=slug)
    )


@pages_router.get("/display-subtype/{slug}", response=TaxonomySchema)
def display_subtype_detail_page(request: HttpRequest, slug: str) -> TaxonomySchema:
    return _serialize_taxonomy(
        get_object_or_404(_taxonomy_detail_qs(DisplaySubtype), slug=slug)
    )


@pages_router.get("/game-format/{slug}", response=TaxonomySchema)
def game_format_detail_page(request: HttpRequest, slug: str) -> TaxonomySchema:
    return _serialize_taxonomy(
        get_object_or_404(_taxonomy_detail_qs(GameFormat), slug=slug)
    )


@pages_router.get("/technology-generation/{slug}", response=TaxonomySchema)
def technology_generation_detail_page(
    request: HttpRequest, slug: str
) -> TaxonomySchema:
    return _serialize_taxonomy(
        get_object_or_404(_taxonomy_detail_qs(TechnologyGeneration), slug=slug)
    )


@pages_router.get("/technology-subgeneration/{slug}", response=TaxonomySchema)
def technology_subgeneration_detail_page(
    request: HttpRequest, slug: str
) -> TaxonomySchema:
    return _serialize_taxonomy(
        get_object_or_404(_taxonomy_detail_qs(TechnologySubgeneration), slug=slug)
    )


# ---------------------------------------------------------------------------
# Reward type (specialized taxonomy)
# ---------------------------------------------------------------------------


@pages_router.get("/reward-type/{slug}", response=RewardTypeDetailSchema)
def reward_type_detail_page(request: HttpRequest, slug: str) -> RewardTypeDetailSchema:
    rt = get_object_or_404(_reward_type_detail_qs(), slug=slug)
    return _serialize_reward_type_detail(rt)


# ---------------------------------------------------------------------------
# Credit role (specialized taxonomy: adds ranked people list)
# ---------------------------------------------------------------------------


@pages_router.get("/credit-role/{slug}", response=CreditRoleDetailSchema)
def credit_role_detail_page(request: HttpRequest, slug: str) -> CreditRoleDetailSchema:
    cr = get_object_or_404(_credit_role_detail_qs(), slug=slug)
    return _serialize_credit_role_detail(cr)
