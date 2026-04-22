"""Series router — list, detail, and claims endpoints."""

from __future__ import annotations

from typing import cast

from django.db.models import Count, F, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.security import django_auth

from apps.core.licensing import get_minimum_display_rank
from apps.core.models import active_status_q
from apps.provenance.helpers import claims_prefetch
from apps.provenance.schemas import RichTextSchema
from apps.provenance.typing import HasActiveClaims

from ..models import Credit, MachineModel, Series, Title
from ._typing import HasRelatedTitles, HasTitleCount
from .edit_claims import execute_claims, plan_scalar_field_claims
from .entity_crud import register_entity_create, register_entity_delete_restore
from .helpers import (
    _build_rich_text,
    _extract_image_urls,
    _serialize_credit,
    _serialize_title_ref,
)
from .schemas import (
    ClaimPatchSchema,
    CreditSchema,
    TitleRefSchema,
)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SeriesListSchema(Schema):
    name: str
    slug: str
    description: RichTextSchema = RichTextSchema()
    title_count: int = 0
    thumbnail_url: str | None = None


class SeriesDetailSchema(Schema):
    name: str
    slug: str
    description: RichTextSchema = RichTextSchema()
    titles: list[TitleRefSchema]
    credits: list[CreditSchema] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _series_titles_qs():
    return (
        Title.objects.active()
        .annotate(
            model_count=Count(
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
    return Credit.objects.filter(series__isnull=False).select_related("person", "role")


def _series_detail_qs():
    return Series.objects.active().prefetch_related(
        Prefetch("titles", queryset=_series_titles_qs()),
        Prefetch("credits", queryset=_series_credits_qs()),
        claims_prefetch(),
    )


def _serialize_series_detail(series) -> dict:
    min_rank = get_minimum_display_rank()
    series_with_claims = cast(HasActiveClaims, series)
    series_with_titles = cast(HasRelatedTitles[Title], series)
    return {
        "name": series.name,
        "slug": series.slug,
        "description": _build_rich_text(
            series, "description", series_with_claims.active_claims
        ),
        "titles": [
            _serialize_title_ref(t, min_rank=min_rank)
            for t in series_with_titles.titles.all()
        ],
        "credits": [_serialize_credit(c) for c in series.credits.all()],
    }


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

series_router = Router(tags=["series"])


@series_router.get("/", response=list[SeriesListSchema])
@decorate_view(cache_control(no_cache=True))
def list_series(request):
    """Return all series with title count and thumbnail."""
    qs = (
        Series.objects.active()
        .annotate(title_count=Count("titles", filter=active_status_q("titles")))
        .order_by("-title_count", "name")
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
    min_rank = get_minimum_display_rank()
    result = []
    for s in qs:
        series_with_titles = cast(HasRelatedTitles[Title], s)
        thumb = None
        for title in series_with_titles.titles.all():
            for pm in title.machine_models.all():
                t, _ = _extract_image_urls(pm.extra_data or {}, min_rank=min_rank)
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
                "title_count": cast(HasTitleCount, s).title_count,
                "thumbnail_url": thumb,
            }
        )
    return result


@series_router.patch(
    "/{slug}/claims/", auth=django_auth, response=SeriesDetailSchema, tags=["private"]
)
def patch_series_claims(request, slug: str, data: ClaimPatchSchema):
    """Assert per-field claims from the authenticated user, then re-resolve."""
    series = get_object_or_404(Series.objects.active(), slug=slug)
    specs = plan_scalar_field_claims(Series, data.fields, entity=series)

    execute_claims(
        series, specs, user=request.user, note=data.note, citation=data.citation
    )

    series = get_object_or_404(_series_detail_qs(), slug=series.slug)
    return _serialize_series_detail(series)


# ---------------------------------------------------------------------------
# Create / delete / restore wiring
# ---------------------------------------------------------------------------

register_entity_create(
    series_router,
    Series,
    detail_qs=_series_detail_qs,
    serialize_detail=_serialize_series_detail,
    response_schema=SeriesDetailSchema,
)
register_entity_delete_restore(
    series_router,
    Series,
    detail_qs=_series_detail_qs,
    serialize_detail=_serialize_series_detail,
    response_schema=SeriesDetailSchema,
)
