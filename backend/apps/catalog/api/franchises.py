"""Franchises router — list, detail, and claims endpoints."""

from __future__ import annotations

from typing import cast

from django.db.models import Count, Prefetch, Q
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

from ..models import Franchise, MachineModel, Title
from ._typing import HasRelatedTitles, HasTitleCount
from .edit_claims import execute_claims, plan_scalar_field_claims
from .entity_crud import register_entity_create, register_entity_delete_restore
from .helpers import (
    _build_rich_text,
    _serialize_title_ref,
)
from .schemas import ClaimPatchSchema, TitleRefSchema

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class FranchiseListSchema(Schema):
    name: str
    slug: str
    title_count: int = 0


class FranchiseDetailSchema(Schema):
    name: str
    slug: str
    description: RichTextSchema = RichTextSchema()
    titles: list[TitleRefSchema]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

franchises_router = Router(tags=["franchises"])


@franchises_router.get("/", response=list[FranchiseListSchema])
@decorate_view(cache_control(no_cache=True))
def list_franchises(request):
    """Return every franchise with title count (no pagination)."""
    qs = (
        Franchise.objects.active()
        .annotate(title_count=Count("titles", filter=active_status_q("titles")))
        .order_by("-title_count", "name")
    )
    return [
        {
            "name": f.name,
            "slug": f.slug,
            "title_count": cast(HasTitleCount, f).title_count,
        }
        for f in qs
    ]


def _franchise_titles_qs():
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


def _franchise_detail_qs():
    return Franchise.objects.active().prefetch_related(
        Prefetch("titles", queryset=_franchise_titles_qs()), claims_prefetch()
    )


def _serialize_franchise_detail(franchise) -> dict:
    min_rank = get_minimum_display_rank()
    franchise_with_claims = cast(HasActiveClaims, franchise)
    franchise_with_titles = cast(HasRelatedTitles[Title], franchise)
    return {
        "name": franchise.name,
        "slug": franchise.slug,
        "description": _build_rich_text(
            franchise, "description", franchise_with_claims.active_claims
        ),
        "titles": [
            _serialize_title_ref(t, min_rank=min_rank)
            for t in franchise_with_titles.titles.all()
        ],
    }


@franchises_router.patch(
    "/{slug}/claims/",
    auth=django_auth,
    response=FranchiseDetailSchema,
    tags=["private"],
)
def patch_franchise_claims(request, slug: str, data: ClaimPatchSchema):
    """Assert per-field claims from the authenticated user, then re-resolve."""
    franchise = get_object_or_404(Franchise.objects.active(), slug=slug)
    specs = plan_scalar_field_claims(Franchise, data.fields, entity=franchise)

    execute_claims(
        franchise, specs, user=request.user, note=data.note, citation=data.citation
    )

    franchise = get_object_or_404(_franchise_detail_qs(), slug=franchise.slug)
    return _serialize_franchise_detail(franchise)


# ---------------------------------------------------------------------------
# Create / delete / restore wiring
# ---------------------------------------------------------------------------

register_entity_create(
    franchises_router,
    Franchise,
    detail_qs=_franchise_detail_qs,
    serialize_detail=_serialize_franchise_detail,
    response_schema=FranchiseDetailSchema,
)
register_entity_delete_restore(
    franchises_router,
    Franchise,
    detail_qs=_franchise_detail_qs,
    serialize_detail=_serialize_franchise_detail,
    response_schema=FranchiseDetailSchema,
)
