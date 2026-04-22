"""Locations router — browse manufacturers by geography."""

from __future__ import annotations

from typing import cast

from django.core.cache import cache
from django.db.models import Count, F, Prefetch, Q
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError

from apps.core.licensing import get_minimum_display_rank
from apps.core.models import active_status_q

from ..cache import LOCATIONS_TREE_KEY
from ..models import (
    CorporateEntity,
    CorporateEntityLocation,
    Location,
    MachineModel,
    Manufacturer,
)
from ._typing import HasModelCount
from .helpers import _first_thumbnail

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class LocationManufacturerSchema(Schema):
    name: str
    slug: str
    model_count: int = 0
    thumbnail_url: str | None = None


class LocationChildRef(Schema):
    name: str
    slug: str
    location_path: str
    location_type: str
    manufacturer_count: int = 0


class LocationAncestorRef(Schema):
    name: str
    slug: str
    location_path: str


class LocationIndexCountry(Schema):
    name: str
    slug: str
    location_path: str
    manufacturer_count: int = 0
    children: list[LocationChildRef] = []


class LocationIndexSchema(Schema):
    countries: list[LocationIndexCountry]


class LocationDetailSchema(Schema):
    name: str
    slug: str
    location_path: str
    location_type: str
    manufacturer_count: int = 0
    ancestors: list[LocationAncestorRef] = []
    children: list[LocationChildRef] = []
    manufacturers: list[LocationManufacturerSchema] = []


# ---------------------------------------------------------------------------
# Tree building
# ---------------------------------------------------------------------------


def _get_location_tree():
    """Build location data from Location + CorporateEntityLocation records.

    Returns a tuple (nodes, children_index) where:
    - nodes: dict[location_path, {name, slug, location_type, parent_path,
                                  location_path, manufacturer_pks: frozenset}]
    - children_index: dict[parent_path_or_None, list[location_path]]

    Results are cached; invalidated by ``invalidate_all()``.
    """
    result = cache.get(LOCATIONS_TREE_KEY)
    if result is not None:
        return result

    # Load all locations with parent chains (up to 4 levels deep).
    all_locs = list(
        Location.objects.active().select_related("parent__parent__parent__parent").all()
    )

    # Accumulate manufacturer PKs at each location and all its ancestors.
    mfr_pks_by_path: dict[str, set[int]] = {}
    for cel in (
        CorporateEntityLocation.objects.select_related(
            "location__parent__parent__parent__parent",
            "corporate_entity__manufacturer",
        )
        .filter(corporate_entity__manufacturer__isnull=False)
        .filter(
            Q(corporate_entity__status="active")
            | Q(corporate_entity__status__isnull=True)
        )
    ):
        mfr_pk = cel.corporate_entity.manufacturer_id
        loc = cel.location
        while loc is not None:
            mfr_pks_by_path.setdefault(loc.location_path, set()).add(mfr_pk)
            loc = loc.parent

    nodes: dict[str, dict] = {}
    children_index: dict[str | None, list[str]] = {}
    for loc in all_locs:
        parent_path = loc.parent.location_path if loc.parent else None
        nodes[loc.location_path] = {
            "name": loc.name,
            "slug": loc.slug,
            "location_path": loc.location_path,
            "location_type": loc.location_type,
            "parent_path": parent_path,
            "manufacturer_pks": frozenset(
                mfr_pks_by_path.get(loc.location_path, set())
            ),
        }
        children_index.setdefault(parent_path, []).append(loc.location_path)

    tree = (nodes, children_index)
    cache.set(LOCATIONS_TREE_KEY, tree, timeout=None)
    return tree


def _children_of(path: str | None, nodes: dict, children_index: dict) -> list[dict]:
    """Return child nodes sorted by manufacturer_count desc, then name."""
    return sorted(
        [nodes[p] for p in children_index.get(path, []) if p in nodes],
        key=lambda n: (-len(n["manufacturer_pks"]), n["name"]),
    )


def _ancestors_of(path: str, nodes: dict) -> list[dict]:
    """Return ancestor chain from root to immediate parent (root first)."""
    ancestors: list[dict] = []
    node = nodes.get(path)
    if node is None:
        return ancestors
    parent_path = node["parent_path"]
    while parent_path is not None:
        parent = nodes.get(parent_path)
        if parent is None:
            break
        ancestors.insert(0, parent)
        parent_path = parent["parent_path"]
    return ancestors


