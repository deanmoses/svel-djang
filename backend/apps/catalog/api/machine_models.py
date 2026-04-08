"""Models (machine models) router — list, detail, and claim-patch endpoints."""

from __future__ import annotations

from typing import Optional

from django.db.models import F, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError
from ninja.pagination import PageNumberPagination, paginate
from ninja.security import django_auth

from ..cache import MODELS_ALL_KEY, get_cached_response, set_cached_response
from .constants import DEFAULT_PAGE_SIZE
from .edit_claims import (
    execute_claims,
    plan_abbreviation_claims,
    plan_credit_claims,
    plan_gameplay_feature_claims,
    plan_m2m_claims,
    plan_scalar_field_claims,
)
from apps.provenance.helpers import build_sources, claims_prefetch

from .helpers import (
    _build_rich_text,
    _extract_image_attribution,
    _extract_image_urls,
    _extract_variant_features,
    _get_feature_descendant_slugs,
    _media_prefetch,
    _serialize_credit,
    _serialize_title_machine,
    _serialize_uploaded_media,
)
from .schemas import (
    AttributionSchema,
    ClaimSchema,
    FranchiseRefSchema,
    GameplayFeatureSchema,
    ModelClaimPatchSchema,
    ModelEditOptionsSchema,
    Ref,
    RewardTypeSchema,
    RichTextSchema,
    SeriesRefSchema,
    ThemeSchema,
    TitleMachineSchema,
    UploadedMediaSchema,
)

from collections import defaultdict

from django.db.models import Case, IntegerField, Value, When

from apps.core.licensing import get_minimum_display_rank
from apps.media.models import EntityMedia

from ..models import (
    Cabinet,
    CorporateEntity,
    CorporateEntityAlias,
    CorporateEntityLocation,
    Credit,
    CreditRole,
    DisplaySubtype,
    DisplayType,
    GameFormat,
    GameplayFeature,
    MachineModel,
    MachineModelGameplayFeature,
    ModelAbbreviation,
    Person,
    RewardType,
    System,
    Tag,
    TechnologyGeneration,
    TechnologySubgeneration,
    Theme,
)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class MachineModelGridSchema(Schema):
    name: str
    slug: str
    year: Optional[int] = None
    manufacturer_name: Optional[str] = None
    technology_generation_name: Optional[str] = None
    thumbnail_url: Optional[str] = None
    abbreviations: list[str] = []
    search_text: Optional[str] = None
    title_slug: Optional[str] = None


class MachineModelListSchema(Schema):
    name: str
    slug: str
    manufacturer: Optional[Ref] = None
    year: Optional[int] = None
    technology_generation: Optional[Ref] = None
    display_type: Optional[Ref] = None
    ipdb_id: Optional[int] = None
    ipdb_rating: Optional[float] = None
    pinside_rating: Optional[float] = None
    themes: list[ThemeSchema] = []
    thumbnail_url: Optional[str] = None


class CreditSchema(Schema):
    person: Ref
    role: str
    role_display: str
    role_sort_order: int


class VariantSchema(Schema):
    name: str
    slug: str
    year: Optional[int] = None
    variant_features: list[str] = []


class ConversionSchema(Schema):
    name: str
    slug: str
    year: Optional[int] = None


class ModelRefSchema(Schema):
    """A reference to a machine model with name, slug, and optional year."""

    name: str
    slug: str
    year: Optional[int] = None


