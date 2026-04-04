"""Corporate entities router — list, detail, and claims endpoints."""

from __future__ import annotations

from typing import Optional

from django.db.models import Count, F, Prefetch, Q
from django.shortcuts import get_object_or_404

from apps.core.models import active_status_q
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError
from ninja.security import django_auth

from .edit_claims import execute_claims, plan_alias_claims, validate_scalar_fields
from apps.provenance.helpers import build_sources, claims_prefetch

from .helpers import (
    _build_rich_text,
    _collect_titles,
    _serialize_locations,
)
from .manufacturers import CorporateEntityLocationSchema
from .schemas import (
    ClaimSchema,
    CorporateEntityClaimPatchSchema,
    RelatedTitleSchema,
    RichTextSchema,
)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ManufacturerRef(Schema):
    name: str
    slug: str


class CorporateEntityListSchema(Schema):
    name: str
    slug: str
    manufacturer: ManufacturerRef
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    model_count: int = 0
    locations: list[CorporateEntityLocationSchema] = []


class CorporateEntityDetailSchema(Schema):
    name: str
    slug: str
    description: RichTextSchema = RichTextSchema()
    manufacturer: ManufacturerRef
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    aliases: list[str] = []
    locations: list[CorporateEntityLocationSchema] = []
    titles: list[RelatedTitleSchema]
    sources: list[ClaimSchema] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detail_qs():
    from ..models import CorporateEntity, CorporateEntityLocation, MachineModel

    return (
        CorporateEntity.objects.active()
        .select_related("manufacturer")
        .prefetch_related(
            "aliases",
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
                .order_by(F("year").desc(nulls_last=True), "name"),
            ),
            claims_prefetch(),
        )
    )


def _serialize_detail(ce) -> dict:
    return {
        "name": ce.name,
        "slug": ce.slug,
        "description": _build_rich_text(
            ce, "description", getattr(ce, "active_claims", [])
        ),
        "manufacturer": {"name": ce.manufacturer.name, "slug": ce.manufacturer.slug},
        "year_start": ce.year_start,
        "year_end": ce.year_end,
        "aliases": [a.value for a in ce.aliases.all()],
        "locations": _serialize_locations(ce),
        "titles": _collect_titles(ce.models.all()),
        "sources": build_sources(getattr(ce, "active_claims", [])),
    }


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

corporate_entities_router = Router(tags=["corporate-entities"])


@corporate_entities_router.get("/", response=list[CorporateEntityListSchema])
@decorate_view(cache_control(no_cache=True))
def list_corporate_entities(request):
    from ..models import CorporateEntity, CorporateEntityLocation

    qs = (
        CorporateEntity.objects.active()
        .select_related("manufacturer")
        .annotate(
            model_count=Count(
                "models",
                filter=Q(models__variant_of__isnull=True) & active_status_q("models"),
            )
        )
        .prefetch_related(
            Prefetch(
                "locations",
                queryset=CorporateEntityLocation.objects.select_related(
                    "location__parent__parent__parent"
                ),
            ),
        )
        .order_by("manufacturer__name", "year_start")
    )
    return [
        {
            "name": ce.name,
            "slug": ce.slug,
            "manufacturer": {
                "name": ce.manufacturer.name,
                "slug": ce.manufacturer.slug,
            },
            "year_start": ce.year_start,
            "year_end": ce.year_end,
            "model_count": ce.model_count,
            "locations": _serialize_locations(ce),
        }
        for ce in qs
    ]


@corporate_entities_router.get("/{slug}", response=CorporateEntityDetailSchema)
@decorate_view(cache_control(no_cache=True))
def get_corporate_entity(request, slug: str):
    ce = get_object_or_404(_detail_qs(), slug=slug)
    return _serialize_detail(ce)


@corporate_entities_router.patch(
    "/{slug}/claims/",
    auth=django_auth,
    response=CorporateEntityDetailSchema,
    tags=["private"],
)
def patch_corporate_entity_claims(
    request, slug: str, data: CorporateEntityClaimPatchSchema
):
    """Assert per-field claims from the authenticated user, then re-resolve."""
    from ..models import CorporateEntity
    from ..resolve._relationships import resolve_corporate_entity_aliases

    if not data.fields and data.aliases is None:
        raise HttpError(422, "No changes provided.")

    ce = get_object_or_404(CorporateEntity.objects.active(), slug=slug)

    specs = validate_scalar_fields(CorporateEntity, data.fields, entity=ce)

    resolvers = []
    if data.aliases is not None:
        alias_specs = plan_alias_claims(
            ce,
            data.aliases,
            claim_field_name="corporate_entity_alias",
        )
        specs.extend(alias_specs)
        if alias_specs:
            resolvers.append(resolve_corporate_entity_aliases)

    if not specs:
        raise HttpError(422, "No changes provided.")

    execute_claims(ce, specs, user=request.user, note=data.note, resolvers=resolvers)

    ce = get_object_or_404(_detail_qs(), slug=ce.slug)
    return _serialize_detail(ce)
