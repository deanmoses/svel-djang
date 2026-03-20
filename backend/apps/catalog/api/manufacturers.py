"""Manufacturers router — list, detail, and claim-patch endpoints."""

from __future__ import annotations

from typing import Optional

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models import Count, F, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError
from ninja.pagination import PageNumberPagination, paginate
from ninja.security import django_auth

from django.utils.text import slugify

from ..cache import MANUFACTURERS_ALL_KEY, invalidate_all
from .constants import DEFAULT_PAGE_SIZE
from .helpers import _build_activity, _claims_prefetch, _extract_image_urls
from .schemas import ClaimPatchSchema, ClaimSchema, RelatedTitleSchema
from .titles import FacetRef, _dedup_facet_refs

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ManufacturerGridSchema(Schema):
    name: str
    slug: str
    model_count: int = 0
    thumbnail_url: Optional[str] = None
    search_text: Optional[str] = None
    locations: list[FacetRef] = []
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    persons: list[FacetRef] = []
    tech_generations: list[FacetRef] = []


class ManufacturerSchema(Schema):
    name: str
    slug: str
    model_count: int = 0


class AddressSchema(Schema):
    city: str
    state: str
    country: str


class CorporateEntitySchema(Schema):
    name: str
    slug: str
    year_start: int | None
    year_end: int | None
    addresses: list[AddressSchema]


class SystemSchema(Schema):
    name: str
    slug: str


class ManufacturerDetailSchema(Schema):
    name: str
    slug: str
    description: str = ""
    description_html: str = ""
    year_start: int | None = None
    year_end: int | None = None
    country: str | None = None
    headquarters: str | None = None
    logo_url: str | None = None
    website: str = ""
    entities: list[CorporateEntitySchema]
    titles: list[RelatedTitleSchema]
    systems: list[SystemSchema]
    activity: list[ClaimSchema]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_titles(models, *, include_manufacturer: bool = False) -> list[dict]:
    """Group models by title into a deduplicated title list."""
    titles: dict[str, dict] = {}
    for m in models:
        if m.title is None:
            continue
        key = m.title.slug
        if key not in titles:
            thumbnail_url = _extract_image_urls(m.extra_data or {})[0]
            entry: dict = {
                "name": m.title.name,
                "slug": m.title.slug,
                "year": m.year,
                "thumbnail_url": thumbnail_url,
            }
            if include_manufacturer:
                entry["manufacturer_name"] = (
                    m.corporate_entity.manufacturer.name
                    if m.corporate_entity and m.corporate_entity.manufacturer
                    else None
                )
            titles[key] = entry
        elif titles[key]["thumbnail_url"] is None:
            thumbnail_url = _extract_image_urls(m.extra_data or {})[0]
            if thumbnail_url:
                titles[key]["thumbnail_url"] = thumbnail_url
    return sorted(titles.values(), key=lambda t: (t["year"] is None, -(t["year"] or 0)))


def _serialize_manufacturer_detail(mfr) -> dict:
    """Serialize a Manufacturer into the detail response dict.

    Expects *mfr* to have been fetched with prefetch_related for entities,
    non_variant_models, and claims (to_attr="active_claims").
    """
    from apps.core.markdown import render_markdown_fields

    return {
        "name": mfr.name,
        "slug": mfr.slug,
        "description": mfr.description,
        **render_markdown_fields(mfr),
        "logo_url": mfr.logo_url,
        "website": mfr.website,
        "entities": [
            {
                "name": e.name,
                "slug": e.slug,
                "year_start": e.year_start,
                "year_end": e.year_end,
                "addresses": [
                    {"city": a.city, "state": a.state, "country": a.country}
                    for a in e.addresses.all()
                ],
            }
            for e in mfr.entities.all()
        ],
        "titles": _collect_titles(
            m for e in mfr.entities.all() for m in e.models.all()
        ),
        "systems": [{"name": s.name, "slug": s.slug} for s in mfr.systems.all()],
        "activity": _build_activity(getattr(mfr, "active_claims", [])),
    }


def _manufacturer_qs():
    from ..models import CorporateEntity, MachineModel, Manufacturer, System

    return Manufacturer.objects.prefetch_related(
        Prefetch(
            "entities",
            queryset=CorporateEntity.objects.prefetch_related(
                "addresses",
                Prefetch(
                    "models",
                    queryset=MachineModel.objects.filter(variant_of__isnull=True)
                    .select_related("technology_generation", "title")
                    .order_by(F("year").desc(nulls_last=True), "name"),
                ),
            ).order_by("year_start"),
        ),
        Prefetch("systems", queryset=System.objects.order_by("name")),
        _claims_prefetch(),
    )


def _build_location_refs(entities) -> list[dict]:
    """Build composite location FacetRefs at every granularity level.

    For an address with city="Chicago", state="Illinois", country="USA",
    emits three refs:
      - "Chicago, Illinois, USA"
      - "Illinois, USA"
      - "USA"
    """
    refs: dict[str, str] = {}  # slug -> display name
    for entity in entities:
        for addr in entity.addresses.all():
            parts = []
            if addr.city:
                parts.append(addr.city)
            if addr.state:
                parts.append(addr.state)
            if addr.country:
                parts.append(addr.country)
            # Emit a ref for each suffix: [city,state,country], [state,country], [country]
            for i in range(len(parts)):
                name = ", ".join(parts[i:])
                slug = slugify(name)
                if slug and slug not in refs:
                    refs[slug] = name
    return [{"slug": s, "name": n} for s, n in refs.items()]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

