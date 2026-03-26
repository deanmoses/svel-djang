"""Gameplay features router — list, detail, and claims endpoints."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError
from ninja.security import django_auth

from .edit_claims import ClaimSpec, execute_claims, validate_scalar_fields
from .helpers import _build_activity, _build_rich_text, _claims_prefetch
from .schemas import (
    ClaimSchema,
    GameplayFeatureClaimPatchSchema,
    GameplayFeatureSchema,
    RichTextSchema,
)

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
    activity: list[ClaimSchema] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detail_qs():
    from ..models import GameplayFeature

    return GameplayFeature.objects.prefetch_related(
        "parents", "children", "aliases", _claims_prefetch()
    )


def _normalize(s: str) -> str:
    s = s.lower().replace("-", "").replace(" ", "")
    if s.endswith("s"):
        s = s[:-1]
    return s


def _serialize_detail(feature) -> dict:
    canonical_norm = _normalize(feature.name)
    display_aliases = [
        a.value for a in feature.aliases.all() if _normalize(a.value) != canonical_norm
    ]
    return {
        "name": feature.name,
        "slug": feature.slug,
        "description": _build_rich_text(
            feature, "description", getattr(feature, "active_claims", [])
        ),
        "aliases": display_aliases,
        "parents": [{"name": p.name, "slug": p.slug} for p in feature.parents.all()],
        "children": [
            {"name": c.name, "slug": c.slug} for c in feature.children.order_by("name")
        ],
        "activity": _build_activity(getattr(feature, "active_claims", [])),
    }


def _plan_parent_claims(feature, desired_slugs: set[str]) -> list[ClaimSpec]:
    """Validate parents and return diff-based ClaimSpecs.

    Parent relationships are diff-based: specs are only created for parents
    that are actually being added or removed relative to the current M2M
    state, because redundant ``exists=True`` claims are pure waste.

    Raises HttpError 422 on invalid slugs, self-links, or cycles.
    """
    from apps.catalog.claims import build_relationship_claim

    from ..models import GameplayFeature

    if feature.slug in desired_slugs:
        raise HttpError(422, "A feature cannot be its own parent.")

    existing = set(
        GameplayFeature.objects.filter(slug__in=desired_slugs).values_list(
            "slug", flat=True
        )
    )
    missing = desired_slugs - existing
    if missing:
        raise HttpError(422, f"Unknown parent slugs: {sorted(missing)}")

    # Cycle detection: for each proposed parent, walk up the existing
    # graph (excluding the edited feature's current parents, since
    # they're being replaced). If we reach the edited feature, reject.
    if desired_slugs:
        all_features = GameplayFeature.objects.prefetch_related("parents").all()
        parent_map: dict[str, set[str]] = {}
        for f in all_features:
            if f.slug == feature.slug:
                continue
            parent_map[f.slug] = {p.slug for p in f.parents.all()}

        for start_slug in desired_slugs:
            visited: set[str] = set()
            stack = [start_slug]
            while stack:
                current = stack.pop()
                if current == feature.slug:
                    raise HttpError(
                        422,
                        f"Adding parent '{start_slug}' would create a cycle.",
                    )
                if current in visited:
                    continue
                visited.add(current)
                stack.extend(parent_map.get(current, set()))

    # Diff against current M2M state
    current_slugs = set(feature.parents.values_list("slug", flat=True))
    specs: list[ClaimSpec] = []
    for parent_slug in desired_slugs - current_slugs:
        claim_key, value = build_relationship_claim(
            "gameplay_feature_parent", {"parent_slug": parent_slug}
        )
        specs.append(
            ClaimSpec(
                field_name="gameplay_feature_parent", value=value, claim_key=claim_key
            )
        )
    for parent_slug in current_slugs - desired_slugs:
        claim_key, value = build_relationship_claim(
            "gameplay_feature_parent", {"parent_slug": parent_slug}, exists=False
        )
        specs.append(
            ClaimSpec(
                field_name="gameplay_feature_parent", value=value, claim_key=claim_key
            )
        )
    return specs


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
    feature = get_object_or_404(_detail_qs(), slug=slug)
    return _serialize_detail(feature)


@gameplay_features_router.patch(
    "/{slug}/claims/",
    auth=django_auth,
    response=GameplayFeatureDetailSchema,
    tags=["private"],
)
def patch_gameplay_feature_claims(
    request, slug: str, data: GameplayFeatureClaimPatchSchema
):
    """Assert per-field claims from the authenticated user, then re-resolve."""
    from ..models import GameplayFeature
    from ..resolve._relationships import resolve_gameplay_feature_parents

    if not data.fields and data.parents is None:
        raise HttpError(422, "No changes provided.")

    feature = get_object_or_404(GameplayFeature, slug=slug)

    specs = validate_scalar_fields(GameplayFeature, data.fields)

    resolvers = []
    if data.parents is not None:
        parent_specs = _plan_parent_claims(feature, set(data.parents))
        specs.extend(parent_specs)
        if parent_specs:
            resolvers.append(resolve_gameplay_feature_parents)

    if not specs:
        raise HttpError(422, "No changes provided.")

    execute_claims(
        feature, specs, user=request.user, note=data.note, resolvers=resolvers
    )

    feature = get_object_or_404(_detail_qs(), slug=feature.slug)
    return _serialize_detail(feature)
