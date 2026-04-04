"""Series router — list, detail, and claims endpoints."""

from __future__ import annotations

from typing import Optional

from django.db.models import Count, F, Prefetch, Q
from django.shortcuts import get_object_or_404

from apps.core.models import active_status_q
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.security import django_auth

from .edit_claims import execute_claims
from apps.provenance.helpers import build_sources, claims_prefetch

from .helpers import (
    _build_rich_text,
    _extract_image_urls,
)
from .machine_models import CreditSchema
from .schemas import ClaimPatchSchema, ClaimSchema, RichTextSchema

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TitleRefSchema(Schema):
    name: str
    slug: str
    abbreviations: list[str] = []
    machine_count: int = 0
    manufacturer_name: Optional[str] = None  # display-only, no paired slug
    year: Optional[int] = None
    thumbnail_url: Optional[str] = None


class SeriesListSchema(Schema):
    name: str
    slug: str
    description: RichTextSchema = RichTextSchema()
    title_count: int = 0
    thumbnail_url: Optional[str] = None


class SeriesDetailSchema(Schema):
    name: str
    slug: str
    description: RichTextSchema = RichTextSchema()
    titles: list[TitleRefSchema]
    credits: list[CreditSchema] = []
    sources: list[ClaimSchema] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_title_list(title) -> dict:
    """Serialize a Title for use in series listing context."""
    thumbnail_url = None
    manufacturer_name = None
    year = None
    machines = list(title.machine_models.all())
    if machines:
        thumbnail_url, _ = _extract_image_urls(machines[0].extra_data or {})
        first = machines[0]
        manufacturer_name = (
            first.corporate_entity.manufacturer.name
            if first.corporate_entity and first.corporate_entity.manufacturer
            else None
        )
        year = first.year
    return {
        "name": title.name,
        "slug": title.slug,
        "abbreviations": [a.value for a in title.abbreviations.all()],
        "machine_count": title.machine_count,
        "manufacturer_name": manufacturer_name,
        "year": year,
        "thumbnail_url": thumbnail_url,
    }


def _series_titles_qs():
    from ..models import MachineModel, Title

    return (
        Title.objects.active()
        .annotate(
            machine_count=Count(
                "machine_models",
                filter=Q(machine_models__variant_of__isnull=True)
                & active_status_q("machine_models"),
            )
        )
        .prefetch_related(
            "abbreviations",
            Prefetch(
                "machine_models",
                queryset=MachineModel.objects.active()
                .filter(variant_of__isnull=True)
                .select_related("corporate_entity__manufacturer")
                .order_by("year", "name"),
            ),
        )
    )


def _series_credits_qs():
    from ..models import Credit

    return Credit.objects.filter(series__isnull=False).select_related("person", "role")


def _series_detail_qs():
    from ..models import Series

    return Series.objects.active().prefetch_related(
        Prefetch("titles", queryset=_series_titles_qs()),
        Prefetch("credits", queryset=_series_credits_qs()),
        claims_prefetch(),
    )


def _serialize_series_detail(series) -> dict:
    return {
        "name": series.name,
        "slug": series.slug,
        "description": _build_rich_text(
            series, "description", getattr(series, "active_claims", [])
        ),
        "titles": [_serialize_title_list(t) for t in series.titles.all()],
        "credits": [
            {
                "person": {"name": c.person.name, "slug": c.person.slug},
                "role": c.role.slug,
                "role_display": c.role.name,
                "role_sort_order": c.role.display_order,
            }
            for c in series.credits.all()
        ],
        "sources": build_sources(getattr(series, "active_claims", [])),
    }


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

series_router = Router(tags=["series"])


@series_router.get("/", response=list[SeriesListSchema])
@decorate_view(cache_control(no_cache=True))
def list_series(request):
    """Return all series with title count and thumbnail."""
    from ..models import MachineModel, Series

    qs = (
        Series.objects.active()
        .annotate(title_count=Count("titles", filter=active_status_q("titles")))
        .prefetch_related(
            Prefetch(
                "titles__machine_models",
                queryset=MachineModel.objects.active()
                .filter(variant_of__isnull=True)
                .exclude(extra_data={})
                .order_by(F("year").asc(nulls_last=True))
                .only("id", "extra_data"),
            )
        )
    )
    result = []
    for s in qs:
        thumb = None
        for title in s.titles.all():
            for pm in title.machine_models.all():
                t, _ = _extract_image_urls(pm.extra_data or {})
                if t:
                    thumb = t
                    break
            if thumb:
                break
        result.append(
            {
                "name": s.name,
                "slug": s.slug,
                "description": _build_rich_text(s, "description"),
                "title_count": s.title_count,
                "thumbnail_url": thumb,
            }
        )
    return result


@series_router.get("/{slug}", response=SeriesDetailSchema)
@decorate_view(cache_control(no_cache=True))
def get_series(request, slug: str):
    series = get_object_or_404(_series_detail_qs(), slug=slug)
    return _serialize_series_detail(series)


@series_router.patch(
    "/{slug}/claims/", auth=django_auth, response=SeriesDetailSchema, tags=["private"]
)
def patch_series_claims(request, slug: str, data: ClaimPatchSchema):
    """Assert per-field claims from the authenticated user, then re-resolve."""
    from ..models import Series
    from .edit_claims import plan_scalar_field_claims

    series = get_object_or_404(Series.objects.active(), slug=slug)
    specs = plan_scalar_field_claims(Series, data.fields, entity=series)

    execute_claims(series, specs, user=request.user)

    series = get_object_or_404(_series_detail_qs(), slug=series.slug)
    return _serialize_series_detail(series)