manufacturers_router = Router(tags=["manufacturers"])


@manufacturers_router.get("/", response=list[ManufacturerSchema])
@paginate(PageNumberPagination, page_size=DEFAULT_PAGE_SIZE)
def list_manufacturers(request):
    from ..models import Manufacturer

    return list(
        Manufacturer.objects.annotate(model_count=Count("entities__models"))
        .order_by("name")
        .values("name", "slug", "model_count")
    )


@manufacturers_router.get("/all/", response=list[ManufacturerGridSchema])
@decorate_view(cache_control(public=True, max_age=300))
def list_all_manufacturers(request):
    """Return every manufacturer with model count and thumbnail (no pagination)."""
    result = cache.get(MANUFACTURERS_ALL_KEY)
    if result is not None:
        return result

    from ..models import MachineModel, Manufacturer

    from ..models import CorporateEntity

    qs = (
        Manufacturer.objects.annotate(
            model_count=Count(
                "entities__models",
                filter=Q(entities__models__variant_of__isnull=True),
            )
        )
        .prefetch_related(
            Prefetch(
                "entities",
                queryset=CorporateEntity.objects.prefetch_related(
                    "addresses",
                    Prefetch(
                        "models",
                        queryset=MachineModel.objects.filter(variant_of__isnull=True)
                        .select_related("technology_generation")
                        .prefetch_related("credits__person")
                        .order_by(F("year").desc(nulls_last=True)),
                    ),
                ),
            ),
        )
        .order_by("-model_count")
    )

    result = []
    for mfr in qs:
        thumb = None
        search_parts: list[str] = []
        tech_gen_pairs: list[tuple[str, str]] = []
        person_pairs: list[tuple[str, str]] = []

        model_years: list[int] = []

        for entity in mfr.entities.all():
            search_parts.append(entity.name)
            for addr in entity.addresses.all():
                if addr.city:
                    search_parts.append(addr.city)
                if addr.state:
                    search_parts.append(addr.state)
                if addr.country:
                    search_parts.append(addr.country)
            for model in entity.models.all():
                if thumb is None and model.extra_data:
                    thumb, _ = _extract_image_urls(model.extra_data)
                if model.year is not None:
                    model_years.append(model.year)
                if model.technology_generation:
                    tg = model.technology_generation
                    tech_gen_pairs.append((tg.slug, tg.name))
                for credit in model.credits.all():
                    person_pairs.append((credit.person.slug, credit.person.name))

        result.append(
            {
                "name": mfr.name,
                "slug": mfr.slug,
                "model_count": mfr.model_count,
                "thumbnail_url": thumb,
                "search_text": " | ".join(search_parts) if search_parts else None,
                "locations": _build_location_refs(mfr.entities.all()),
                "year_min": min(model_years) if model_years else None,
                "year_max": max(model_years) if model_years else None,
                "persons": _dedup_facet_refs(person_pairs),
                "tech_generations": _dedup_facet_refs(tech_gen_pairs),
            }
        )
    cache.set(MANUFACTURERS_ALL_KEY, result, timeout=None)
    return result


@manufacturers_router.get("/{slug}", response=ManufacturerDetailSchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_manufacturer(request, slug: str):
    mfr = get_object_or_404(_manufacturer_qs(), slug=slug)
    return _serialize_manufacturer_detail(mfr)


@manufacturers_router.patch(
    "/{slug}/claims/",
    auth=django_auth,
    response=ManufacturerDetailSchema,
    tags=["private"],
)
def patch_manufacturer_claims(request, slug: str, data: ClaimPatchSchema):
    """Assert per-field claims from the authenticated user, then re-resolve."""
    from apps.core.markdown_links import prepare_markdown_claim_value
    from apps.provenance.models import Claim

    from ..models import Manufacturer
    from ..resolve import MANUFACTURER_DIRECT_FIELDS, resolve_manufacturer

    editable_fields = set(MANUFACTURER_DIRECT_FIELDS.keys())
    unknown = set(data.fields.keys()) - editable_fields
    if unknown:
        raise HttpError(422, f"Unknown or non-editable fields: {sorted(unknown)}")

    mfr = get_object_or_404(Manufacturer, slug=slug)

    for field_name, value in data.fields.items():
        try:
            value = prepare_markdown_claim_value(field_name, value, Manufacturer)
        except ValidationError as exc:
            raise HttpError(422, "; ".join(exc.messages)) from exc
        Claim.objects.assert_claim(mfr, field_name, value, user=request.user)

    resolve_manufacturer(mfr)
    invalidate_all()

    mfr = get_object_or_404(_manufacturer_qs(), slug=mfr.slug)
    return _serialize_manufacturer_detail(mfr)
