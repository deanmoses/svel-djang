"""Titles router — list, detail, and claims endpoints."""

from __future__ import annotations

from typing import Any, Optional

from django.db.models import Count, F, Max, Prefetch, Q
from django.shortcuts import get_object_or_404

from apps.core.models import active_status_q
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError
from ninja.pagination import PageNumberPagination, paginate
from ninja.security import django_auth

from .constants import DEFAULT_PAGE_SIZE
from .edit_claims import (
    execute_claims,
    plan_abbreviation_claims,
    plan_scalar_field_claims,
)
from apps.provenance.helpers import build_sources, claims_prefetch

from .helpers import (
    _build_rich_text,
    _extract_image_urls,
    _intersect_facet_sets,
    _serialize_credit,
    _serialize_title_machine,
)
from .machine_models import CreditSchema, MachineModelDetailSchema
from .schemas import (
    ClaimSchema,
    EditCitationInput,
    GameplayFeatureSchema,
    RichTextSchema,
    SeriesRefSchema,
    ThemeSchema,
    TitleMachineSchema,
)
import re
from collections import defaultdict

from django.db.models import Min, OuterRef, Subquery

from apps.core.licensing import get_minimum_display_rank

from ..cache import TITLES_ALL_KEY, get_cached_response, set_cached_response
from ..models import (
    Credit,
    MachineModel,
    MachineModelGameplayFeature,
    Title,
    TitleAbbreviation,
)

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
    manufacturer: Optional[FacetRef] = None
    year: Optional[int] = None
    thumbnail_url: Optional[str] = None
    # Facet data — aggregated from non-variant models
    tech_generations: list[FacetRef] = []
    display_types: list[FacetRef] = []
    player_counts: list[int] = []
    systems: list[FacetRef] = []
    themes: list[FacetRef] = []
    gameplay_features: list[FacetRef] = []
    reward_types: list[FacetRef] = []
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

    technology_generation: Optional[FacetRef] = None
    display_type: Optional[FacetRef] = None
    player_count: Optional[int] = None
    flipper_count: Optional[int] = None
    system: Optional[FacetRef] = None
    cabinet: Optional[FacetRef] = None
    game_format: Optional[FacetRef] = None
    display_subtype: Optional[FacetRef] = None
    themes: list[ThemeSchema] = []
    gameplay_features: list[GameplayFeatureSchema] = []
    reward_types: list[FacetRef] = []
    production_quantity: Optional[str] = None


class TitleDetailSchema(Schema):
    name: str
    slug: str
    abbreviations: list[str] = []
    description: RichTextSchema = RichTextSchema()
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
    sources: list[ClaimSchema] = []


class TitleClaimPatchSchema(Schema):
    fields: dict[str, Any] = {}
    abbreviations: list[str] | None = None
    note: str = ""
    citation: EditCitationInput | None = None


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


def _serialize_title_list(title, *, min_rank: int | None = None) -> dict:
    thumbnail_url = None
    manufacturer = None
    year = None
    machines = list(title.machine_models.all())

    # Collect facet data from all non-variant models
    tech_gen_pairs = []
    display_type_pairs = []
    player_counts_set: set[int] = set()
    system_pairs = []
    theme_pairs = []
    gameplay_feature_pairs = []
    reward_type_pairs = []
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
        for gf in m.gameplay_features.all():
            gameplay_feature_pairs.append((gf.slug, gf.name))
        for rt in m.reward_types.all():
            reward_type_pairs.append((rt.slug, rt.name))
        for credit in m.credits.all():
            person_pairs.append((credit.person.slug, credit.person.name))
        if m.year is not None:
            years.append(m.year)
        if m.ipdb_rating is not None:
            ratings.append(float(m.ipdb_rating))

    if machines:
        thumbnail_url, _ = _extract_image_urls(
            machines[0].extra_data or {}, min_rank=min_rank
        )
        first = machines[0]
        mfr = (
            first.corporate_entity.manufacturer
            if first.corporate_entity and first.corporate_entity.manufacturer
            else None
        )
        manufacturer = {"slug": mfr.slug, "name": mfr.name} if mfr else None
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
        "manufacturer": manufacturer,
        "year": year,
        "thumbnail_url": thumbnail_url,
        "tech_generations": _dedup_facet_refs(tech_gen_pairs),
        "display_types": _dedup_facet_refs(display_type_pairs),
        "player_counts": sorted(player_counts_set),
        "systems": _dedup_facet_refs(system_pairs),
        "themes": _dedup_facet_refs(theme_pairs),
        "gameplay_features": _dedup_facet_refs(gameplay_feature_pairs),
        "reward_types": _dedup_facet_refs(reward_type_pairs),
        "persons": _dedup_facet_refs(person_pairs),
        "franchise": franchise,
        "series": series_list,
        "year_min": min(years) if years else None,
        "year_max": max(years) if years else None,
        "ipdb_rating_max": max(ratings) if ratings else None,
    }


