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

from apps.core.markdown import render_markdown_fields

from ..cache import MODELS_ALL_KEY, invalidate_all
from .constants import DEFAULT_PAGE_SIZE
from .helpers import (
    _build_activity,
    _claims_prefetch,
    _extract_image_urls,
    _extract_variant_features,
    _serialize_title_machine,
)
from .schemas import (
    ClaimPatchSchema,
    ClaimSchema,
    FranchiseRefSchema,
    GameplayFeatureSchema,
    SeriesRefSchema,
    ThemeSchema,
    TitleMachineSchema,
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
    manufacturer_name: Optional[str] = None
    manufacturer_slug: Optional[str] = None
    year: Optional[int] = None
    technology_generation_name: Optional[str] = None
    technology_generation_slug: Optional[str] = None
    display_type_name: Optional[str] = None
    display_type_slug: Optional[str] = None
    ipdb_id: Optional[int] = None
    ipdb_rating: Optional[float] = None
    pinside_rating: Optional[float] = None
    themes: list[ThemeSchema] = []
    thumbnail_url: Optional[str] = None


class CreditSchema(Schema):
    person_name: str
    person_slug: str
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


class MachineModelDetailSchema(Schema):
    name: str
    slug: str
    manufacturer_name: Optional[str] = None
    manufacturer_slug: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    technology_generation_name: Optional[str] = None
    technology_generation_slug: Optional[str] = None
    technology_subgeneration_name: Optional[str] = None
    technology_subgeneration_slug: Optional[str] = None
    display_type_name: Optional[str] = None
    display_type_slug: Optional[str] = None
    player_count: Optional[int] = None
    themes: list[ThemeSchema] = []
    production_quantity: str
    system_name: Optional[str] = None
    system_slug: Optional[str] = None
    flipper_count: Optional[int] = None
    ipdb_id: Optional[int] = None
    opdb_id: Optional[str] = None
    pinside_id: Optional[int] = None
    ipdb_rating: Optional[float] = None
    pinside_rating: Optional[float] = None
    description: str = ""
    description_html: str = ""
    title_description: str = ""
    abbreviations: list[str] = []
    extra_data: dict
    credits: list[CreditSchema]
    activity: list[ClaimSchema]
    thumbnail_url: Optional[str] = None
    hero_image_url: Optional[str] = None
    variant_features: list[str] = []
    variants: list[VariantSchema] = []
    title_name: Optional[str] = None
    title_slug: Optional[str] = None
    cabinet_name: Optional[str] = None
    cabinet_slug: Optional[str] = None
    game_format_name: Optional[str] = None
    game_format_slug: Optional[str] = None
    display_subtype_name: Optional[str] = None
    display_subtype_slug: Optional[str] = None
    gameplay_features: list[GameplayFeatureSchema] = []
    franchise: Optional[FranchiseRefSchema] = None
    series: list[SeriesRefSchema] = []
    variant_of_name: Optional[str] = None
    variant_of_slug: Optional[str] = None
    variant_of_year: Optional[int] = None
    variant_siblings: list[VariantSchema] = []
    is_conversion: bool = False
    converted_from_name: Optional[str] = None
    converted_from_slug: Optional[str] = None
    converted_from_year: Optional[int] = None
    conversions: list[ConversionSchema] = []
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
    game_format: str = "",
    cabinet: str = "",
    tag: str = "",
    year_min: int | None = None,
    year_max: int | None = None,
    person: str = "",
    ordering: str = "-year",
):
    from ..models import MachineModel

    qs = (
        MachineModel.objects.select_related(
            "corporate_entity__manufacturer",
            "technology_generation",
            "display_type",
            "title",
        )
        .prefetch_related("themes")
        .filter(variant_of__isnull=True)
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
        qs = qs.filter(gameplay_features__slug=feature)
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


def _serialize_model_list(pm) -> dict:
    thumbnail_url, _ = _extract_image_urls(pm.extra_data or {})
    return {
        "name": pm.name,
        "slug": pm.slug,
        "manufacturer_name": (
            pm.corporate_entity.manufacturer.name
            if pm.corporate_entity and pm.corporate_entity.manufacturer
            else None
        ),
        "manufacturer_slug": (
            pm.corporate_entity.manufacturer.slug
            if pm.corporate_entity and pm.corporate_entity.manufacturer
            else None
        ),
        "year": pm.year,
        "technology_generation_name": (
            pm.technology_generation.name if pm.technology_generation else None
        ),
        "technology_generation_slug": (
            pm.technology_generation.slug if pm.technology_generation else None
        ),
        "display_type_name": pm.display_type.name if pm.display_type else None,
        "display_type_slug": pm.display_type.slug if pm.display_type else None,
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
    from django.db.models import Case, F, IntegerField, Value, When

    credits = [
        {
            "person_name": c.person.name,
            "person_slug": c.person.slug,
            "role": c.role.slug,
            "role_display": c.role.name,
            "role_sort_order": c.role.display_order,
        }
        for c in pm.credits.all()
    ]

    activity_claims = getattr(pm, "active_claims", None)
    if activity_claims is None:
        activity_claims = list(
            pm.claims.filter(is_active=True)
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
    activity = _build_activity(activity_claims)

    thumbnail_url, hero_image_url = _extract_image_urls(pm.extra_data or {})
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

    return {
        "name": pm.name,
        "slug": pm.slug,
        "description": pm.description,
        **render_markdown_fields(pm),
        "manufacturer_name": (
            pm.corporate_entity.manufacturer.name
            if pm.corporate_entity and pm.corporate_entity.manufacturer
            else None
        ),
        "manufacturer_slug": (
            pm.corporate_entity.manufacturer.slug
            if pm.corporate_entity and pm.corporate_entity.manufacturer
            else None
        ),
        "year": pm.year,
        "month": pm.month,
        "technology_generation_name": (
            pm.technology_generation.name if pm.technology_generation else None
        ),
        "technology_generation_slug": (
            pm.technology_generation.slug if pm.technology_generation else None
        ),
        "technology_subgeneration_name": (
            pm.technology_subgeneration.name
            if pm.technology_subgeneration
            else (
                pm.system.technology_subgeneration.name
                if pm.system and pm.system.technology_subgeneration
                else None
            )
        ),
        "technology_subgeneration_slug": (
            pm.technology_subgeneration.slug
            if pm.technology_subgeneration
            else (
                pm.system.technology_subgeneration.slug
                if pm.system and pm.system.technology_subgeneration
                else None
            )
        ),
        "display_type_name": pm.display_type.name if pm.display_type else None,
        "display_type_slug": pm.display_type.slug if pm.display_type else None,
        "player_count": pm.player_count,
        "themes": [{"name": t.name, "slug": t.slug} for t in pm.themes.all()],
        "production_quantity": pm.production_quantity,
        "system_name": pm.system.name if pm.system else None,
        "system_slug": pm.system.slug if pm.system else None,
        "flipper_count": pm.flipper_count,
        "ipdb_id": pm.ipdb_id,
        "opdb_id": pm.opdb_id,
        "pinside_id": pm.pinside_id,
        "ipdb_rating": float(pm.ipdb_rating) if pm.ipdb_rating is not None else None,
        "pinside_rating": float(pm.pinside_rating)
        if pm.pinside_rating is not None
        else None,
        "title_description": pm.title.description if pm.title else "",
        "abbreviations": [a.value for a in pm.abbreviations.all()],
        "extra_data": pm.extra_data or {},
        "credits": credits,
        "activity": activity,
        "thumbnail_url": thumbnail_url,
        "hero_image_url": hero_image_url,
        "variant_features": variant_features,
        "variants": variants,
        "variant_of_name": pm.variant_of.name if pm.variant_of else None,
        "variant_of_slug": pm.variant_of.slug if pm.variant_of else None,
        "variant_of_year": pm.variant_of.year if pm.variant_of else None,
        "variant_siblings": variant_siblings,
        "is_conversion": pm.is_conversion,
        "converted_from_name": pm.converted_from.name if pm.converted_from else None,
        "converted_from_slug": pm.converted_from.slug if pm.converted_from else None,
        "converted_from_year": pm.converted_from.year if pm.converted_from else None,
        "conversions": [
            {"name": c.name, "slug": c.slug, "year": c.year}
            for c in pm.conversions.all()
        ],
        "title_name": pm.title.name if pm.title else None,
        "title_slug": pm.title.slug if pm.title else None,
        "cabinet_name": pm.cabinet.name if pm.cabinet else None,
        "cabinet_slug": pm.cabinet.slug if pm.cabinet else None,
        "game_format_name": pm.game_format.name if pm.game_format else None,
        "game_format_slug": pm.game_format.slug if pm.game_format else None,
        "display_subtype_name": (
            pm.display_subtype.name if pm.display_subtype else None
        ),
        "display_subtype_slug": (
            pm.display_subtype.slug if pm.display_subtype else None
        ),
        "gameplay_features": [
            {"name": gf.name, "slug": gf.slug} for gf in pm.gameplay_features.all()
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
            _serialize_title_machine(sibling)
            for sibling in (pm.title.machine_models.all() if pm.title else [])
            if sibling.variant_of_id is None
        ],
    }


def _model_detail_qs():
    """Return the queryset used for model detail / patch endpoints."""
    from ..models import Credit, MachineModel

    return MachineModel.objects.select_related(
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
    ).prefetch_related(
        "variants",
        "variant_of__variants",
        "conversions",
        "themes",
        "gameplay_features",
        "abbreviations",
        "title__series",
        Prefetch(
            "title__machine_models",
            queryset=MachineModel.objects.filter(variant_of__isnull=True)
            .select_related("corporate_entity__manufacturer", "technology_generation")
            .prefetch_related("variants")
            .order_by("year", "name"),
        ),
        Prefetch(
            "credits",
            queryset=Credit.objects.filter(model__isnull=False).select_related(
                "person", "role"
            ),
        ),
        _claims_prefetch(),
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
        game_format=game_format,
        cabinet=cabinet,
        tag=tag,
        year_min=year_min,
        year_max=year_max,
        person=person,
        ordering=ordering,
    )
    return [_serialize_model_list(pm) for pm in qs]


def _build_search_text(pm) -> str:
    """Build a pipe-separated search text from all related entity names."""
    parts: list[str] = []
    if pm.corporate_entity and pm.corporate_entity.manufacturer:
        mfr = pm.corporate_entity.manufacturer
        parts.append(mfr.name)
        for entity in mfr.entities.all():
            parts.append(entity.name)
            for addr in entity.addresses.all():
                if addr.city:
                    parts.append(addr.city)
                if addr.state:
                    parts.append(addr.state)
                if addr.country:
                    parts.append(addr.country)
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
@decorate_view(cache_control(public=True, max_age=300))
def list_recent_models(request):
    """Return the 3 newest non-variant models, one per title."""
    from ..models import MachineModel

    qs = (
        MachineModel.objects.filter(variant_of__isnull=True)
        .select_related("corporate_entity__manufacturer")
        .order_by(
            F("year").desc(nulls_last=True),
            F("month").desc(nulls_last=True),
            "-updated_at",
        )
    )
    results = []
    seen_titles: set[int | None] = set()
    for m in qs:
        title_id = m.title_id
        if title_id in seen_titles:
            continue
        seen_titles.add(title_id)
        thumbnail_url, _ = _extract_image_urls(m.extra_data or {})
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
@decorate_view(cache_control(public=True, max_age=300))
def list_all_models(request):
    """Return every model (including variants) with minimal fields (no pagination)."""
    from django.core.cache import cache

    from ..models import Credit, MachineModel

    result = cache.get(MODELS_ALL_KEY)
    if result is not None:
        return result
    qs = (
        MachineModel.objects.select_related(
            "corporate_entity__manufacturer",
            "technology_generation",
            "technology_subgeneration",
            "display_type",
            "title",
            "system",
            "display_subtype",
            "cabinet",
            "game_format",
        )
        .prefetch_related(
            "themes",
            "tags",
            "gameplay_features",
            "variants",
            "abbreviations",
            "corporate_entity__manufacturer__entities__addresses",
            Prefetch(
                "credits",
                queryset=Credit.objects.filter(model__isnull=False).select_related(
                    "person", "role"
                ),
            ),
        )
        .order_by("name")
    )
    result = []
    for pm in qs:
        thumbnail_url, _ = _extract_image_urls(pm.extra_data or {})
        result.append(
            {
                "name": pm.name,
                "slug": pm.slug,
                "year": pm.year,
                "manufacturer_name": (
                    pm.corporate_entity.manufacturer.name
                    if pm.corporate_entity and pm.corporate_entity.manufacturer
                    else None
                ),
                "technology_generation_name": (
                    pm.technology_generation.name if pm.technology_generation else None
                ),
                "thumbnail_url": thumbnail_url,
                "abbreviations": [a.value for a in pm.abbreviations.all()],
                "search_text": _build_search_text(pm),
                "title_slug": pm.title.slug if pm.title else None,
            }
        )
    cache.set(MODELS_ALL_KEY, result, timeout=None)
    return result


@models_router.get("/{slug}", response=MachineModelDetailSchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_model(request, slug: str):
    pm = get_object_or_404(_model_detail_qs(), slug=slug)
    return _serialize_model_detail(pm)


@models_router.patch(
    "/{slug}/claims/",
    auth=django_auth,
    response=MachineModelDetailSchema,
    tags=["private"],
)
def patch_model_claims(request, slug: str, data: ClaimPatchSchema):
    """Assert per-field claims from the authenticated user, then re-resolve the model."""
    from apps.provenance.models import Claim

    from ..models import MachineModel
    from ..resolve import DIRECT_FIELDS, resolve_model

    editable_fields = set(DIRECT_FIELDS.keys())
    unknown = set(data.fields.keys()) - editable_fields
    if unknown:
        raise HttpError(422, f"Unknown or non-editable fields: {sorted(unknown)}")

    pm = get_object_or_404(MachineModel, slug=slug)

    for field_name, value in data.fields.items():
        Claim.objects.assert_claim(pm, field_name, value, user=request.user)

    resolve_model(pm)
    invalidate_all()

    pm = get_object_or_404(_model_detail_qs(), slug=slug)
    return _serialize_model_detail(pm)
