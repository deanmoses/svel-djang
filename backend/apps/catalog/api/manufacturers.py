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

from ..cache import MANUFACTURERS_ALL_KEY, invalidate_all
from .constants import DEFAULT_PAGE_SIZE
from .helpers import _build_activity, _claims_prefetch, _extract_image_urls
from .schemas import ClaimPatchSchema, ClaimSchema, RelatedTitleSchema

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ManufacturerGridSchema(Schema):
    name: str
    slug: str
    trade_name: str
    model_count: int = 0
    thumbnail_url: Optional[str] = None
    search_text: Optional[str] = None


class ManufacturerSchema(Schema):
    name: str
    slug: str
    trade_name: str
    model_count: int = 0


class AddressSchema(Schema):
    city: str
    state: str
    country: str


class CorporateEntitySchema(Schema):
    name: str
    years_active: str
    addresses: list[AddressSchema]


class SystemSchema(Schema):
    name: str
    slug: str


class ManufacturerDetailSchema(Schema):
    name: str
    slug: str
    trade_name: str
    description: str = ""
    description_html: str = ""
    founded_year: int | None = None
    dissolved_year: int | None = None
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
                    m.manufacturer.name if m.manufacturer else None
                )
            titles[key] = entry
        elif titles[key]["thumbnail_url"] is None:
            thumbnail_url = _extract_image_urls(m.extra_data or {})[0]
            if thumbnail_url:
                titles[key]["thumbnail_url"] = thumbnail_url
    return list(titles.values())


def _serialize_manufacturer_detail(mfr) -> dict:
    """Serialize a Manufacturer into the detail response dict.

    Expects *mfr* to have been fetched with prefetch_related for entities,
    non_variant_models, and claims (to_attr="active_claims").
    """
    from apps.core.markdown import render_markdown_fields

    return {
        "name": mfr.name,
        "slug": mfr.slug,
        "trade_name": mfr.trade_name,
        "description": mfr.description,
        **render_markdown_fields(mfr),
        "founded_year": mfr.founded_year,
        "dissolved_year": mfr.dissolved_year,
        "country": mfr.country,
        "headquarters": mfr.headquarters,
        "logo_url": mfr.logo_url,
        "website": mfr.website,
        "entities": [
            {
                "name": e.name,
                "years_active": e.years_active,
                "addresses": [
                    {"city": a.city, "state": a.state, "country": a.country}
                    for a in e.addresses.all()
                ],
            }
            for e in mfr.entities.all()
        ],
        "titles": _collect_titles(mfr.non_variant_models),
        "systems": [{"name": s.name, "slug": s.slug} for s in mfr.systems.all()],
        "activity": _build_activity(getattr(mfr, "active_claims", [])),
    }


def _manufacturer_qs():
    from ..models import CorporateEntity, MachineModel, Manufacturer, System

    return Manufacturer.objects.prefetch_related(
        Prefetch(
            "entities",
            queryset=CorporateEntity.objects.prefetch_related("addresses").order_by(
                "years_active"
            ),
        ),
        Prefetch(
            "models",
            queryset=MachineModel.objects.filter(variant_of__isnull=True)
            .select_related("technology_generation", "title")
            .order_by(F("year").desc(nulls_last=True), "name"),
            to_attr="non_variant_models",
        ),
        Prefetch("systems", queryset=System.objects.order_by("name")),
        _claims_prefetch(),
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

manufacturers_router = Router(tags=["manufacturers"])


@manufacturers_router.get("/", response=list[ManufacturerSchema])
@paginate(PageNumberPagination, page_size=DEFAULT_PAGE_SIZE)
def list_manufacturers(request):
    from ..models import Manufacturer

    return list(
        Manufacturer.objects.annotate(model_count=Count("models"))
        .order_by("name")
        .values("name", "slug", "trade_name", "model_count")
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
            model_count=Count("models", filter=Q(models__variant_of__isnull=True))
        )
        .prefetch_related(
            Prefetch(
                "models",
                queryset=MachineModel.objects.filter(variant_of__isnull=True)
                .exclude(extra_data={})
                .order_by(F("year").desc(nulls_last=True))
                .only("id", "manufacturer_id", "year", "extra_data"),
                to_attr="models_with_images",
            ),
            Prefetch(
                "entities",
                queryset=CorporateEntity.objects.prefetch_related("addresses"),
            ),
        )
        .order_by("-model_count")
    )

    result = []
    for mfr in qs:
        thumb = None
        for model in mfr.models_with_images:
            thumb, _ = _extract_image_urls(model.extra_data)
            if thumb:
                break
        # Build search text from name, trade_name, entities, and addresses.
        parts: list[str] = []
        if mfr.trade_name and mfr.trade_name != mfr.name:
            parts.append(mfr.trade_name)
        for entity in mfr.entities.all():
            parts.append(entity.name)
            for addr in entity.addresses.all():
                if addr.city:
                    parts.append(addr.city)
                if addr.state:
                    parts.append(addr.state)
                if addr.country:
                    parts.append(addr.country)
        result.append(
            {
                "name": mfr.name,
                "slug": mfr.slug,
                "trade_name": mfr.trade_name,
                "model_count": mfr.model_count,
                "thumbnail_url": thumb,
                "search_text": " | ".join(parts) if parts else None,
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
