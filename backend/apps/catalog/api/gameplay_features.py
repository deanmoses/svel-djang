"""Gameplay features router — list, detail, and claims endpoints."""

from __future__ import annotations

from typing import cast

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.security import django_auth

from apps.media.schemas import UploadedMediaSchema
from apps.provenance.helpers import claims_prefetch
from apps.provenance.schemas import RichTextSchema
from apps.provenance.typing import HasActiveClaims

from ..models import GameplayFeature
from ._counts import bulk_title_counts_via_models
from .edit_claims import (
    execute_claims,
    plan_alias_claims,
    plan_parent_claims,
    raise_form_error,
    validate_scalar_fields,
)
from .entity_crud import register_entity_create, register_entity_delete_restore
from .helpers import (
    _build_rich_text,
    _media_prefetch,
    _serialize_uploaded_media,
)
from .schemas import (
    GameplayFeatureSchema,
    HierarchyClaimPatchSchema,
)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class GameplayFeatureListSchema(Schema):
    name: str
    slug: str
    aliases: list[str] = []
    title_count: int = 0
    parent_slugs: list[str] = []


class GameplayFeatureDetailSchema(Schema):
    name: str
    slug: str
    description: RichTextSchema = RichTextSchema()
    aliases: list[str] = []
    parents: list[GameplayFeatureSchema] = []
    children: list[GameplayFeatureSchema] = []
    uploaded_media: list[UploadedMediaSchema] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detail_qs():
    return GameplayFeature.objects.active().prefetch_related(
        Prefetch("parents", queryset=GameplayFeature.objects.active()),
        Prefetch("children", queryset=GameplayFeature.objects.active()),
        "aliases",
        claims_prefetch(),
        _media_prefetch(),
    )


def _serialize_detail(feature) -> dict:
    return {
        "name": feature.name,
        "slug": feature.slug,
        "description": _build_rich_text(
            feature, "description", cast(HasActiveClaims, feature).active_claims
        ),
        "aliases": [a.value for a in feature.aliases.all()],
        "parents": [{"name": p.name, "slug": p.slug} for p in feature.parents.all()],
        "children": [
            {"name": c.name, "slug": c.slug} for c in feature.children.order_by("name")
        ],
        "uploaded_media": _serialize_uploaded_media(
            getattr(feature, "all_media", None) or []
        ),
    }


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

gameplay_features_router = Router(tags=["gameplay-features"])


@gameplay_features_router.get("/", response=list[GameplayFeatureListSchema])
@decorate_view(cache_control(no_cache=True))
def list_gameplay_features(request):
    features = list(
        GameplayFeature.objects.active().prefetch_related(
            Prefetch("children", queryset=GameplayFeature.objects.active()),
            Prefetch("parents", queryset=GameplayFeature.objects.active()),
            "aliases",
        )
    )

    children_map: dict[int, list[int]] = {
        f.pk: [c.pk for c in f.children.all()] for f in features
    }
    counts = bulk_title_counts_via_models(
        [f.pk for f in features],
        "gameplay_features",
        children_map=children_map,
    )
    features.sort(key=lambda f: (-counts.get(f.pk, 0), f.name.lower()))

    return [
        {
            "name": f.name,
            "slug": f.slug,
            "aliases": [a.value for a in f.aliases.all()],
            "title_count": counts.get(f.pk, 0),
            "parent_slugs": [p.slug for p in f.parents.all()],
        }
        for f in features
    ]


@gameplay_features_router.patch(
    "/{slug}/claims/",
    auth=django_auth,
    response=GameplayFeatureDetailSchema,
    tags=["private"],
)
def patch_gameplay_feature_claims(request, slug: str, data: HierarchyClaimPatchSchema):
    """Assert per-field claims from the authenticated user, then re-resolve."""
    if not data.fields and data.parents is None and data.aliases is None:
        raise_form_error("No changes provided.")

    feature = get_object_or_404(GameplayFeature.objects.active(), slug=slug)

    specs = validate_scalar_fields(GameplayFeature, data.fields, entity=feature)

    if data.parents is not None:
        specs.extend(
            plan_parent_claims(
                feature,
                set(data.parents),
                model_class=GameplayFeature,
                claim_field_name="gameplay_feature_parent",
            )
        )

    if data.aliases is not None:
        specs.extend(
            plan_alias_claims(
                feature,
                data.aliases,
                claim_field_name="gameplay_feature_alias",
            )
        )

    if not specs:
        raise_form_error("No changes provided.")

    execute_claims(
        feature,
        specs,
        user=request.user,
        note=data.note,
        citation=data.citation,
    )

    feature = get_object_or_404(_detail_qs(), slug=feature.slug)
    return _serialize_detail(feature)


# ---------------------------------------------------------------------------
# Create / delete / restore wiring
# ---------------------------------------------------------------------------

register_entity_create(
    gameplay_features_router,
    GameplayFeature,
    detail_qs=_detail_qs,
    serialize_detail=_serialize_detail,
    response_schema=GameplayFeatureDetailSchema,
)
register_entity_delete_restore(
    gameplay_features_router,
    GameplayFeature,
    detail_qs=_detail_qs,
    serialize_detail=_serialize_detail,
    response_schema=GameplayFeatureDetailSchema,
)