class MachineModelDetailSchema(Schema):
    name: str
    slug: str
    manufacturer: Optional[Ref] = None
    corporate_entity: Optional[Ref] = None
    year: Optional[int] = None
    month: Optional[int] = None
    technology_generation: Optional[Ref] = None
    technology_subgeneration: Optional[Ref] = None
    display_type: Optional[Ref] = None
    player_count: Optional[int] = None
    themes: list[ThemeSchema] = []
    production_quantity: str
    system: Optional[Ref] = None
    flipper_count: Optional[int] = None
    ipdb_id: Optional[int] = None
    opdb_id: Optional[str] = None
    pinside_id: Optional[int] = None
    ipdb_rating: Optional[float] = None
    pinside_rating: Optional[float] = None
    description: RichTextSchema = RichTextSchema()
    title_description: RichTextSchema = RichTextSchema()
    abbreviations: list[str] = []
    extra_data: dict
    credits: list[CreditSchema]
    sources: list[ClaimSchema]
    thumbnail_url: Optional[str] = None
    hero_image_url: Optional[str] = None
    image_attribution: Optional[AttributionSchema] = None
    uploaded_media: list[UploadedMediaSchema] = []
    variant_features: list[str] = []
    variants: list[VariantSchema] = []
    title: Optional[Ref] = None
    cabinet: Optional[Ref] = None
    game_format: Optional[Ref] = None
    display_subtype: Optional[Ref] = None
    gameplay_features: list[GameplayFeatureSchema] = []
    tags: list[Ref] = []
    reward_types: list[RewardTypeSchema] = []
    franchise: Optional[FranchiseRefSchema] = None
    series: list[SeriesRefSchema] = []
    variant_of: Optional[ModelRefSchema] = None
    variant_siblings: list[VariantSchema] = []
    converted_from: Optional[ModelRefSchema] = None
    conversions: list[ConversionSchema] = []
    remake_of: Optional[ModelRefSchema] = None
    remakes: list[ConversionSchema] = []
    title_models: list[TitleMachineSchema] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_model_list_qs(
    manufacturer: str = "",
    type: str = "",
    subgeneration: str = "",
    display: str = "",
    display_subtype: str = "",
    feature: str = "",
    reward_type: str = "",
    game_format: str = "",
    cabinet: str = "",
    tag: str = "",
    year_min: int | None = None,
    year_max: int | None = None,
    person: str = "",
    ordering: str = "-year",
):
    qs = (
        MachineModel.objects.active()
        .select_related(
            "corporate_entity__manufacturer",
            "technology_generation",
            "display_type",
            "title",
        )
        .prefetch_related(
            "themes",
            Prefetch(
                "entity_media",
                queryset=EntityMedia.objects.filter(
                    is_primary=True,
                    asset__status="ready",
                ).select_related("asset"),
                to_attr="primary_media",
            ),
        )
        .filter(Q(variant_of__isnull=True) | Q(converted_from__isnull=False))
    )

    if manufacturer:
        qs = qs.filter(corporate_entity__manufacturer__slug=manufacturer)
    if type:
        qs = qs.filter(technology_generation__slug=type)
    if subgeneration:
        qs = qs.filter(
            Q(technology_subgeneration__slug=subgeneration)
            | Q(system__technology_subgeneration__slug=subgeneration)
        )
    if display:
        qs = qs.filter(display_type__slug=display)
    if display_subtype:
        qs = qs.filter(display_subtype__slug=display_subtype)
    if feature:
        qs = qs.filter(
            gameplay_features__slug__in=_get_feature_descendant_slugs(feature)
        )
    if reward_type:
        qs = qs.filter(reward_types__slug=reward_type)
    if game_format:
        qs = qs.filter(game_format__slug=game_format)
    if cabinet:
        qs = qs.filter(cabinet__slug=cabinet)
    if tag:
        qs = qs.filter(tags__slug=tag)
    if year_min is not None:
        qs = qs.filter(year__gte=year_min)
    if year_max is not None:
        qs = qs.filter(year__lte=year_max)
    if person:
        qs = qs.filter(credits__person__slug=person).distinct()

    ordering_map = {
        "name": [F("name").asc()],
        "-name": [F("name").desc()],
        "year": [F("year").asc(nulls_last=True)],
        "-year": [F("year").desc(nulls_last=True)],
        "-ipdb_rating": [F("ipdb_rating").desc(nulls_last=True)],
        "-pinside_rating": [F("pinside_rating").desc(nulls_last=True)],
        "ipdb_rating": [F("ipdb_rating").asc(nulls_last=True)],
        "pinside_rating": [F("pinside_rating").asc(nulls_last=True)],
    }
    order_exprs = ordering_map.get(ordering, ordering_map["-year"])
    qs = qs.order_by(*order_exprs, "name")

    return qs


