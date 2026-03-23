"""Locations router — browse manufacturers by geography."""

from __future__ import annotations

from typing import Optional

from django.db.models import Count, F, Prefetch, Q
from django.utils.text import slugify
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError

from .helpers import _extract_image_urls

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class LocationManufacturerSchema(Schema):
    name: str
    slug: str
    model_count: int = 0
    thumbnail_url: Optional[str] = None


class CityRef(Schema):
    name: str
    slug: str
    manufacturer_count: int = 0


class StateRef(Schema):
    name: str
    slug: str
    manufacturer_count: int = 0
    cities: list[CityRef] = []


class CountryRef(Schema):
    name: str
    slug: str
    manufacturer_count: int = 0
    states: list[StateRef] = []
    cities: list[CityRef] = []


class LocationIndexSchema(Schema):
    countries: list[CountryRef]


class CountryDetailSchema(Schema):
    name: str
    slug: str
    manufacturer_count: int = 0
    states: list[StateRef]
    cities: list[CityRef]
    manufacturers: list[LocationManufacturerSchema]


class StateDetailSchema(Schema):
    name: str
    slug: str
    country_name: str
    country_slug: str
    manufacturer_count: int = 0
    cities: list[CityRef]
    manufacturers: list[LocationManufacturerSchema]


class CityDetailSchema(Schema):
    name: str
    slug: str
    state_name: str | None = None
    state_slug: str | None = None
    country_name: str
    country_slug: str
    manufacturer_count: int = 0
    manufacturers: list[LocationManufacturerSchema]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_location_tree():
    """Build a hierarchical location tree from Address records.

    Returns a dict keyed by country_slug -> {name, states: {state_slug -> {name, cities: ...}}}.
    Also returns a flat mapping of (country_slug, state_slug, city_slug) -> set of manufacturer PKs.
    """
    from ..models import Address

    addresses = (
        Address.objects.select_related(
            "corporate_entity__manufacturer",
        )
        .filter(corporate_entity__manufacturer__isnull=False)
        .values_list(
            "country",
            "state",
            "city",
            "corporate_entity__manufacturer__pk",
            "corporate_entity__manufacturer__name",
            "corporate_entity__manufacturer__slug",
        )
    )

    # Build the tree
    countries: dict[str, dict] = {}  # slug -> {name, manufacturers, states}

    for country, state, city, mfr_pk, mfr_name, mfr_slug in addresses:
        if not country:
            continue

        country_slug = slugify(country)
        if country_slug not in countries:
            countries[country_slug] = {
                "name": country,
                "manufacturers": set(),
                "states": {},
                "cities": {},  # cities with no state
            }
        countries[country_slug]["manufacturers"].add(mfr_pk)

        if state:
            state_slug = slugify(state)
            states = countries[country_slug]["states"]
            if state_slug not in states:
                states[state_slug] = {
                    "name": state,
                    "manufacturers": set(),
                    "cities": {},
                }
            states[state_slug]["manufacturers"].add(mfr_pk)

            if city:
                city_slug = slugify(city)
                cities = states[state_slug]["cities"]
                if city_slug not in cities:
                    cities[city_slug] = {
                        "name": city,
                        "manufacturers": set(),
                    }
                cities[city_slug]["manufacturers"].add(mfr_pk)
        elif city:
            # City with no state — store directly on the country
            city_slug = slugify(city)
            direct_cities = countries[country_slug]["cities"]
            if city_slug not in direct_cities:
                direct_cities[city_slug] = {
                    "name": city,
                    "manufacturers": set(),
                }
            direct_cities[city_slug]["manufacturers"].add(mfr_pk)

    return countries


def _serialize_cities(cities_dict):
    """Serialize a {slug: {name, manufacturers}} dict into a sorted list."""
    return sorted(
        [
            {
                "name": city_data["name"],
                "slug": city_slug,
                "manufacturer_count": len(city_data["manufacturers"]),
            }
            for city_slug, city_data in cities_dict.items()
        ],
        key=lambda c: c["name"],
    )


def _get_manufacturers_for_pks(pks):
    """Return serialized manufacturer list for a set of PKs."""
    from ..models import CorporateEntity, MachineModel, Manufacturer

    qs = (
        Manufacturer.objects.filter(pk__in=pks)
        .annotate(
            model_count=Count(
                "entities__models",
                filter=Q(entities__models__variant_of__isnull=True),
            )
        )
        .prefetch_related(
            Prefetch(
                "entities",
                queryset=CorporateEntity.objects.prefetch_related(
                    Prefetch(
                        "models",
                        queryset=MachineModel.objects.filter(variant_of__isnull=True)
                        .order_by(F("year").desc(nulls_last=True))
                        .only("extra_data"),
                    ),
                ),
            ),
        )
        .order_by("-model_count", "name")
    )

    result = []
    for mfr in qs:
        thumb = None
        for entity in mfr.entities.all():
            if thumb:
                break
            for model in entity.models.all():
                if model.extra_data:
                    thumb, _ = _extract_image_urls(model.extra_data)
                    if thumb:
                        break

        result.append(
            {
                "name": mfr.name,
                "slug": mfr.slug,
                "model_count": mfr.model_count,
                "thumbnail_url": thumb,
            }
        )
    return result


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

