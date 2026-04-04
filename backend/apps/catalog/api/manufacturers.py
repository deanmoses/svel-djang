"""Manufacturers router — list, detail, and claim-patch endpoints."""

from __future__ import annotations

from typing import Optional

from django.core.cache import cache
from django.db.models import Count, F, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.pagination import PageNumberPagination, paginate
from ninja.security import django_auth

from apps.core.models import active_status_q


from ..cache import MANUFACTURERS_ALL_KEY
from .constants import DEFAULT_PAGE_SIZE
from apps.provenance.helpers import build_sources, claims_prefetch

from .helpers import (
    _build_rich_text,
    _collect_titles,
    _extract_image_urls,
    _media_prefetch,
    _serialize_locations,
    _serialize_uploaded_media,
)
from .schemas import (
    ClaimPatchSchema,
    ClaimSchema,
    RelatedTitleSchema,
    RichTextSchema,
    UploadedMediaSchema,
)
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


class CorporateEntityLocationAncestorRef(Schema):
    display_name: str
    location_path: str


class CorporateEntityLocationSchema(Schema):
    location_path: str
    location_type: str
    display_name: str
    slug: str
    ancestors: list[CorporateEntityLocationAncestorRef] = []


class CorporateEntitySchema(Schema):
    name: str
    slug: str
    year_start: int | None
    year_end: int | None
    locations: list[CorporateEntityLocationSchema]


class SystemSchema(Schema):
    name: str
    slug: str


class ManufacturerPersonSchema(Schema):
    name: str
    slug: str
    roles: list[str] = []


class ManufacturerDetailSchema(Schema):
    name: str
    slug: str
    description: RichTextSchema = RichTextSchema()
    year_start: int | None = None
    year_end: int | None = None
    country: str | None = None
    headquarters: str | None = None
    logo_url: str | None = None
    website: str = ""
    entities: list[CorporateEntitySchema]
    titles: list[RelatedTitleSchema]
    systems: list[SystemSchema]
    persons: list[ManufacturerPersonSchema] = []
    uploaded_media: list[UploadedMediaSchema] = []
    sources: list[ClaimSchema]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_manufacturer_detail(mfr) -> dict:
    """Serialize a Manufacturer into the detail response dict.

    Expects *mfr* to have been fetched with prefetch_related for entities,
    non_variant_models, credits, and claims (to_attr="active_claims").
    """

    # Collect persons with roles and compute year range across entities.
    person_roles: dict[str, dict] = {}  # slug -> {name, roles set}
    year_starts: list[int] = []
    year_ends: list[int] = []

    for e in mfr.entities.all():
        if e.year_start is not None:
            year_starts.append(e.year_start)
        if e.year_end is not None:
            year_ends.append(e.year_end)
        for m in e.models.all():
            for credit in m.credits.all():
                p = credit.person
                if p.slug not in person_roles:
                    person_roles[p.slug] = {
                        "name": p.name,
                        "slug": p.slug,
                        "roles": set(),
                    }
                if credit.role:
                    person_roles[p.slug]["roles"].add(credit.role.name)

    persons = sorted(
        (
            {"name": v["name"], "slug": v["slug"], "roles": sorted(v["roles"])}
            for v in person_roles.values()
        ),
        key=lambda p: p["name"],
    )

    return {
        "name": mfr.name,
        "slug": mfr.slug,
        "description": _build_rich_text(
            mfr, "description", getattr(mfr, "active_claims", [])
        ),
        "year_start": min(year_starts) if year_starts else None,
        "year_end": max(year_ends) if year_ends else None,
        "logo_url": mfr.logo_url,
        "website": mfr.website,
        "entities": [
            {
                "name": e.name,
                "slug": e.slug,
                "year_start": e.year_start,
                "year_end": e.year_end,
                "locations": _serialize_locations(e),
            }
            for e in mfr.entities.all()
        ],
        "titles": _collect_titles(
            m for e in mfr.entities.all() for m in e.models.all()
        ),
        "systems": [{"name": s.name, "slug": s.slug} for s in mfr.systems.all()],
        "persons": persons,
        "uploaded_media": _serialize_uploaded_media(
            getattr(mfr, "all_media", None) or []
        ),
        "sources": build_sources(getattr(mfr, "active_claims", [])),
    }


