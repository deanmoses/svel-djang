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
)
from apps.provenance.helpers import build_sources, claims_prefetch

from .helpers import (
    _build_rich_text,
    _extract_image_urls,
    _serialize_title_machine,
)
from .machine_models import CreditSchema, MachineModelDetailSchema
from .schemas import (
    ClaimSchema,
    GameplayFeatureSchema,
    RichTextSchema,
    SeriesRefSchema,
    ThemeSchema,
    TitleMachineSchema,
)
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
        thumbnail_url, _ = _extract_image_urls(machines[0].extra_data or {})
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
    from ..models import Title

    links: list[dict] = []

    # Related titles by name match (only OPDB-backed ones).
    import re

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

    tg = _agreed_value(models, lambda m: _fk_pair(m, "technology_generation"))
    if tg:
        specs["technology_generation"] = {"name": tg[0], "slug": tg[1]}

    dt = _agreed_value(models, lambda m: _fk_pair(m, "display_type"))
    if dt:
        specs["display_type"] = {"name": dt[0], "slug": dt[1]}

    pc = _agreed_value(models, lambda m: m.player_count)
    if pc is not None:
        specs["player_count"] = pc

    fc = _agreed_value(models, lambda m: m.flipper_count)
    if fc is not None:
        specs["flipper_count"] = fc

    sys = _agreed_value(models, lambda m: _fk_pair(m, "system"))
    if sys:
        specs["system"] = {"name": sys[0], "slug": sys[1]}

    cab = _agreed_value(models, lambda m: _fk_pair(m, "cabinet"))
    if cab:
        specs["cabinet"] = {"name": cab[0], "slug": cab[1]}

    gf = _agreed_value(models, lambda m: _fk_pair(m, "game_format"))
    if gf:
        specs["game_format"] = {"name": gf[0], "slug": gf[1]}

    dst = _agreed_value(models, lambda m: _fk_pair(m, "display_subtype"))
    if dst:
        specs["display_subtype"] = {"name": dst[0], "slug": dst[1]}

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

    # Gameplay features: intersection across all models.
    # Build {slug: (name, count)} per model from prefetched through-model rows.
    gf_maps: list[dict[str, tuple[str, int | None]]] = []
    for m in models:
        gf_map: dict[str, tuple[str, int | None]] = {}
        for t in m.machinemodelgameplayfeature_set.all():
            gf_map[t.gameplayfeature.slug] = (t.gameplayfeature.name, t.count)
        gf_maps.append(gf_map)

    if gf_maps and all(gf_maps):
        # Intersect on slug; include count only when all models agree.
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
    rt_sets = [
        frozenset((rt.slug, rt.name) for rt in m.reward_types.all()) for m in models
    ]
    if rt_sets and all(rt_sets):
        common = rt_sets[0]
        for s in rt_sets[1:]:
            common &= s
        if common:
            specs["reward_types"] = [{"slug": s, "name": n} for s, n in sorted(common)]

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
                    "person": {"name": c.person.name, "slug": c.person.slug},
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
    from ..models import MachineModel, MachineModelGameplayFeature

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
    from ..models import Title

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
    from ..models import Title

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
    return [_serialize_title_list(t) for t in qs]


@titles_router.get("/all/", response=list[TitleListSchema])
@decorate_view(cache_control(no_cache=True))
def list_all_titles(request):
    """Return every title with minimal fields (no pagination)."""
    from django.core.cache import cache

    from ..models import Title

    result = cache.get(TITLES_ALL_KEY)
    if result is not None:
        return result

    qs = (
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
        )
        .select_related("franchise")
        .prefetch_related(_title_models_prefetch(), "series", "abbreviations")
        .order_by(F("latest_year").desc(nulls_last=True), "name")
    )
    result = [_serialize_title_list(t) for t in qs]
    cache.set(TITLES_ALL_KEY, result, timeout=None)
    return result


@titles_router.get("/{slug}", response=TitleDetailSchema)
@decorate_view(cache_control(no_cache=True))
def get_title(request, slug: str):
    title = get_object_or_404(_detail_qs(), slug=slug)
    return _serialize_title_detail(title)


@titles_router.patch(
    "/{slug}/claims/",
    auth=django_auth,
    response=TitleDetailSchema,
    tags=["private"],
)
def patch_title_claims(request, slug: str, data: TitleClaimPatchSchema):
    """Assert title-owned claims and return the refreshed title detail."""
    from ..models import Title
    from ..resolve._relationships import resolve_all_title_abbreviations
    from .edit_claims import plan_scalar_field_claims

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

    resolvers = []
    if data.abbreviations is not None:
        abbreviation_specs = plan_abbreviation_claims(title, data.abbreviations)
        specs.extend(abbreviation_specs)
        if abbreviation_specs:
            resolvers.append(
                lambda: resolve_all_title_abbreviations(model_ids={title.pk})
            )

    if not specs:
        raise HttpError(422, "No changes provided.")

    execute_claims(title, specs, user=request.user, note=data.note, resolvers=resolvers)

    title = get_object_or_404(_detail_qs(), slug=title.slug)
    return _serialize_title_detail(title)