def _get_manufacturers_for_pks(pks):
    """Return serialized manufacturer list for a set of PKs."""
    qs = (
        Manufacturer.objects.active()
        .filter(pk__in=pks)
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
                        "models",
                        queryset=MachineModel.objects.active()
                        .filter(variant_of__isnull=True)
                        .order_by(F("year").desc(nulls_last=True))
                        .only("extra_data"),
                    ),
                ),
            ),
        )
        .order_by("-model_count", "name")
    )

    min_rank = get_minimum_display_rank()
    return [
        {
            "name": mfr.name,
            "slug": mfr.slug,
            "model_count": cast(HasModelCount, mfr).model_count,
            "thumbnail_url": _first_thumbnail(mfr.entities.all(), min_rank=min_rank),
        }
        for mfr in qs
    ]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

locations_router = Router(tags=["locations"])


@locations_router.get("/", response=LocationIndexSchema)
@decorate_view(cache_control(no_cache=True))
def list_locations(request):
    """Return all countries with their direct children and manufacturer counts."""
    nodes, children_index = _get_location_tree()

    countries = []
    for country_path in sorted(
        children_index.get(None, []), key=lambda p: nodes[p]["name"]
    ):
        country = nodes[country_path]
        children = _children_of(country_path, nodes, children_index)
        countries.append(
            {
                "name": country["name"],
                "slug": country["slug"],
                "location_path": country_path,
                "manufacturer_count": len(country["manufacturer_pks"]),
                "children": [
                    {
                        "name": c["name"],
                        "slug": c["slug"],
                        "location_path": c["location_path"],
                        "location_type": c["location_type"],
                        "manufacturer_count": len(c["manufacturer_pks"]),
                    }
                    for c in children
                ],
            }
        )

    return {"countries": countries}


def _get_location_detail(location_path: str) -> dict:
    """Shared implementation for all location detail endpoints."""
    nodes, children_index = _get_location_tree()

    node = nodes.get(location_path)
    if not node:
        raise HttpError(404, "Location not found")

    ancestors = _ancestors_of(location_path, nodes)
    children = _children_of(location_path, nodes, children_index)

    return {
        "name": node["name"],
        "slug": node["slug"],
        "location_path": location_path,
        "location_type": node["location_type"],
        "manufacturer_count": len(node["manufacturer_pks"]),
        "ancestors": [
            {"name": a["name"], "slug": a["slug"], "location_path": a["location_path"]}
            for a in ancestors
        ],
        "children": [
            {
                "name": c["name"],
                "slug": c["slug"],
                "location_path": c["location_path"],
                "location_type": c["location_type"],
                "manufacturer_count": len(c["manufacturer_pks"]),
            }
            for c in children
        ],
        "manufacturers": _get_manufacturers_for_pks(node["manufacturer_pks"]),
    }


# Ninja's path converter syntax doesn't support Django's <path:...> wildcard,
# so we define explicit routes for each supported hierarchy depth (1–4 segments).
# Pindata's maximum depth is 4 (e.g. france/idf/essonne/marcoussis).


@locations_router.get("/{s1}", response=LocationDetailSchema)
@decorate_view(cache_control(no_cache=True))
def get_location_1(request, s1: str):
    """Return detail for a single-segment location (e.g. 'usa')."""
    return _get_location_detail(s1)


@locations_router.get("/{s1}/{s2}", response=LocationDetailSchema)
@decorate_view(cache_control(no_cache=True))
def get_location_2(request, s1: str, s2: str):
    """Return detail for a two-segment location (e.g. 'usa/il')."""
    return _get_location_detail(f"{s1}/{s2}")


@locations_router.get("/{s1}/{s2}/{s3}", response=LocationDetailSchema)
@decorate_view(cache_control(no_cache=True))
def get_location_3(request, s1: str, s2: str, s3: str):
    """Return detail for a three-segment location (e.g. 'usa/il/chicago')."""
    return _get_location_detail(f"{s1}/{s2}/{s3}")


@locations_router.get("/{s1}/{s2}/{s3}/{s4}", response=LocationDetailSchema)
@decorate_view(cache_control(no_cache=True))
def get_location_4(request, s1: str, s2: str, s3: str, s4: str):
    """Return detail for a four-segment location (e.g. 'france/idf/essonne/marcoussis')."""
    return _get_location_detail(f"{s1}/{s2}/{s3}/{s4}")