def _manufacturer_qs():
    from ..models import CorporateEntity, MachineModel, Manufacturer, System

    from ..models import CorporateEntityLocation

    return Manufacturer.objects.active().prefetch_related(
        Prefetch(
            "entities",
            queryset=CorporateEntity.objects.active()
            .prefetch_related(
                Prefetch(
                    "locations",
                    queryset=CorporateEntityLocation.objects.select_related(
                        "location__parent__parent__parent"
                    ),
                ),
                Prefetch(
                    "models",
                    queryset=MachineModel.objects.active()
                    .filter(variant_of__isnull=True)
                    .select_related("technology_generation", "title")
                    .prefetch_related("credits__person", "credits__role")
                    .order_by(F("year").desc(nulls_last=True), "name"),
                ),
            )
            .order_by("year_start"),
        ),
        Prefetch("systems", queryset=System.objects.active().order_by("name")),
        claims_prefetch(),
        _media_prefetch(),
    )


def _build_location_refs(entities) -> list[dict]:
    """Build location FacetRefs for each location and all its ancestors.

    Uses location_path as the slug so refs are globally unique and stable.
    """
    refs: dict[str, str] = {}  # location_path -> name
    for entity in entities:
        for cel in entity.locations.all():
            loc = cel.location
            while loc is not None:
                if loc.location_path not in refs:
                    refs[loc.location_path] = loc.name
                loc = loc.parent
    return [{"slug": path, "name": name} for path, name in refs.items()]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

manufacturers_router = Router(tags=["manufacturers"])


@manufacturers_router.get("/", response=list[ManufacturerSchema])
@paginate(PageNumberPagination, page_size=DEFAULT_PAGE_SIZE)
def list_manufacturers(request):
    from ..models import Manufacturer

    return list(
        Manufacturer.objects.active()
        .annotate(
            model_count=Count(
                "entities__models",
                filter=active_status_q("entities__models"),
            )
        )
        .order_by("name")
        .values("name", "slug", "model_count")
    )


@manufacturers_router.get("/all/", response=list[ManufacturerGridSchema])
@decorate_view(cache_control(no_cache=True))
def list_all_manufacturers(request):
    """Return every manufacturer with model count and thumbnail (no pagination)."""
    result = cache.get(MANUFACTURERS_ALL_KEY)
    if result is not None:
        return result

    from ..models import (
        CorporateEntity,
        CorporateEntityLocation,
        MachineModel,
        Manufacturer,
    )

    qs = (
        Manufacturer.objects.active()
        .annotate(
            model_count=Count(
                "entities__models",
                filter=Q(entities__models__variant_of__isnull=True)
                & active_status_q("entities__models"),
            )
        )
        .prefetch_related(
            Prefetch(
                "entities",
                queryset=CorporateEntity.objects.active().prefetch_related(
                    Prefetch(
                        "locations",
                        queryset=CorporateEntityLocation.objects.select_related(
                            "location__parent__parent__parent__parent"
                        ),
                    ),
                    "aliases",
                    Prefetch(
                        "models",
                        queryset=MachineModel.objects.active()
                        .filter(variant_of__isnull=True)
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
            for alias in entity.aliases.all():
                search_parts.append(alias.value)
            for cel in entity.locations.all():
                loc = cel.location
                while loc is not None:
                    if loc.name:
                        search_parts.append(loc.name)
                    loc = loc.parent
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
@decorate_view(cache_control(no_cache=True))
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
    from .edit_claims import execute_claims, plan_scalar_field_claims

    from ..models import Manufacturer

    mfr = get_object_or_404(Manufacturer.objects.active(), slug=slug)

    specs = plan_scalar_field_claims(Manufacturer, data.fields, entity=mfr)

    execute_claims(mfr, specs, user=request.user)

    mfr = get_object_or_404(_manufacturer_qs(), slug=mfr.slug)
    return _serialize_manufacturer_detail(mfr)
