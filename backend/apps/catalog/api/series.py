"""Series router — list and detail endpoints."""

from __future__ import annotations

from typing import Optional

from django.db.models import Count, F, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view

from .helpers import _extract_image_urls

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TitleRefSchema(Schema):
    name: str
    slug: str
    short_name: str
    machine_count: int = 0
    manufacturer_name: Optional[str] = None
    year: Optional[int] = None
    thumbnail_url: Optional[str] = None


class SeriesListSchema(Schema):
    name: str
    slug: str
    description: str = ""
    title_count: int = 0
    thumbnail_url: Optional[str] = None


class SeriesDetailSchema(Schema):
    name: str
    slug: str
    description: str = ""
    titles: list[TitleRefSchema]


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
        manufacturer_name = first.manufacturer.name if first.manufacturer else None
        year = first.year
    return {
        "name": title.name,
        "slug": title.slug,
        "short_name": title.short_name,
        "machine_count": title.machine_count,
        "manufacturer_name": manufacturer_name,
        "year": year,
        "thumbnail_url": thumbnail_url,
    }


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

series_router = Router(tags=["series"])


@series_router.get("/", response=list[SeriesListSchema])
@decorate_view(cache_control(public=True, max_age=300))
def list_series(request):
    """Return all series with title count and thumbnail."""
    from ..models import MachineModel, Series

    qs = Series.objects.annotate(title_count=Count("titles")).prefetch_related(
        Prefetch(
            "titles__machine_models",
            queryset=MachineModel.objects.filter(alias_of__isnull=True)
            .exclude(extra_data={})
            .order_by(F("year").asc(nulls_last=True))
            .only("id", "extra_data"),
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
                "description": s.description,
                "title_count": s.title_count,
                "thumbnail_url": thumb,
            }
        )
    return result


@series_router.get("/{slug}", response=SeriesDetailSchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_series(request, slug: str):
    from ..models import MachineModel, Series, Title

    titles_qs = Title.objects.annotate(
        machine_count=Count(
            "machine_models",
            filter=Q(machine_models__alias_of__isnull=True),
        )
    ).prefetch_related(
        Prefetch(
            "machine_models",
            queryset=MachineModel.objects.filter(alias_of__isnull=True)
            .select_related("manufacturer")
            .order_by("year", "name"),
        )
    )
    series = get_object_or_404(
        Series.objects.prefetch_related(Prefetch("titles", queryset=titles_qs)),
        slug=slug,
    )
    return {
        "name": series.name,
        "slug": series.slug,
        "description": series.description,
        "titles": [_serialize_title_list(t) for t in series.titles.all()],
    }
