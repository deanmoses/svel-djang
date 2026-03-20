"""Titles router — list and detail endpoints."""

from __future__ import annotations

from typing import Optional

from django.db.models import Count, F, Max, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.pagination import PageNumberPagination, paginate

from apps.core.markdown import render_markdown_fields

from .constants import DEFAULT_PAGE_SIZE
from .helpers import _extract_image_urls, _serialize_title_machine
from .machine_models import CreditSchema, MachineModelDetailSchema
from .schemas import SeriesRefSchema, ThemeSchema, TitleMachineSchema
from ..cache import TITLES_ALL_KEY

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class FacetRef(Schema):
    slug: str
    name: str


class TitleListSchema(Schema):
    name: str
    slug: str
    abbreviations: list[str] = []
    machine_count: int = 0
    manufacturer_name: Optional[str] = None
    manufacturer_slug: Optional[str] = None
    year: Optional[int] = None
    thumbnail_url: Optional[str] = None
    # Facet data — aggregated from non-variant models
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


class AgreedSpecsSchema(Schema):
    """Spec fields where all child models of a title agree on the value."""

    technology_generation_name: Optional[str] = None
    technology_generation_slug: Optional[str] = None
    display_type_name: Optional[str] = None
    display_type_slug: Optional[str] = None
    player_count: Optional[int] = None
    flipper_count: Optional[int] = None
    system_name: Optional[str] = None
    system_slug: Optional[str] = None
    cabinet_name: Optional[str] = None
    cabinet_slug: Optional[str] = None
    game_format_name: Optional[str] = None
    game_format_slug: Optional[str] = None
    display_subtype_name: Optional[str] = None
    display_subtype_slug: Optional[str] = None
    themes: list[ThemeSchema] = []
    production_quantity: Optional[str] = None


class TitleDetailSchema(Schema):
    name: str
    slug: str
    abbreviations: list[str] = []
    description: str = ""
    description_html: str = ""
    needs_review: bool = False
    needs_review_notes: str = ""
    review_links: list[ReviewLinkSchema] = []
    hero_image_url: Optional[str] = None
    franchise: Optional[FacetRef] = None
    machines: list[TitleMachineSchema]
    series: list[SeriesRefSchema] = []
    credits: list[CreditSchema] = []
    agreed_specs: AgreedSpecsSchema = AgreedSpecsSchema()
    model_detail: Optional[MachineModelDetailSchema] = None


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

    # Collect facet data from all non-variant models
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
        manufacturer_name = (
            first.corporate_entity.manufacturer.name
            if first.corporate_entity and first.corporate_entity.manufacturer
            else None
        )
        manufacturer_slug = (
            first.corporate_entity.manufacturer.slug
            if first.corporate_entity and first.corporate_entity.manufacturer
            else None
        )
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
        "abbreviations": [a.value for a in title.abbreviations.all()],
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


def _agreed_value(models, accessor):
    """Return a value if *every* model agrees, else None.

    *accessor* is called with each model and should return the value (or None
    if the model has no data for this field).  The value is only returned when
    **all** models produce the same non-None result; if any model returns None
    or disagrees the result is None.
    """
    values = [accessor(m) for m in models]
    if not values or any(v is None for v in values):
        return None
    first = values[0]
    return first if all(v == first for v in values) else None


def _compute_agreed_specs(models) -> dict:
    """Return spec fields that all *models* agree on."""

    def _fk_pair(m, attr):
        obj = getattr(m, attr, None)
        return (obj.name, obj.slug) if obj else None

    specs: dict = {}

    tg = _agreed_value(models, lambda m: _fk_pair(m, "technology_generation"))
    if tg:
        specs["technology_generation_name"], specs["technology_generation_slug"] = tg

    dt = _agreed_value(models, lambda m: _fk_pair(m, "display_type"))
    if dt:
        specs["display_type_name"], specs["display_type_slug"] = dt

    pc = _agreed_value(models, lambda m: m.player_count)
    if pc is not None:
        specs["player_count"] = pc

    fc = _agreed_value(models, lambda m: m.flipper_count)
    if fc is not None:
        specs["flipper_count"] = fc

    sys = _agreed_value(models, lambda m: _fk_pair(m, "system"))
    if sys:
        specs["system_name"], specs["system_slug"] = sys

    cab = _agreed_value(models, lambda m: _fk_pair(m, "cabinet"))
    if cab:
        specs["cabinet_name"], specs["cabinet_slug"] = cab

    gf = _agreed_value(models, lambda m: _fk_pair(m, "game_format"))
    if gf:
        specs["game_format_name"], specs["game_format_slug"] = gf

    dst = _agreed_value(models, lambda m: _fk_pair(m, "display_subtype"))
    if dst:
        specs["display_subtype_name"], specs["display_subtype_slug"] = dst

    pq = _agreed_value(models, lambda m: m.production_quantity or None)
    if pq:
        specs["production_quantity"] = pq

    # Themes: only roll up when every model has the same set.
    theme_sets = [frozenset((t.slug, t.name) for t in m.themes.all()) for m in models]
    if (
        theme_sets
        and all(ts for ts in theme_sets)
        and all(ts == theme_sets[0] for ts in theme_sets)
    ):
        specs["themes"] = [{"name": n, "slug": s} for s, n in sorted(theme_sets[0])]

    return specs