def _serialize_model_list(pm, *, min_rank: int | None = None) -> dict:
    primary_media = getattr(pm, "primary_media", None)
    thumbnail_url, _ = _extract_image_urls(
        pm.extra_data or {}, primary_media, min_rank=min_rank
    )
    mfr = (
        pm.corporate_entity.manufacturer
        if pm.corporate_entity and pm.corporate_entity.manufacturer
        else None
    )
    return {
        "name": pm.name,
        "slug": pm.slug,
        "manufacturer": {"name": mfr.name, "slug": mfr.slug} if mfr else None,
        "year": pm.year,
        "technology_generation": (
            {
                "name": pm.technology_generation.name,
                "slug": pm.technology_generation.slug,
            }
            if pm.technology_generation
            else None
        ),
        "display_type": (
            {"name": pm.display_type.name, "slug": pm.display_type.slug}
            if pm.display_type
            else None
        ),
        "ipdb_id": pm.ipdb_id,
        # Note: technology_subgeneration not included in list view
        "ipdb_rating": float(pm.ipdb_rating) if pm.ipdb_rating is not None else None,
        "pinside_rating": float(pm.pinside_rating)
        if pm.pinside_rating is not None
        else None,
        "themes": [{"name": t.name, "slug": t.slug} for t in pm.themes.all()],
        "thumbnail_url": thumbnail_url,
    }


