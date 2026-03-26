"""Shared helpers for PATCH claims endpoints.

Provides the plan/execute pattern for entity editing: validate input,
build a list of ClaimSpecs, then execute them atomically in a ChangeSet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from ninja.errors import HttpError

from ..cache import invalidate_all


@dataclass(frozen=True)
class ClaimSpec:
    """A planned claim to be written — separates diffing from execution."""

    field_name: str
    value: object
    claim_key: str = ""


def validate_scalar_fields(model_class, fields: dict) -> list[ClaimSpec]:
    """Validate scalar fields and return ClaimSpecs.

    Scalar fields are assertion-based: a spec is created for every field in
    the request, even if the value matches the current state. Reasserting
    the same value is meaningful (e.g., a user confirming a machine-sourced
    value). The frontend is responsible for only sending changed fields.

    Raises HttpError 422 on unknown fields or invalid markdown.
    """
    from apps.core.markdown_links import prepare_markdown_claim_value
    from apps.core.models import get_claim_fields

    editable = set(get_claim_fields(model_class))
    unknown = set(fields.keys()) - editable
    if unknown:
        raise HttpError(422, f"Unknown or non-editable fields: {sorted(unknown)}")

    specs: list[ClaimSpec] = []
    for field_name, value in fields.items():
        try:
            value = prepare_markdown_claim_value(field_name, value, model_class)
        except ValidationError as exc:
            raise HttpError(422, "; ".join(exc.messages)) from exc
        specs.append(ClaimSpec(field_name=field_name, value=value))
    return specs


def plan_parent_claims(
    entity,
    desired_slugs: set[str],
    *,
    model_class,
    claim_field_name: str,
) -> list[ClaimSpec]:
    """Validate parent hierarchy changes and return diff-based ClaimSpecs.

    Works for any model with a self-referencing ``parents`` M2M resolved
    via relationship claims (GameplayFeature, Theme).

    Raises HttpError 422 on invalid slugs, self-links, or cycles.
    """
    from apps.catalog.claims import build_relationship_claim

    if entity.slug in desired_slugs:
        raise HttpError(422, f"A {model_class.__name__} cannot be its own parent.")

    existing = set(
        model_class.objects.filter(slug__in=desired_slugs).values_list(
            "slug", flat=True
        )
    )
    missing = desired_slugs - existing
    if missing:
        raise HttpError(422, f"Unknown parent slugs: {sorted(missing)}")

    # Cycle detection: for each proposed parent, walk up the existing
    # graph (excluding the edited entity's current parents, since
    # they're being replaced). If we reach the edited entity, reject.
    if desired_slugs:
        all_entities = model_class.objects.prefetch_related("parents").all()
        parent_map: dict[str, set[str]] = {}
        for e in all_entities:
            if e.slug == entity.slug:
                continue
            parent_map[e.slug] = {p.slug for p in e.parents.all()}

        for start_slug in desired_slugs:
            visited: set[str] = set()
            stack = [start_slug]
            while stack:
                current = stack.pop()
                if current == entity.slug:
                    raise HttpError(
                        422,
                        f"Adding parent '{start_slug}' would create a cycle.",
                    )
                if current in visited:
                    continue
                visited.add(current)
                stack.extend(parent_map.get(current, set()))

    # Diff against current M2M state
    current_slugs = set(entity.parents.values_list("slug", flat=True))
    specs: list[ClaimSpec] = []
    for parent_slug in desired_slugs - current_slugs:
        claim_key, value = build_relationship_claim(
            claim_field_name, {"parent_slug": parent_slug}
        )
        specs.append(
            ClaimSpec(field_name=claim_field_name, value=value, claim_key=claim_key)
        )
    for parent_slug in current_slugs - desired_slugs:
        claim_key, value = build_relationship_claim(
            claim_field_name, {"parent_slug": parent_slug}, exists=False
        )
        specs.append(
            ClaimSpec(field_name=claim_field_name, value=value, claim_key=claim_key)
        )
    return specs


def execute_claims(
    entity,
    specs: list[ClaimSpec],
    *,
    user,
    note: str = "",
    resolvers: list[Callable] | None = None,
    resolve_fn: Callable | None = None,
) -> None:
    """Create a ChangeSet + claims atomically, resolve, and invalidate cache.

    ``resolvers`` is an optional list of callables to run inside the
    transaction before the entity resolver — e.g., relationship resolvers
    like ``resolve_gameplay_feature_parents``.

    ``resolve_fn`` overrides the default ``resolve_entity`` — used by
    MachineModel which needs ``resolve_model`` instead.

    Raises HttpError 422 on IntegrityError (unique constraint violations).
    """
    from apps.provenance.models import ChangeSet, Claim

    if resolve_fn is None:
        from ..resolve import resolve_entity

        resolve_fn = resolve_entity

    try:
        with transaction.atomic():
            cs = ChangeSet.objects.create(user=user, note=note)
            for spec in specs:
                Claim.objects.assert_claim(
                    entity,
                    spec.field_name,
                    spec.value,
                    user=user,
                    claim_key=spec.claim_key,
                    changeset=cs,
                )
            for resolver in resolvers or []:
                resolver()
            resolve_fn(entity)
    except IntegrityError as exc:
        raise HttpError(422, f"Unique constraint violation: {exc}") from exc

    invalidate_all()
