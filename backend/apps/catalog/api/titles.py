"""Titles router — list and detail endpoints."""

from __future__ import annotations

from typing import Optional

from django.db.models import Count, F, Max, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.pagination import PageNumberPagination, paginate

from .constants import DEFAULT_PAGE_SIZE
from .helpers import _extract_image_urls, _serialize_title_machine
from .machine_models import DesignCreditSchema
from .schemas import SeriesRefSchema, TitleMachineSchema

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class FacetRef(Schema):
    slug: str
    name: str


class TitleListSchema(Schema):
    name: str
    slug: str
    short_name: str
    machine_count: int = 0
    manufacturer_name: Optional[str] = None
    manufacturer_slug: Optional[str] = None
    year: Optional[int] = None
    thumbnail_url: Optional[str] = None
    # Facet data — aggregated from non-alias models
    tech_generations: list[FacetRef] = []
    display_types: list[FacetRef] = []
    player_counts: list[int] = []
    systems: list[FacetRef] = []
    themes: list[FacetRef] = []
    persons: list[FacetRef] = []
    franchise: Optional[FacetRef] = None
    series: list[FacetRef] = []
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    ipdb_rating_max: Optional[float] = None


class ReviewLinkSchema(Schema):
    label: str
    url: str


class TitleDetailSchema(Schema):
    name: str
    slug: str
    short_name: str
    needs_review: bool = False
    needs_review_notes: str = ""
    review_links: list[ReviewLinkSchema] = []
    machines: list[TitleMachineSchema]
    series: list[SeriesRefSchema] = []
    credits: list[DesignCreditSchema] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dedup_facet_refs(items) -> list[dict]:
    """Deduplicate {slug, name} pairs preserving insertion order."""
    seen: set[str] = set()
    result: list[dict] = []
    for slug, name in items:
        if slug and slug not in seen:
            seen.add(slug)
            result.append({"slug": slug, "name": name})
    return result


def _serialize_title_list(title) -> dict:
    thumbnail_url = None
    manufacturer_name = None
    manufacturer_slug = None
    year = None
    machines = list(title.machine_models.all())

    # Collect facet data from all non-alias models
    tech_gen_pairs = []
    display_type_pairs = []
    player_counts_set: set[int] = set()
    system_pairs = []
    theme_pairs = []
    person_pairs = []
    years = []
    ratings = []

    for m in machines:
        if m.technology_generation:
            tech_gen_pairs.append(
                (m.technology_generation.slug, m.technology_generation.name)
            )
        if m.display_type:
            display_type_pairs.append((m.display_type.slug, m.display_type.name))
        if m.player_count is not None:
            player_counts_set.add(m.player_count)
        if m.system:
            system_pairs.append((m.system.slug, m.system.name))
        for theme in m.themes.all():
            theme_pairs.append((theme.slug, theme.name))
        for credit in m.credits.all():
            person_pairs.append((credit.person.slug, credit.person.name))
        if m.year is not None:
            years.append(m.year)
        if m.ipdb_rating is not None:
            ratings.append(float(m.ipdb_rating))

    if machines:
        thumbnail_url, _ = _extract_image_urls(machines[0].extra_data or {})
        first = machines[0]
        manufacturer_name = first.manufacturer.name if first.manufacturer else None
        manufacturer_slug = first.manufacturer.slug if first.manufacturer else None
        year = first.year

    # Franchise (direct on Title) and Series (M2M on Title)
    franchise = None
    if title.franchise:
        franchise = {"slug": title.franchise.slug, "name": title.franchise.name}
    series_list = [
        {"slug": s.slug, "name": s.name}
        for s in getattr(title, "series_list", None) or title.series.all()
    ]

    return {
        "name": title.name,
        "slug": title.slug,
        "short_name": title.short_name,
        "machine_count": title.machine_count,
        "manufacturer_name": manufacturer_name,
        "manufacturer_slug": manufacturer_slug,
        "year": year,
        "thumbnail_url": thumbnail_url,
        "tech_generations": _dedup_facet_refs(tech_gen_pairs),
        "display_types": _dedup_facet_refs(display_type_pairs),
        "player_counts": sorted(player_counts_set),
        "systems": _dedup_facet_refs(system_pairs),
        "themes": _dedup_facet_refs(theme_pairs),
        "persons": _dedup_facet_refs(person_pairs),
        "franchise": franchise,
        "series": series_list,
        "year_min": min(years) if years else None,
        "year_max": max(years) if years else None,
        "ipdb_rating_max": max(ratings) if ratings else None,
    }