def _serialize_title_detail(title) -> dict:
    model_objs = list(title.machine_models.all())
    machines = [_serialize_title_machine(pm) for pm in model_objs]
    series = [
        {"name": s.name, "slug": s.slug}
        for s in getattr(title, "series_list", None) or title.series.all()
    ]
    review_links = _build_review_links(title) if title.needs_review else []

    # Hero image from the earliest model.
    hero_image_url = None
    if model_objs:
        _, hero_image_url = _extract_image_urls(model_objs[0].extra_data or {})

    # Credits that appear on every model (intersection, not union).
    credit_sets = []
    credit_data: dict[tuple[str, str], dict] = {}
    for pm in model_objs:
        model_keys: set[tuple[str, str]] = set()
        for c in pm.credits.all():
            key = (c.person.slug, c.role.slug)
            model_keys.add(key)
            credit_data.setdefault(
                key,
                {
                    "person_name": c.person.name,
                    "person_slug": c.person.slug,
                    "role": c.role.slug,
                    "role_display": c.role.name,
                    "role_sort_order": c.role.display_order,
                },
            )
        credit_sets.append(model_keys)

    if credit_sets:
        common_keys = credit_sets[0]
        for s in credit_sets[1:]:
            common_keys &= s
        # Preserve insertion order from credit_data (first model's ordering).
        credits = [v for k, v in credit_data.items() if k in common_keys]
    else:
        credits = []

    # Agreed specs across all models.
    agreed_specs = _compute_agreed_specs(model_objs) if model_objs else {}

    # For single-model titles with no variants, include full model detail inline.
    model_detail = None
    if len(machines) == 1 and not machines[0].get("variants"):
        from .machine_models import _model_detail_qs, _serialize_model_detail

        pm = _model_detail_qs().get(slug=machines[0]["slug"])
        model_detail = _serialize_model_detail(pm)

    return {
        "name": title.name,
        "slug": title.slug,
        "abbreviations": [a.value for a in title.abbreviations.all()],
        "description": title.description,
        **render_markdown_fields(title),
        "needs_review": title.needs_review,
        "needs_review_notes": title.needs_review_notes,
        "review_links": review_links,
        "hero_image_url": hero_image_url,
        "franchise": (
            {"slug": title.franchise.slug, "name": title.franchise.name}
            if title.franchise
            else None
        ),
        "machines": machines,
        "series": series,
        "credits": credits,
        "agreed_specs": agreed_specs,
        "model_detail": model_detail,
    }


def _title_models_prefetch():
    from ..models import MachineModel

    return Prefetch(
        "machine_models",
        queryset=MachineModel.objects.filter(variant_of__isnull=True)
        .select_related(
            "corporate_entity__manufacturer",
            "technology_generation",
            "display_type",
            "display_subtype",
            "system",
            "cabinet",
            "game_format",
        )
        .prefetch_related("themes", "credits__person", "credits__role", "variants")
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
            "machine_models", filter=Q(machine_models__variant_of__isnull=True)
        )
    )
    if display:
        qs = qs.filter(machine_models__display_type__slug=display).distinct()
    qs = (
        qs.select_related("franchise")
        .prefetch_related(_title_models_prefetch(), "series", "abbreviations")
        .order_by("name")
    )
    return [_serialize_title_list(t) for t in qs]


@titles_router.get("/all/", response=list[TitleListSchema])
@decorate_view(cache_control(public=True, max_age=300))
def list_all_titles(request):
    """Return every title with minimal fields (no pagination)."""
    from django.core.cache import cache

    from ..models import Title

    result = cache.get(TITLES_ALL_KEY)
    if result is not None:
        return result

    qs = (
        Title.objects.annotate(
            machine_count=Count(
                "machine_models", filter=Q(machine_models__variant_of__isnull=True)
            ),
            latest_year=Max(
                "machine_models__year",
                filter=Q(machine_models__variant_of__isnull=True),
            ),
        )
        .select_related("franchise")
        .prefetch_related(_title_models_prefetch(), "series", "abbreviations")
        .order_by(F("latest_year").desc(nulls_last=True), "name")
    )
    result = [_serialize_title_list(t) for t in qs]
    cache.set(TITLES_ALL_KEY, result, timeout=None)
    return result


@titles_router.get("/{slug}", response=TitleDetailSchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_title(request, slug: str):
    from ..models import Title

    title = get_object_or_404(
        Title.objects.prefetch_related(
            _title_models_prefetch(), "series", "abbreviations"
        ),
        slug=slug,
    )
    return _serialize_title_detail(title)
