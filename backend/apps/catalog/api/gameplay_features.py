"""Gameplay features router — list and detail endpoints."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view

from apps.core.markdown import render_markdown_fields

from .schemas import GameplayFeatureSchema

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
    description: str = ""
    description_html: str = ""
    aliases: list[str] = []
    parents: list[GameplayFeatureSchema] = []
    children: list[GameplayFeatureSchema] = []


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

gameplay_features_router = Router(tags=["gameplay-features"])


@gameplay_features_router.get("/", response=list[GameplayFeatureListSchema])
@decorate_view(cache_control(public=True, max_age=300))
def list_gameplay_features(request):
    from ..models import GameplayFeature, MachineModel

    features = list(
        GameplayFeature.objects.prefetch_related("children", "parents").order_by("name")
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


@gameplay_features_router.get("/{slug}", response=GameplayFeatureDetailSchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_gameplay_feature(request, slug: str):
    from ..models import GameplayFeature

    feature = get_object_or_404(
        GameplayFeature.objects.prefetch_related("parents", "children", "aliases"),
        slug=slug,
    )

    # Display-worthy aliases: exclude those that normalize to the canonical name.
    def _normalize(s: str) -> str:
        s = s.lower().replace("-", "").replace(" ", "")
        if s.endswith("s"):
            s = s[:-1]
        return s

    canonical_norm = _normalize(feature.name)
    display_aliases = [
        a.value for a in feature.aliases.all() if _normalize(a.value) != canonical_norm
    ]

    return {
        "name": feature.name,
        "slug": feature.slug,
        "description": feature.description,
        **render_markdown_fields(feature),
        "aliases": display_aliases,
        "parents": [{"name": p.name, "slug": p.slug} for p in feature.parents.all()],
        "children": [
            {"name": c.name, "slug": c.slug} for c in feature.children.order_by("name")
        ],
    }