def _build_review_links(title) -> list[dict]:
    """Build external/internal review links for a needs_review title."""
    links: list[dict] = []

    # Related titles by name match (only OPDB-backed ones).
    base_name = re.sub(r"\s*\([^)]*\)\s*$", "", title.name).strip()
    related = (
        Title.objects.active()
        .filter(Q(name__iexact=title.name) | Q(name__iexact=base_name))
        .exclude(pk=title.pk)
        .exclude(opdb_id__isnull=True)
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

    for key, attr in (
        ("technology_generation", "technology_generation"),
        ("display_type", "display_type"),
        ("system", "system"),
        ("cabinet", "cabinet"),
        ("game_format", "game_format"),
        ("display_subtype", "display_subtype"),
    ):
        val = _agreed_value(models, lambda m, a=attr: _fk_pair(m, a))
        if val:
            specs[key] = {"name": val[0], "slug": val[1]}

    pc = _agreed_value(models, lambda m: m.player_count)
    if pc is not None:
        specs["player_count"] = pc

    fc = _agreed_value(models, lambda m: m.flipper_count)
    if fc is not None:
        specs["flipper_count"] = fc

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

    # Gameplay features: intersection across all models (with count agreement).
    gf_maps: list[dict[str, tuple[str, int | None]]] = []
    for m in models:
        gf_map: dict[str, tuple[str, int | None]] = {}
        for t in m.machinemodelgameplayfeature_set.all():
            gf_map[t.gameplayfeature.slug] = (t.gameplayfeature.name, t.count)
        gf_maps.append(gf_map)

    if gf_maps and all(gf_maps):
        common_slugs = set(gf_maps[0])
        for gf_map in gf_maps[1:]:
            common_slugs &= set(gf_map)
        if common_slugs:
            result = []
            for slug in sorted(common_slugs):
                name = gf_maps[0][slug][0]
                counts = [gf_map[slug][1] for gf_map in gf_maps]
                count = counts[0] if all(c == counts[0] for c in counts) else None
                result.append({"slug": slug, "name": name, "count": count})
            specs["gameplay_features"] = result

    # Reward types: intersection across all models.
    rt = _intersect_facet_sets(models, "reward_types")
    if rt:
        specs["reward_types"] = rt

    return specs


def _serialize_title_detail(title) -> dict:
    min_rank = get_minimum_display_rank()
    model_objs = list(title.machine_models.all())
    machines = [_serialize_title_machine(pm, min_rank=min_rank) for pm in model_objs]
    series = [
        {"name": s.name, "slug": s.slug}
        for s in getattr(title, "series_list", None) or title.series.all()
    ]
    review_links = _build_review_links(title) if title.needs_review else []

    # Hero image from the earliest model.
    hero_image_url = None
    if model_objs:
        _, hero_image_url = _extract_image_urls(
            model_objs[0].extra_data or {}, min_rank=min_rank
        )

    # Credits that appear on every model (intersection, not union).
    credit_sets = []
    credit_data: dict[tuple[str, str], dict] = {}
    for pm in model_objs:
        model_keys: set[tuple[str, str]] = set()
        for c in pm.credits.all():
            key = (c.person.slug, c.role.slug)
            model_keys.add(key)
            credit_data.setdefault(key, _serialize_credit(c))
        credit_sets.append(model_keys)

    if credit_sets:
        common_keys = credit_sets[0]
        for s in credit_sets[1:]:
            common_keys &= s
        credits = [v for k, v in credit_data.items() if k in common_keys]
    else:
        credits = []

    # Agreed specs across all models.
    agreed_specs = _compute_agreed_specs(model_objs) if model_objs else {}

    # For single-model titles with no variants, include full model detail inline.
    model_detail = None
    if len(machines) == 1 and not machines[0].get("variants"):
        from .machine_models import _model_detail_qs, _serialize_model_detail  # noqa: E402 — avoid circular at module level

        pm = _model_detail_qs().get(slug=machines[0]["slug"])
        model_detail = _serialize_model_detail(pm)

    description = _build_rich_text(
        title, "description", getattr(title, "active_claims", [])
    )

    return {
        "name": title.name,
        "slug": title.slug,
        "abbreviations": [a.value for a in title.abbreviations.all()],
        "description": description,
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
        "sources": build_sources(getattr(title, "active_claims", [])),
    }


def _title_models_prefetch():
    return Prefetch(
        "machine_models",
        queryset=MachineModel.objects.active()
        .filter(variant_of__isnull=True)
        .select_related(
            "corporate_entity__manufacturer",
            "technology_generation",
            "display_type",
            "display_subtype",
            "system",
            "cabinet",
            "game_format",
        )
        .prefetch_related(
            "themes",
            "gameplay_features",
            Prefetch(
                "machinemodelgameplayfeature_set",
                queryset=MachineModelGameplayFeature.objects.select_related(
                    "gameplayfeature"
                ),
            ),
            "reward_types",
            "credits__person",
            "credits__role",
            "variants",
        )
        .order_by("year", "name"),
    )


def _detail_qs():
    return (
        Title.objects.active()
        .select_related("franchise")
        .prefetch_related(
            _title_models_prefetch(),
            "series",
            "abbreviations",
            claims_prefetch(),
        )
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

titles_router = Router(tags=["titles"])


@titles_router.get("/", response=list[TitleListSchema])
@paginate(PageNumberPagination, page_size=DEFAULT_PAGE_SIZE)
def list_titles(request, display: str = ""):
    qs = Title.objects.active().annotate(
        machine_count=Count(
            "machine_models",
            filter=Q(machine_models__variant_of__isnull=True)
            & active_status_q("machine_models"),
        )
    )
    if display:
        qs = qs.filter(machine_models__display_type__slug=display).distinct()
    qs = (
        qs.select_related("franchise")
        .prefetch_related(_title_models_prefetch(), "series", "abbreviations")
        .order_by("name")
    )
    min_rank = get_minimum_display_rank()
    return [_serialize_title_list(t, min_rank=min_rank) for t in qs]


@titles_router.get("/all/", response=list[TitleListSchema])
@decorate_view(cache_control(no_cache=True))
def list_all_titles(request):
    """Return every title with facet data for client-side filtering.

    Performance-critical: this serializes ~6k titles with facet arrays
    aggregated from ~7k machine models.  The result is cached indefinitely
    and invalidated on data changes, so cold-cache rebuild speed matters.

    Strategy (instead of prefetch + ORM iteration):
    1. Annotate scalar card fields (manufacturer, year) via correlated
       subqueries so the DB does the work in one SQL statement.
    2. Use ``values_list`` instead of full ORM object instantiation to
       avoid Python-side hydration overhead for thousands of rows.
    3. Fetch M2M facet data (themes, features, credits, etc.) via bulk
       queries on through tables into ``dict`` lookup maps.
    4. Assemble the response dicts from the lookup maps.

    This reduces cold-cache rebuild from ~3.5s to ~0.5s locally
    (~30s to ~5s on production hardware).
    """
    response = get_cached_response(TITLES_ALL_KEY)
    if response is not None:
        return response

    # Cached once for the entire rebuild — avoids ~6k Constance DB lookups.
    min_rank = get_minimum_display_rank()

    # "First model" = earliest non-variant model by (year, name), used to
    # derive the title's display manufacturer, year, and thumbnail.
    first_model = (
        MachineModel.objects.filter(title=OuterRef("pk"), variant_of__isnull=True)
        .active()
        .order_by("year", "name")
    )
    # Column indices for the values_list below.
    T_ID = 0
    T_NAME = 1
    T_SLUG = 2
    T_MACHINE_COUNT = 3
    T_LATEST_YEAR = 4
    T_MFR_SLUG = 5
    T_MFR_NAME = 6
    T_PRIMARY_YEAR = 7
    T_PRIMARY_MODEL_ID = 8
    T_YEAR_MIN = 9
    T_IPDB_RATING_MAX = 10
    T_FRANCHISE_SLUG = 11
    T_FRANCHISE_NAME = 12

    title_rows = list(
        Title.objects.active()
        .annotate(
            machine_count=Count(
                "machine_models",
                filter=Q(machine_models__variant_of__isnull=True)
                & active_status_q("machine_models"),
            ),
            latest_year=Max(
                "machine_models__year",
                filter=Q(machine_models__variant_of__isnull=True),
            ),
            primary_mfr_slug=Subquery(
                first_model.values("corporate_entity__manufacturer__slug")[:1]
            ),
            primary_mfr_name=Subquery(
                first_model.values("corporate_entity__manufacturer__name")[:1]
            ),
            primary_year=Subquery(first_model.values("year")[:1]),
            primary_model_id=Subquery(first_model.values("pk")[:1]),
            year_min=Min(
                "machine_models__year",
                filter=Q(machine_models__variant_of__isnull=True),
            ),
            ipdb_rating_max=Max(
                "machine_models__ipdb_rating",
                filter=Q(machine_models__variant_of__isnull=True),
            ),
        )
        .values_list(
            "id",
            "name",
            "slug",
            "machine_count",
            "latest_year",
            "primary_mfr_slug",
            "primary_mfr_name",
            "primary_year",
            "primary_model_id",
            "year_min",
            "ipdb_rating_max",
            "franchise__slug",
            "franchise__name",
        )
        .order_by(F("latest_year").desc(nulls_last=True), "name")
    )

    # --- Batch thumbnail fetch ---
    primary_model_ids = [
        r[T_PRIMARY_MODEL_ID] for r in title_rows if r[T_PRIMARY_MODEL_ID]
    ]
    thumb_data: dict[int, str | None] = {}
    for mid, extra_data in MachineModel.objects.filter(
        id__in=primary_model_ids
    ).values_list("id", "extra_data"):
        if extra_data:
            thumb, _ = _extract_image_urls(extra_data, min_rank=min_rank)
            thumb_data[mid] = thumb
        else:
            thumb_data[mid] = None

    # --- Bulk abbreviations and series ---
    title_ids = [r[T_ID] for r in title_rows]

    title_abbrevs: dict[int, list[str]] = defaultdict(list)
    for tid, value in TitleAbbreviation.objects.filter(
        title_id__in=title_ids
    ).values_list("title_id", "value"):
        title_abbrevs[tid].append(value)

    title_series: dict[int, list[tuple[str, str]]] = defaultdict(list)
    Series = Title.series.through
    for tid, slug, name in Series.objects.filter(title_id__in=title_ids).values_list(
        "title_id", "series__slug", "series__name"
    ):
        title_series[tid].append((slug, name))

    # --- Bulk facet queries via through tables ---
    model_qs = MachineModel.objects.filter(
        title__isnull=False, variant_of__isnull=True
    ).active()

    title_model_map: dict[int, list[int]] = defaultdict(list)
    model_ids: set[int] = set()
    for title_id, model_id in model_qs.values_list("title_id", "id"):
        title_model_map[title_id].append(model_id)
        model_ids.add(model_id)

    model_tech_gen: dict[int, tuple[str, str]] = {}
    for mid, slug, name in model_qs.filter(
        technology_generation__isnull=False
    ).values_list("id", "technology_generation__slug", "technology_generation__name"):
        model_tech_gen[mid] = (slug, name)

    model_display: dict[int, tuple[str, str]] = {}
    for mid, slug, name in model_qs.filter(display_type__isnull=False).values_list(
        "id", "display_type__slug", "display_type__name"
    ):
        model_display[mid] = (slug, name)

    model_system: dict[int, tuple[str, str]] = {}
    for mid, slug, name in model_qs.filter(system__isnull=False).values_list(
        "id", "system__slug", "system__name"
    ):
        model_system[mid] = (slug, name)

    model_player_count: dict[int, int | None] = {}
    for mid, pc in model_qs.values_list("id", "player_count"):
        model_player_count[mid] = pc

    model_themes: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for mid, slug, name in MachineModel.themes.through.objects.filter(
        machinemodel_id__in=model_ids
    ).values_list("machinemodel_id", "theme__slug", "theme__name"):
        model_themes[mid].append((slug, name))

    model_gf: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for mid, slug, name in MachineModel.gameplay_features.through.objects.filter(
        machinemodel_id__in=model_ids
    ).values_list(
        "machinemodel_id",
        "gameplayfeature__slug",
        "gameplayfeature__name",
    ):
        model_gf[mid].append((slug, name))

    model_rt: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for mid, slug, name in MachineModel.reward_types.through.objects.filter(
        machinemodel_id__in=model_ids
    ).values_list("machinemodel_id", "rewardtype__slug", "rewardtype__name"):
        model_rt[mid].append((slug, name))

    model_persons: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for mid, slug, name in Credit.objects.filter(model_id__in=model_ids).values_list(
        "model_id", "person__slug", "person__name"
    ):
        model_persons[mid].append((slug, name))

    # --- Assembly ---
    result = []
    for r in title_rows:
        tid = r[T_ID]
        mids = title_model_map.get(tid, [])

        mfr = {"slug": r[T_MFR_SLUG], "name": r[T_MFR_NAME]} if r[T_MFR_SLUG] else None
        franchise = (
            {"slug": r[T_FRANCHISE_SLUG], "name": r[T_FRANCHISE_NAME]}
            if r[T_FRANCHISE_SLUG]
            else None
        )

        result.append(
            {
                "name": r[T_NAME],
                "slug": r[T_SLUG],
                "abbreviations": title_abbrevs.get(tid, []),
                "machine_count": r[T_MACHINE_COUNT],
                "manufacturer": mfr,
                "year": r[T_PRIMARY_YEAR],
                "thumbnail_url": thumb_data.get(r[T_PRIMARY_MODEL_ID]),
                "tech_generations": _dedup_facet_refs(
                    model_tech_gen[mid] for mid in mids if mid in model_tech_gen
                ),
                "display_types": _dedup_facet_refs(
                    model_display[mid] for mid in mids if mid in model_display
                ),
                "player_counts": sorted(
                    {
                        model_player_count[mid]
                        for mid in mids
                        if model_player_count.get(mid) is not None
                    }
                ),
                "systems": _dedup_facet_refs(
                    model_system[mid] for mid in mids if mid in model_system
                ),
                "themes": _dedup_facet_refs(
                    p for mid in mids for p in model_themes.get(mid, [])
                ),
                "gameplay_features": _dedup_facet_refs(
                    p for mid in mids for p in model_gf.get(mid, [])
                ),
                "reward_types": _dedup_facet_refs(
                    p for mid in mids for p in model_rt.get(mid, [])
                ),
                "persons": _dedup_facet_refs(
                    p for mid in mids for p in model_persons.get(mid, [])
                ),
                "franchise": franchise,
                "series": [
                    {"slug": s, "name": n} for s, n in title_series.get(tid, [])
                ],
                "year_min": r[T_YEAR_MIN],
                "year_max": r[T_LATEST_YEAR],
                "ipdb_rating_max": (
                    float(r[T_IPDB_RATING_MAX]) if r[T_IPDB_RATING_MAX] else None
                ),
            }
        )
    return set_cached_response(TITLES_ALL_KEY, result)


@titles_router.patch(
    "/{slug}/claims/",
    auth=django_auth,
    response=TitleDetailSchema,
    tags=["private"],
)
def patch_title_claims(request, slug: str, data: TitleClaimPatchSchema):
    """Assert title-owned claims and return the refreshed title detail."""
    if not data.fields and data.abbreviations is None:
        raise HttpError(422, "No changes provided.")

    title = get_object_or_404(
        Title.objects.active().prefetch_related("abbreviations"), slug=slug
    )
    specs = (
        plan_scalar_field_claims(Title, data.fields, entity=title)
        if data.fields
        else []
    )

    if data.abbreviations is not None:
        specs.extend(plan_abbreviation_claims(title, data.abbreviations))

    if not specs:
        raise HttpError(422, "No changes provided.")

    execute_claims(
        title,
        specs,
        user=request.user,
        note=data.note,
        citation=data.citation,
    )

    title = get_object_or_404(_detail_qs(), slug=title.slug)
    return _serialize_title_detail(title)
