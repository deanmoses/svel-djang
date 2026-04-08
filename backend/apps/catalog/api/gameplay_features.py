"""Gameplay features router — list, detail, and claims endpoints."""

from __future__ import annotations

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError
from ninja.security import django_auth

from .edit_claims import (
    execute_claims,
    plan_alias_claims,
    plan_parent_claims,
    validate_scalar_fields,
)
from apps.provenance.helpers import build_sources, claims_prefetch

from .helpers import (
    _build_rich_text,
    _media_prefetch,
    _serialize_uploaded_media,
)
from .schemas import (
    ClaimSchema,
    GameplayFeatureSchema,
    HierarchyClaimPatchSchema,
    RichTextSchema,
    UploadedMediaSchema,
)

from ..models import GameplayFeature, MachineModel

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class GameplayFeatureListSchema(Schema):
    name: str
    slug: str
    model_count: int = 0
    parent_slugs: list[str] = []


class GameplayFeatureDetailSchema(Schema):
    name: str
    slug: str
    description: RichTextSchema = RichTextSchema()
    aliases: list[str] = []
    parents: list[GameplayFeatureSchema] = []
    children: list[GameplayFeatureSchema] = []
    uploaded_media: list[UploadedMediaSchema] = []
    sources: list[ClaimSchema] = []


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
            feature, "description", getattr(feature, "active_claims", [])
        ),
        "aliases": [a.value for a in feature.aliases.all()],
        "parents": [{"name": p.name, "slug": p.slug} for p in feature.parents.all()],
        "children": [
            {"name": c.name, "slug": c.slug} for c in feature.children.order_by("name")
        ],
        "uploaded_media": _serialize_uploaded_media(
            getattr(feature, "all_media", None) or []
        ),
        "sources": build_sources(getattr(feature, "active_claims", [])),
    }


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

gameplay_features_router = Router(tags=["gameplay-features"])


@gameplay_features_router.get("/", response=list[GameplayFeatureListSchema])
@decorate_view(cache_control(no_cache=True))
def list_gameplay_features(request):
    features = list(
        GameplayFeature.objects.active()
        .prefetch_related(
            Prefetch("children", queryset=GameplayFeature.objects.active()),
            Prefetch("parents", queryset=GameplayFeature.objects.active()),
        )
        .order_by("name")
    )

    # Build children map for transitive closure.
    children_map: dict[int, list[int]] = {
        f.pk: [c.pk for c in f.children.all()] for f in features
    }

    # Fetch (gameplay_feature_pk, machinemodel_pk) for non-variant machines only.
    Through = MachineModel.gameplay_features.through
    feature_to_model_pks: dict[int, set[int]] = {}
    for gf_pk, mm_pk in Through.objects.filter(
        machinemodel__variant_of__isnull=True
    ).values_list("gameplayfeature_id", "machinemodel_id"):
        feature_to_model_pks.setdefault(gf_pk, set()).add(mm_pk)

    def _get_descendants(pk: int) -> set[int]:
        result: set[int] = {pk}
        stack = [pk]
        while stack:
            current = stack.pop()
            for child_pk in children_map.get(current, []):
                if child_pk not in result:
                    result.add(child_pk)
                    stack.append(child_pk)
        return result

    result = []
    for f in features:
        descendants = _get_descendants(f.pk)
        all_model_pks: set[int] = set()
        for d_pk in descendants:
            all_model_pks |= feature_to_model_pks.get(d_pk, set())
        result.append(
            {
                "name": f.name,
                "slug": f.slug,
                "model_count": len(all_model_pks),
                "parent_slugs": [p.slug for p in f.parents.all()],
            }
        )
    return result


@gameplay_features_router.patch(
    "/{slug}/claims/",
    auth=django_auth,
    response=GameplayFeatureDetailSchema,
    tags=["private"],
)
def patch_gameplay_feature_claims(request, slug: str, data: HierarchyClaimPatchSchema):
    """Assert per-field claims from the authenticated user, then re-resolve."""
    if not data.fields and data.parents is None and data.aliases is None:
        raise HttpError(422, "No changes provided.")

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
        raise HttpError(422, "No changes provided.")

    execute_claims(
        feature,
        specs,
        user=request.user,
        note=data.note,
        citation=data.citation,
    )

    feature = get_object_or_404(_detail_qs(), slug=feature.slug)
    return _serialize_detail(feature)