locations_router = Router(tags=["locations"])


@locations_router.get("/", response=LocationIndexSchema)
@decorate_view(cache_control(public=True, max_age=300))
def list_locations(request):
    """Return all countries with their state/city hierarchy and manufacturer counts."""
    tree = _get_location_tree()

    countries = []
    for country_slug, country_data in sorted(tree.items(), key=lambda x: x[1]["name"]):
        states = []
        for state_slug, state_data in sorted(
            country_data["states"].items(), key=lambda x: x[1]["name"]
        ):
            states.append(
                {
                    "name": state_data["name"],
                    "slug": state_slug,
                    "manufacturer_count": len(state_data["manufacturers"]),
                    "cities": _serialize_cities(state_data["cities"]),
                }
            )
        countries.append(
            {
                "name": country_data["name"],
                "slug": country_slug,
                "manufacturer_count": len(country_data["manufacturers"]),
                "states": states,
                "cities": _serialize_cities(country_data["cities"]),
            }
        )

    return {"countries": countries}


@locations_router.get("/{country_slug}", response=CountryDetailSchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_country(request, country_slug: str):
    """Return a country's manufacturers and state/city breakdown."""
    tree = _get_location_tree()

    country_data = tree.get(country_slug)
    if not country_data:
        raise HttpError(404, "Country not found")

    states = []
    for state_slug, state_data in sorted(
        country_data["states"].items(), key=lambda x: x[1]["name"]
    ):
        states.append(
            {
                "name": state_data["name"],
                "slug": state_slug,
                "manufacturer_count": len(state_data["manufacturers"]),
                "cities": _serialize_cities(state_data["cities"]),
            }
        )

    return {
        "name": country_data["name"],
        "slug": country_slug,
        "manufacturer_count": len(country_data["manufacturers"]),
        "states": states,
        "cities": _serialize_cities(country_data["cities"]),
        "manufacturers": _get_manufacturers_for_pks(country_data["manufacturers"]),
    }


@locations_router.get("/{country_slug}/{state_slug}", response=StateDetailSchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_state(request, country_slug: str, state_slug: str):
    """Return a state's manufacturers and city breakdown."""
    tree = _get_location_tree()

    country_data = tree.get(country_slug)
    if not country_data:
        raise HttpError(404, "Country not found")

    state_data = country_data["states"].get(state_slug)
    if not state_data:
        raise HttpError(404, "State not found")

    return {
        "name": state_data["name"],
        "slug": state_slug,
        "country_name": country_data["name"],
        "country_slug": country_slug,
        "manufacturer_count": len(state_data["manufacturers"]),
        "cities": _serialize_cities(state_data["cities"]),
        "manufacturers": _get_manufacturers_for_pks(state_data["manufacturers"]),
    }


@locations_router.get(
    "/{country_slug}/cities/{city_slug}",
    response=CityDetailSchema,
)
@decorate_view(cache_control(public=True, max_age=300))
def get_country_city(request, country_slug: str, city_slug: str):
    """Return a city (no state) and its manufacturers."""
    tree = _get_location_tree()

    country_data = tree.get(country_slug)
    if not country_data:
        raise HttpError(404, "Country not found")

    city_data = country_data["cities"].get(city_slug)
    if not city_data:
        raise HttpError(404, "City not found")

    return {
        "name": city_data["name"],
        "slug": city_slug,
        "state_name": None,
        "state_slug": None,
        "country_name": country_data["name"],
        "country_slug": country_slug,
        "manufacturer_count": len(city_data["manufacturers"]),
        "manufacturers": _get_manufacturers_for_pks(city_data["manufacturers"]),
    }


@locations_router.get(
    "/{country_slug}/{state_slug}/{city_slug}",
    response=CityDetailSchema,
)
@decorate_view(cache_control(public=True, max_age=300))
def get_city(request, country_slug: str, state_slug: str, city_slug: str):
    """Return a city's manufacturers."""
    tree = _get_location_tree()

    country_data = tree.get(country_slug)
    if not country_data:
        raise HttpError(404, "Country not found")

    state_data = country_data["states"].get(state_slug)
    if not state_data:
        raise HttpError(404, "State not found")

    city_data = state_data["cities"].get(city_slug)
    if not city_data:
        raise HttpError(404, "City not found")

    return {
        "name": city_data["name"],
        "slug": city_slug,
        "state_name": state_data["name"],
        "state_slug": state_slug,
        "country_name": country_data["name"],
        "country_slug": country_slug,
        "manufacturer_count": len(city_data["manufacturers"]),
        "manufacturers": _get_manufacturers_for_pks(city_data["manufacturers"]),
    }
