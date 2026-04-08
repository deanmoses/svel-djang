"""Manufacturers router — list, detail, and claim-patch endpoints."""

from __future__ import annotations

from typing import Optional

from django.db.models import Count, F, Max, Min, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.pagination import PageNumberPagination, paginate
from ninja.security import django_auth

from apps.core.models import active_status_q


from ..cache import MANUFACTURERS_ALL_KEY, get_cached_response, set_cached_response
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

from collections import defaultdict

from apps.core.licensing import get_minimum_display_rank

from ..models import (
    CorporateEntity,
    CorporateEntityAlias,
    CorporateEntityLocation,
    Credit,
    MachineModel,
    Manufacturer,
    System,
)
from .edit_claims import execute_claims, plan_scalar_field_claims

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
    """Return every manufacturer with facet data for client-side filtering.

    Performance-critical: uses bulk queries and lookup maps instead of
    deep prefetch + Python iteration.  See ``list_all_titles`` for the
    full explanation of this pattern.
    """
    response = get_cached_response(MANUFACTURERS_ALL_KEY)
    if response is not None:
        return response

    min_rank = get_minimum_display_rank()

    # --- Main query with annotations ---
    manufacturers = list(
        Manufacturer.objects.active()
        .annotate(
            model_count=Count(
                "entities__models",
                filter=Q(entities__models__variant_of__isnull=True)
                & active_status_q("entities__models"),
            ),
            year_min=Min(
                "entities__models__year",
                filter=Q(entities__models__variant_of__isnull=True)
                & active_status_q("entities__models"),
            ),
            year_max=Max(
                "entities__models__year",
                filter=Q(entities__models__variant_of__isnull=True)
                & active_status_q("entities__models"),
            ),
        )
        .order_by("-model_count")
    )

    # --- Batch thumbnail: newest model with extra_data per manufacturer ---
    mfr_thumb_model: dict[int, int] = {}
    for mfr_id, model_id in (
        MachineModel.objects.active()
        .filter(
            variant_of__isnull=True,
            extra_data__isnull=False,
            corporate_entity__manufacturer__isnull=False,
        )
        .order_by(F("year").desc(nulls_last=True), "name")
        .values_list("corporate_entity__manufacturer_id", "id")
    ):
        if mfr_id not in mfr_thumb_model:
            mfr_thumb_model[mfr_id] = model_id
    thumb_models = {
        m.id: m
        for m in MachineModel.objects.filter(id__in=mfr_thumb_model.values()).only(
            "id", "extra_data"
        )
    }

    # --- Bulk search text + facet data per manufacturer ---
    mfr_ids = {m.id for m in manufacturers}

    # Entity names per manufacturer
    mfr_entity_names: dict[int, list[str]] = defaultdict(list)
    mfr_entity_ids: dict[int, list[int]] = defaultdict(list)
    for eid, mfr_id, ename in CorporateEntity.objects.active().values_list(
        "id", "manufacturer_id", "name"
    ):
        if mfr_id in mfr_ids:
            mfr_entity_names[mfr_id].append(ename)
            mfr_entity_ids[mfr_id].append(eid)

    all_entity_ids = {eid for eids in mfr_entity_ids.values() for eid in eids}

    # Aliases per entity → grouped by manufacturer
    entity_to_mfr: dict[int, int] = {}
    for mfr_id, eids in mfr_entity_ids.items():
        for eid in eids:
            entity_to_mfr[eid] = mfr_id

    mfr_alias_names: dict[int, list[str]] = defaultdict(list)
    for eid, aval in CorporateEntityAlias.objects.filter(
        corporate_entity_id__in=all_entity_ids
    ).values_list("corporate_entity_id", "value"):
        mid = entity_to_mfr.get(eid)
        if mid:
            mfr_alias_names[mid].append(aval)

    # Locations per manufacturer (with hierarchy)
    mfr_location_names: dict[int, list[str]] = defaultdict(list)
    mfr_location_refs: dict[int, dict[str, str]] = defaultdict(dict)
    for eid, loc_path, loc_name, p1n, p1p, p2n, p2p, p3n, p3p, p4n, p4p in (
        CorporateEntityLocation.objects.filter(corporate_entity_id__in=all_entity_ids)
        .select_related("location__parent__parent__parent__parent")
        .values_list(
            "corporate_entity_id",
            "location__location_path",
            "location__name",
            "location__parent__name",
            "location__parent__location_path",
            "location__parent__parent__name",
            "location__parent__parent__location_path",
            "location__parent__parent__parent__name",
            "location__parent__parent__parent__location_path",
            "location__parent__parent__parent__parent__name",
            "location__parent__parent__parent__parent__location_path",
        )
    ):
        mid = entity_to_mfr.get(eid)
        if not mid:
            continue
        for name, path in (
            (loc_name, loc_path),
            (p1n, p1p),
            (p2n, p2p),
            (p3n, p3p),
            (p4n, p4p),
        ):
            if name:
                mfr_location_names[mid].append(name)
            if path and name and path not in mfr_location_refs[mid]:
                mfr_location_refs[mid][path] = name

    # Tech generations per manufacturer (via models)
    mfr_tech_gens: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for mfr_id, tg_slug, tg_name in (
        MachineModel.objects.active()
        .filter(
            variant_of__isnull=True,
            technology_generation__isnull=False,
            corporate_entity__manufacturer_id__in=mfr_ids,
        )
        .values_list(
            "corporate_entity__manufacturer_id",
            "technology_generation__slug",
            "technology_generation__name",
        )
        .distinct()
    ):
        mfr_tech_gens[mfr_id].append((tg_slug, tg_name))

    # Persons per manufacturer (via model credits)
    mfr_persons: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for mfr_id, p_slug, p_name in (
        Credit.objects.filter(
            model__variant_of__isnull=True,
            model__corporate_entity__manufacturer_id__in=mfr_ids,
        )
        .values_list(
            "model__corporate_entity__manufacturer_id",
            "person__slug",
            "person__name",
        )
        .distinct()
    ):
        mfr_persons[mfr_id].append((p_slug, p_name))

    # --- Assembly ---
    result = []
    for mfr in manufacturers:
        search_parts: list[str] = []
        search_parts.extend(mfr_entity_names.get(mfr.id, []))
        search_parts.extend(mfr_alias_names.get(mfr.id, []))
        search_parts.extend(mfr_location_names.get(mfr.id, []))

        thumb = None
        tm_id = mfr_thumb_model.get(mfr.id)
        tm = thumb_models.get(tm_id) if tm_id else None
        if tm and tm.extra_data:
            thumb, _ = _extract_image_urls(tm.extra_data, min_rank=min_rank)

        loc_refs_map = mfr_location_refs.get(mfr.id, {})
        locations = [
            {"slug": path, "name": name} for path, name in loc_refs_map.items()
        ]

        result.append(
            {
                "name": mfr.name,
                "slug": mfr.slug,
                "model_count": mfr.model_count,
                "thumbnail_url": thumb,
                "search_text": (" | ".join(search_parts) if search_parts else None),
                "locations": locations,
                "year_min": mfr.year_min,
                "year_max": mfr.year_max,
                "persons": _dedup_facet_refs(mfr_persons.get(mfr.id, [])),
                "tech_generations": _dedup_facet_refs(mfr_tech_gens.get(mfr.id, [])),
            }
        )
    return set_cached_response(MANUFACTURERS_ALL_KEY, result)


@manufacturers_router.patch(
    "/{slug}/claims/",
    auth=django_auth,
    response=ManufacturerDetailSchema,
    tags=["private"],
)
def patch_manufacturer_claims(request, slug: str, data: ClaimPatchSchema):
    """Assert per-field claims from the authenticated user, then re-resolve."""
    mfr = get_object_or_404(Manufacturer.objects.active(), slug=slug)

    specs = plan_scalar_field_claims(Manufacturer, data.fields, entity=mfr)

    execute_claims(
        mfr, specs, user=request.user, note=data.note, citation=data.citation
    )

    mfr = get_object_or_404(_manufacturer_qs(), slug=mfr.slug)
    return _serialize_manufacturer_detail(mfr)