def _serialize_model_detail(pm) -> dict:
    """Serialize a MachineModel into the detail response dict.

    Expects *pm* to have been fetched with prefetch_related for credits
    (with select_related("person")) and claims (to_attr="active_claims").
    """
    min_rank = get_minimum_display_rank()

    credits = [_serialize_credit(c) for c in pm.credits.all()]

    active_claims = getattr(pm, "active_claims", None)
    if active_claims is None:
        active_claims = list(
            pm.claims.filter(is_active=True)
            .exclude(source__is_enabled=False)
            .select_related("source", "user")
            .annotate(
                effective_priority=Case(
                    When(source__isnull=False, then=F("source__priority")),
                    When(user__isnull=False, then=F("user__profile__priority")),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            )
            .order_by("claim_key", "-effective_priority", "-created_at")
        )
    sources = build_sources(active_claims)

    all_media = getattr(pm, "all_media", None) or []
    primary_media = [em for em in all_media if em.is_primary]
    thumbnail_url, hero_image_url = _extract_image_urls(
        pm.extra_data or {}, primary_media or None, min_rank=min_rank
    )
    image_attribution = _extract_image_attribution(
        pm.extra_data or {}, primary_media or None
    )
    uploaded_media = _serialize_uploaded_media(all_media)
    description = _build_rich_text(pm, "description", active_claims)
    variant_features = _extract_variant_features(pm.extra_data or {})

    variants = [
        {
            "name": v.name,
            "slug": v.slug,
            "year": v.year,
            "variant_features": _extract_variant_features(v.extra_data or {}),
        }
        for v in pm.variants.all()
    ]

    # Build sibling variants: other variants of the same parent.
    variant_siblings = []
    if pm.variant_of_id is not None:
        variant_siblings = [
            {
                "name": sib.name,
                "slug": sib.slug,
                "year": sib.year,
                "variant_features": _extract_variant_features(sib.extra_data or {}),
            }
            for sib in pm.variant_of.variants.all()
            if sib.pk != pm.pk
        ]

    # Resolve technology subgeneration: direct on model, or inherited from system.
    subgen = pm.technology_subgeneration or (
        pm.system.technology_subgeneration
        if pm.system and pm.system.technology_subgeneration
        else None
    )

    mfr = (
        pm.corporate_entity.manufacturer
        if pm.corporate_entity and pm.corporate_entity.manufacturer
        else None
    )

    return {
        "name": pm.name,
        "slug": pm.slug,
        "description": description,
        "manufacturer": {"name": mfr.name, "slug": mfr.slug} if mfr else None,
        "corporate_entity": (
            {"name": pm.corporate_entity.name, "slug": pm.corporate_entity.slug}
            if pm.corporate_entity
            else None
        ),
        "year": pm.year,
        "month": pm.month,
        "technology_generation": (
            {
                "name": pm.technology_generation.name,
                "slug": pm.technology_generation.slug,
            }
            if pm.technology_generation
            else None
        ),
        "technology_subgeneration": (
            {"name": subgen.name, "slug": subgen.slug} if subgen else None
        ),
        "display_type": (
            {"name": pm.display_type.name, "slug": pm.display_type.slug}
            if pm.display_type
            else None
        ),
        "player_count": pm.player_count,
        "themes": [{"name": t.name, "slug": t.slug} for t in pm.themes.all()],
        "production_quantity": pm.production_quantity,
        "system": (
            {"name": pm.system.name, "slug": pm.system.slug} if pm.system else None
        ),
        "flipper_count": pm.flipper_count,
        "ipdb_id": pm.ipdb_id,
        "opdb_id": pm.opdb_id,
        "pinside_id": pm.pinside_id,
        "ipdb_rating": float(pm.ipdb_rating) if pm.ipdb_rating is not None else None,
        "pinside_rating": float(pm.pinside_rating)
        if pm.pinside_rating is not None
        else None,
        "title_description": _build_rich_text(pm.title, "description")
        if pm.title
        else {},
        "abbreviations": [a.value for a in pm.abbreviations.all()],
        "extra_data": pm.extra_data or {},
        "credits": credits,
        "sources": sources,
        "thumbnail_url": thumbnail_url,
        "hero_image_url": hero_image_url,
        "image_attribution": image_attribution,
        "uploaded_media": uploaded_media,
        "variant_features": variant_features,
        "variants": variants,
        "variant_of": (
            {
                "name": pm.variant_of.name,
                "slug": pm.variant_of.slug,
                "year": pm.variant_of.year,
            }
            if pm.variant_of
            else None
        ),
        "variant_siblings": variant_siblings,
        "converted_from": (
            {
                "name": pm.converted_from.name,
                "slug": pm.converted_from.slug,
                "year": pm.converted_from.year,
            }
            if pm.converted_from
            else None
        ),
        "conversions": [
            {"name": c.name, "slug": c.slug, "year": c.year}
            for c in pm.conversions.all()
        ],
        "remake_of": (
            {
                "name": pm.remake_of.name,
                "slug": pm.remake_of.slug,
                "year": pm.remake_of.year,
            }
            if pm.remake_of
            else None
        ),
        "remakes": [
            {"name": r.name, "slug": r.slug, "year": r.year} for r in pm.remakes.all()
        ],
        "title": ({"name": pm.title.name, "slug": pm.title.slug} if pm.title else None),
        "cabinet": (
            {"name": pm.cabinet.name, "slug": pm.cabinet.slug} if pm.cabinet else None
        ),
        "game_format": (
            {"name": pm.game_format.name, "slug": pm.game_format.slug}
            if pm.game_format
            else None
        ),
        "display_subtype": (
            {"name": pm.display_subtype.name, "slug": pm.display_subtype.slug}
            if pm.display_subtype
            else None
        ),
        "gameplay_features": [
            {
                "name": t.gameplayfeature.name,
                "slug": t.gameplayfeature.slug,
                "count": t.count,
            }
            for t in pm.machinemodelgameplayfeature_set.all()
        ],
        "tags": [{"name": t.name, "slug": t.slug} for t in pm.tags.all()],
        "reward_types": [
            {"name": rt.name, "slug": rt.slug} for rt in pm.reward_types.all()
        ],
        "franchise": (
            {"name": pm.title.franchise.name, "slug": pm.title.franchise.slug}
            if pm.title and pm.title.franchise
            else None
        ),
        "series": [
            {"name": s.name, "slug": s.slug}
            for s in (pm.title.series.all() if pm.title else [])
        ],
        "title_models": [
            _serialize_title_machine(sibling, min_rank=min_rank)
            for sibling in (pm.title.machine_models.all() if pm.title else [])
            if sibling.variant_of_id is None
        ],
    }


def _model_detail_qs():
    """Return the queryset used for model detail / patch endpoints."""
    return (
        MachineModel.objects.active()
        .select_related(
            "corporate_entity__manufacturer",
            "title",
            "title__franchise",
            "system",
            "system__technology_subgeneration",
            "technology_generation",
            "technology_subgeneration",
            "display_type",
            "display_subtype",
            "cabinet",
            "game_format",
            "variant_of",
            "converted_from",
            "remake_of",
        )
        .prefetch_related(
            "variants",
            "variant_of__variants",
            "conversions",
            "remakes",
            "themes",
            Prefetch(
                "machinemodelgameplayfeature_set",
                queryset=MachineModelGameplayFeature.objects.select_related(
                    "gameplayfeature"
                ).order_by("gameplayfeature__name"),
            ),
            "tags",
            "reward_types",
            "abbreviations",
            "title__series",
            Prefetch(
                "title__machine_models",
                queryset=MachineModel.objects.active()
                .filter(Q(variant_of__isnull=True) | Q(converted_from__isnull=False))
                .select_related(
                    "corporate_entity__manufacturer", "technology_generation"
                )
                .prefetch_related("variants")
                .order_by("year", "name"),
            ),
            Prefetch(
                "credits",
                queryset=Credit.objects.filter(model__isnull=False).select_related(
                    "person", "role"
                ),
            ),
            claims_prefetch(),
            _media_prefetch(),
        )
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

models_router = Router(tags=["models"])


@models_router.get("/", response=list[MachineModelListSchema])
@paginate(PageNumberPagination, page_size=DEFAULT_PAGE_SIZE)
def list_models(
    request,
    manufacturer: str = "",
    type: str = "",
    subgeneration: str = "",
    display: str = "",
    display_subtype: str = "",
    feature: str = "",
    reward_type: str = "",
    game_format: str = "",
    cabinet: str = "",
    tag: str = "",
    year_min: int | None = None,
    year_max: int | None = None,
    person: str = "",
    ordering: str = "-year",
):
    qs = _build_model_list_qs(
        manufacturer=manufacturer,
        type=type,
        subgeneration=subgeneration,
        display=display,
        display_subtype=display_subtype,
        feature=feature,
        reward_type=reward_type,
        game_format=game_format,
        cabinet=cabinet,
        tag=tag,
        year_min=year_min,
        year_max=year_max,
        person=person,
        ordering=ordering,
    )
    min_rank = get_minimum_display_rank()
    return [_serialize_model_list(pm, min_rank=min_rank) for pm in qs]


def _build_search_text(pm) -> str:
    """Build a pipe-separated search text from all related entity names."""
    parts: list[str] = []
    if pm.corporate_entity and pm.corporate_entity.manufacturer:
        mfr = pm.corporate_entity.manufacturer
        parts.append(mfr.name)
        for entity in mfr.entities.all():
            parts.append(entity.name)
            for cel in entity.locations.all():
                loc = cel.location
                while loc is not None:
                    if loc.name:
                        parts.append(loc.name)
                    loc = loc.parent
    if pm.system:
        parts.append(pm.system.name)
    if pm.technology_generation:
        parts.append(pm.technology_generation.name)
    if pm.display_type:
        parts.append(pm.display_type.name)
    if pm.display_subtype:
        parts.append(pm.display_subtype.name)
    if pm.cabinet:
        parts.append(pm.cabinet.name)
    if pm.game_format:
        parts.append(pm.game_format.name)
    for theme in pm.themes.all():
        parts.append(theme.name)
    for tag in pm.tags.all():
        parts.append(tag.name)
    for gf in pm.gameplay_features.all():
        parts.append(gf.name)
    for credit in pm.credits.all():
        parts.append(credit.person.name)
    for abbr in pm.abbreviations.all():
        parts.append(abbr.value)
    return " | ".join(parts)


class ModelRecentSchema(Schema):
    name: str
    slug: str
    manufacturer_name: Optional[str] = None
    year: Optional[int] = None
    thumbnail_url: Optional[str] = None


@models_router.get("/recent/", response=list[ModelRecentSchema])
@decorate_view(cache_control(no_cache=True))
def list_recent_models(request):
    """Return the 3 newest non-variant models, one per title."""
    qs = (
        MachineModel.objects.active()
        .filter(Q(variant_of__isnull=True) | Q(converted_from__isnull=False))
        .select_related("corporate_entity__manufacturer")
        .order_by(
            F("year").desc(nulls_last=True),
            F("month").desc(nulls_last=True),
            "-updated_at",
        )[:20]  # generous LIMIT — we only need 3 unique titles
    )
    min_rank = get_minimum_display_rank()
    results = []
    seen_titles: set[int | None] = set()
    for m in qs:
        title_id = m.title_id
        if title_id in seen_titles:
            continue
        seen_titles.add(title_id)
        thumbnail_url, _ = _extract_image_urls(m.extra_data or {}, min_rank=min_rank)
        results.append(
            {
                "name": m.name,
                "slug": m.slug,
                "manufacturer_name": (
                    m.corporate_entity.manufacturer.name
                    if m.corporate_entity and m.corporate_entity.manufacturer
                    else None
                ),
                "year": m.year,
                "thumbnail_url": thumbnail_url,
            }
        )
        if len(results) == 3:
            break
    return results


@models_router.get("/all/", response=list[MachineModelGridSchema])
@decorate_view(cache_control(no_cache=True))
def list_all_models(request):
    """Return every model (including variants) for client-side search/grid.

    Performance-critical: serializes ~7k models with search_text built from
    M2M relations.  Uses ``values_list`` to avoid ORM object hydration and
    bulk through-table queries for M2M data.  See ``list_all_titles`` for
    the full explanation of this pattern.
    """
    response = get_cached_response(MODELS_ALL_KEY)
    if response is not None:
        return response

    min_rank = get_minimum_display_rank()

    # Column indices for the values_list below.
    M_ID = 0
    M_NAME = 1
    M_SLUG = 2
    M_YEAR = 3
    M_EXTRA_DATA = 4
    M_MFR_ID = 5
    M_MFR_NAME = 6
    M_TECH_GEN_NAME = 7
    M_DISPLAY_TYPE_NAME = 8
    M_DISPLAY_SUBTYPE_NAME = 9
    M_TITLE_SLUG = 10
    M_SYSTEM_NAME = 11
    M_CABINET_NAME = 12
    M_GAME_FORMAT_NAME = 13

    rows = list(
        MachineModel.objects.active()
        .values_list(
            "id",
            "name",
            "slug",
            "year",
            "extra_data",
            "corporate_entity__manufacturer__id",
            "corporate_entity__manufacturer__name",
            "technology_generation__name",
            "display_type__name",
            "display_subtype__name",
            "title__slug",
            "system__name",
            "cabinet__name",
            "game_format__name",
        )
        .order_by("name")
    )
    model_ids = {r[M_ID] for r in rows}

    # --- Bulk M2M queries for search_text ---
    model_themes: dict[int, list[str]] = defaultdict(list)
    for mid, name in MachineModel.themes.through.objects.filter(
        machinemodel_id__in=model_ids
    ).values_list("machinemodel_id", "theme__name"):
        model_themes[mid].append(name)

    model_tags: dict[int, list[str]] = defaultdict(list)
    for mid, name in MachineModel.tags.through.objects.filter(
        machinemodel_id__in=model_ids
    ).values_list("machinemodel_id", "tag__name"):
        model_tags[mid].append(name)

    model_gf: dict[int, list[str]] = defaultdict(list)
    for mid, name in MachineModel.gameplay_features.through.objects.filter(
        machinemodel_id__in=model_ids
    ).values_list("machinemodel_id", "gameplayfeature__name"):
        model_gf[mid].append(name)

    model_credits: dict[int, list[str]] = defaultdict(list)
    for mid, name in Credit.objects.filter(model_id__in=model_ids).values_list(
        "model_id", "person__name"
    ):
        model_credits[mid].append(name)

    model_abbrevs: dict[int, list[str]] = defaultdict(list)
    for mid, value in ModelAbbreviation.objects.filter(
        machine_model_id__in=model_ids
    ).values_list("machine_model_id", "value"):
        model_abbrevs[mid].append(value)

    # --- Bulk manufacturer search text (entity names, aliases, locations) ---
    # Build manufacturer_id → search parts map
    mfr_search_parts: dict[int, list[str]] = defaultdict(list)

    # Entity names
    for mfr_id, ename in CorporateEntity.objects.active().values_list(
        "manufacturer_id", "name"
    ):
        if mfr_id:
            mfr_search_parts[mfr_id].append(ename)

    # Entity aliases
    for mfr_id, aval in CorporateEntityAlias.objects.filter(
        corporate_entity__manufacturer__isnull=False
    ).values_list("corporate_entity__manufacturer_id", "value"):
        mfr_search_parts[mfr_id].append(aval)

    # Location names (walk hierarchy via pre-fetched chain)
    for mfr_id, loc_name, p1, p2, p3, p4 in (
        CorporateEntityLocation.objects.filter(
            corporate_entity__manufacturer__isnull=False
        )
        .select_related("location__parent__parent__parent__parent")
        .values_list(
            "corporate_entity__manufacturer_id",
            "location__name",
            "location__parent__name",
            "location__parent__parent__name",
            "location__parent__parent__parent__name",
            "location__parent__parent__parent__parent__name",
        )
    ):
        for n in (loc_name, p1, p2, p3, p4):
            if n:
                mfr_search_parts[mfr_id].append(n)

    # --- Assembly ---
    result = []
    for r in rows:
        mid = r[M_ID]
        extra_data = r[M_EXTRA_DATA]
        thumbnail_url, _ = _extract_image_urls(extra_data or {}, min_rank=min_rank)

        # Build search_text from bulk maps
        parts: list[str] = []
        mfr_id, mfr_name = r[M_MFR_ID], r[M_MFR_NAME]
        if mfr_name:
            parts.append(mfr_name)
            parts.extend(mfr_search_parts.get(mfr_id, []))
        for name in (
            r[M_SYSTEM_NAME],
            r[M_TECH_GEN_NAME],
            r[M_DISPLAY_TYPE_NAME],
            r[M_DISPLAY_SUBTYPE_NAME],
            r[M_CABINET_NAME],
            r[M_GAME_FORMAT_NAME],
        ):
            if name:
                parts.append(name)
        parts.extend(model_themes.get(mid, []))
        parts.extend(model_tags.get(mid, []))
        parts.extend(model_gf.get(mid, []))
        parts.extend(model_credits.get(mid, []))
        parts.extend(model_abbrevs.get(mid, []))

        result.append(
            {
                "name": r[M_NAME],
                "slug": r[M_SLUG],
                "year": r[M_YEAR],
                "manufacturer_name": mfr_name,
                "technology_generation_name": r[M_TECH_GEN_NAME],
                "thumbnail_url": thumbnail_url,
                "abbreviations": model_abbrevs.get(mid, []),
                "search_text": " | ".join(parts) if parts else None,
                "title_slug": r[M_TITLE_SLUG],
            }
        )
    return set_cached_response(MODELS_ALL_KEY, result)


@models_router.get("/edit-options/", response=ModelEditOptionsSchema)
@decorate_view(cache_control(no_cache=True))
def get_model_edit_options(request):
    """Return all dropdown options for the MachineModel edit form."""

    def _opts(qs):
        return [{"slug": obj.slug, "label": obj.name} for obj in qs]

    return {
        "themes": _opts(Theme.objects.active().order_by("name")),
        "tags": _opts(Tag.objects.active().order_by("name")),
        "reward_types": _opts(
            RewardType.objects.active().order_by("display_order", "name")
        ),
        "gameplay_features": _opts(GameplayFeature.objects.active().order_by("name")),
        "technology_generations": _opts(
            TechnologyGeneration.objects.active().order_by("display_order", "name")
        ),
        "technology_subgenerations": _opts(
            TechnologySubgeneration.objects.active().order_by("display_order", "name")
        ),
        "display_types": _opts(
            DisplayType.objects.active().order_by("display_order", "name")
        ),
        "display_subtypes": _opts(
            DisplaySubtype.objects.active().order_by("display_order", "name")
        ),
        "cabinets": _opts(Cabinet.objects.active().order_by("display_order", "name")),
        "game_formats": _opts(
            GameFormat.objects.active().order_by("display_order", "name")
        ),
        "systems": _opts(System.objects.active().order_by("name")),
        "corporate_entities": _opts(CorporateEntity.objects.active().order_by("name")),
        "people": _opts(Person.objects.active().order_by("name")),
        "credit_roles": _opts(
            CreditRole.objects.active().order_by("display_order", "name")
        ),
        "models": [
            {
                "slug": obj.slug,
                "label": f"{obj.name} ({obj.year})" if obj.year else obj.name,
            }
            for obj in MachineModel.objects.active().order_by("name")
        ],
    }


_SELF_REF_FIELDS = frozenset({"variant_of", "converted_from", "remake_of"})


@models_router.patch(
    "/{slug}/claims/",
    auth=django_auth,
    response=MachineModelDetailSchema,
    tags=["private"],
)
def patch_model_claims(request, slug: str, data: ModelClaimPatchSchema):
    """Assert per-field claims from the authenticated user, then re-resolve the model."""
    pm = get_object_or_404(
        MachineModel.objects.active().prefetch_related(
            "themes",
            "tags",
            "reward_types",
            "machinemodelgameplayfeature_set__gameplayfeature",
            "abbreviations",
            "credits__person",
            "credits__role",
        ),
        slug=slug,
    )

    specs = (
        plan_scalar_field_claims(MachineModel, data.fields, entity=pm)
        if data.fields
        else []
    )

    for field_name, value in data.fields.items():
        if field_name in _SELF_REF_FIELDS and value == slug:
            raise HttpError(
                422, f"Field '{field_name}' cannot reference the model itself."
            )

    if data.themes is not None:
        specs.extend(
            plan_m2m_claims(
                pm,
                set(data.themes),
                target_model=Theme,
                claim_field_name="theme",
                m2m_attr="themes",
            )
        )
    if data.tags is not None:
        specs.extend(
            plan_m2m_claims(
                pm,
                set(data.tags),
                target_model=Tag,
                claim_field_name="tag",
                m2m_attr="tags",
            )
        )
    if data.reward_types is not None:
        specs.extend(
            plan_m2m_claims(
                pm,
                set(data.reward_types),
                target_model=RewardType,
                claim_field_name="reward_type",
                m2m_attr="reward_types",
            )
        )
    if data.gameplay_features is not None:
        specs.extend(plan_gameplay_feature_claims(pm, data.gameplay_features))
    if data.credits is not None:
        specs.extend(plan_credit_claims(pm, data.credits))
    if data.abbreviations is not None:
        specs.extend(plan_abbreviation_claims(pm, data.abbreviations))

    if not specs:
        raise HttpError(422, "No changes provided.")

    execute_claims(pm, specs, user=request.user, note=data.note, citation=data.citation)

    pm = get_object_or_404(_model_detail_qs(), slug=pm.slug)
    return _serialize_model_detail(pm)