def _build_review_links(title) -> list[dict]:
    """Build external/internal review links for a needs_review title."""
    from ..models import Title

    links: list[dict] = []
    opdb_id = title.opdb_id

    # IPDB link (synthetic IDs are "ipdb:{id}").
    if opdb_id.startswith("ipdb:"):
        ipdb_id = opdb_id.split(":")[1]
        links.append(
            {
                "label": f"IPDB #{ipdb_id}",
                "url": f"https://www.ipdb.org/machine.cgi?id={ipdb_id}",
            }
        )

    # Related titles by name match (only OPDB-backed ones).
    import re

    base_name = re.sub(r"\s*\([^)]*\)\s*$", "", title.name).strip()
    related = (
        Title.objects.filter(Q(name__iexact=title.name) | Q(name__iexact=base_name))
        .exclude(pk=title.pk)
        .exclude(opdb_id__startswith="ipdb:")
    )
    for rt in related:
        links.append({"label": rt.name, "url": f"/titles/{rt.slug}"})
        links.append(
            {
                "label": f"OPDB {rt.opdb_id}",
                "url": f"https://opdb.org/machines/{rt.opdb_id}",
            }
        )

    return links


def _serialize_title_detail(title) -> dict:
    machines = [_serialize_title_machine(pm) for pm in title.machine_models.all()]
    series = [
        {"name": s.name, "slug": s.slug}
        for s in getattr(title, "series_list", None) or title.series.all()
    ]
    review_links = _build_review_links(title) if title.needs_review else []

    # Aggregate credits from all models, deduplicating by (person, role)
    seen: set[tuple[str, str]] = set()
    credits: list[dict] = []
    for pm in title.machine_models.all():
        for c in pm.credits.all():
            key = (c.person.slug, c.role)
            if key not in seen:
                seen.add(key)
                credits.append(
                    {
                        "person_name": c.person.name,
                        "person_slug": c.person.slug,
                        "role": c.role,
                        "role_display": c.get_role_display(),
                    }
                )

    return {
        "name": title.name,
        "slug": title.slug,
        "short_name": title.short_name,
        "needs_review": title.needs_review,
        "needs_review_notes": title.needs_review_notes,
        "review_links": review_links,
        "machines": machines,
        "series": series,
        "credits": credits,
    }


def _title_models_prefetch():
    from ..models import MachineModel

    return Prefetch(
        "machine_models",
        queryset=MachineModel.objects.filter(alias_of__isnull=True)
        .select_related(
            "manufacturer", "technology_generation", "display_type", "system"
        )
        .prefetch_related("themes", "credits__person")
        .order_by("year", "name"),
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

titles_router = Router(tags=["titles"])


@titles_router.get("/", response=list[TitleListSchema])
@paginate(PageNumberPagination, page_size=DEFAULT_PAGE_SIZE)
def list_titles(request, display: str = ""):
    from ..models import Title

    qs = Title.objects.annotate(
        machine_count=Count(
            "machine_models", filter=Q(machine_models__alias_of__isnull=True)
        )
    )
    if display:
        qs = qs.filter(machine_models__display_type__slug=display).distinct()
    qs = (
        qs.select_related("franchise")
        .prefetch_related(_title_models_prefetch(), "series")
        .order_by("name")
    )
    return [_serialize_title_list(t) for t in qs]


@titles_router.get("/all/", response=list[TitleListSchema])
@decorate_view(cache_control(public=True, max_age=300))
def list_all_titles(request):
    """Return every title with minimal fields (no pagination)."""
    from ..models import Title

    qs = (
        Title.objects.annotate(
            machine_count=Count(
                "machine_models", filter=Q(machine_models__alias_of__isnull=True)
            ),
            latest_year=Max(
                "machine_models__year",
                filter=Q(machine_models__alias_of__isnull=True),
            ),
        )
        .select_related("franchise")
        .prefetch_related(_title_models_prefetch(), "series")
        .order_by(F("latest_year").desc(nulls_last=True), "name")
    )
    return [_serialize_title_list(t) for t in qs]


@titles_router.get("/{slug}", response=TitleDetailSchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_title(request, slug: str):
    from ..models import Title

    title = get_object_or_404(
        Title.objects.prefetch_related(_title_models_prefetch(), "series"),
        slug=slug,
    )
    return _serialize_title_detail(title)
