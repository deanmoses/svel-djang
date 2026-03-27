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
        field = model_class._meta.get_field(field_name)
        # Claim.value is NOT NULL; store allowed clears as "" and let the
        # resolver coerce that sentinel back to None/blank based on field
        # metadata. Required fields must reject clears up front.
        if value is None:
            if not (field.null or getattr(field, "blank", False)):
                raise HttpError(422, f"Field '{field_name}' cannot be cleared.")
            value = ""
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


def plan_alias_claims(
    entity,
    desired_aliases: list[str],
    *,
    claim_field_name: str,
) -> list[ClaimSpec]:
    """Validate alias changes and return diff-based ClaimSpecs.

    Normalises input (strip, deduplicate by lowercase key) and diffs
    against current alias rows.  Preserves user-typed case via
    ``alias_display`` so the resolver stores the display form.

    Returns specs for adds, removes, and display-case updates.
    """
    from apps.catalog.claims import build_relationship_claim

    # Normalise: strip, deduplicate by lowercase key, drop blanks.
    # Last-write-wins for display case when duplicates differ only in case.
    desired: dict[str, str] = {}  # lowercase → display string
    for raw in desired_aliases:
        val = raw.strip()
        if val:
            desired[val.lower()] = val

    current: dict[str, str] = {}  # lowercase → stored display string
    for a in entity.aliases.all():
        current[a.value.lower()] = a.value

    specs: list[ClaimSpec] = []
    # Adds and display-case updates
    for lower, display in desired.items():
        if lower not in current or current[lower] != display:
            claim_key, value = build_relationship_claim(
                claim_field_name,
                {"alias_value": lower, "alias_display": display},
            )
            specs.append(
                ClaimSpec(field_name=claim_field_name, value=value, claim_key=claim_key)
            )
    # Removes
    for lower in current.keys() - desired.keys():
        claim_key, value = build_relationship_claim(
            claim_field_name, {"alias_value": lower}, exists=False
        )
        specs.append(
            ClaimSpec(field_name=claim_field_name, value=value, claim_key=claim_key)
        )
    return specs


def plan_m2m_claims(
    entity,
    desired_slugs: set[str],
    *,
    target_model,
    claim_field_name: str,
    slug_key: str,
    m2m_attr: str,
) -> list[ClaimSpec]:
    """Validate and diff a simple slug-set M2M relationship.

    Works for any MachineModel M2M that is resolved by slug (themes, tags,
    reward_types).  Unlike ``plan_parent_claims``, no hierarchy or cycle
    checks are needed.

    Raises HttpError 422 on unknown slugs.
    """
    from apps.catalog.claims import build_relationship_claim

    if desired_slugs:
        existing = set(
            target_model.objects.filter(slug__in=desired_slugs).values_list(
                "slug", flat=True
            )
        )
        missing = desired_slugs - existing
        if missing:
            raise HttpError(422, f"Unknown {claim_field_name} slugs: {sorted(missing)}")

    current_slugs = {obj.slug for obj in getattr(entity, m2m_attr).all()}
    specs: list[ClaimSpec] = []
    for slug in desired_slugs - current_slugs:
        claim_key, value = build_relationship_claim(claim_field_name, {slug_key: slug})
        specs.append(
            ClaimSpec(field_name=claim_field_name, value=value, claim_key=claim_key)
        )
    for slug in current_slugs - desired_slugs:
        claim_key, value = build_relationship_claim(
            claim_field_name, {slug_key: slug}, exists=False
        )
        specs.append(
            ClaimSpec(field_name=claim_field_name, value=value, claim_key=claim_key)
        )
    return specs


def plan_gameplay_feature_claims(
    entity,
    desired_features: list,
) -> list[ClaimSpec]:
    """Validate and diff gameplay features (slug + optional count) on a MachineModel.

    Each entry has a ``slug`` and optional ``count``.  Duplicate slugs in the
    input are rejected.  Count must be positive if provided.

    Assumes ``entity`` has a ``machinemodelgameplayfeature_set`` reverse
    relation (i.e., is a MachineModel with that through-table prefetched).

    Raises HttpError 422 on invalid input.
    """
    from apps.catalog.claims import build_relationship_claim
    from apps.catalog.models import GameplayFeature

    # Normalise input into {slug: count} and validate.
    desired: dict[str, int | None] = {}
    for feat in desired_features:
        slug = feat.slug
        count = feat.count
        if slug in desired:
            raise HttpError(422, f"Duplicate gameplay feature slug: {slug!r}")
        if count is not None and count <= 0:
            raise HttpError(422, f"Count must be positive for {slug!r}, got {count}")
        desired[slug] = count

    if desired:
        existing = set(
            GameplayFeature.objects.filter(slug__in=desired.keys()).values_list(
                "slug", flat=True
            )
        )
        missing = set(desired.keys()) - existing
        if missing:
            raise HttpError(422, f"Unknown gameplay_feature slugs: {sorted(missing)}")

    # Current state from prefetched through-table.
    current: dict[str, int | None] = {}
    for row in entity.machinemodelgameplayfeature_set.all():
        current[row.gameplayfeature.slug] = row.count

    specs: list[ClaimSpec] = []
    # Adds and count changes.
    for slug, count in desired.items():
        if slug not in current or current[slug] != count:
            claim_key, value = build_relationship_claim(
                "gameplay_feature", {"gameplay_feature_slug": slug}
            )
            value["count"] = count
            specs.append(
                ClaimSpec(
                    field_name="gameplay_feature",
                    value=value,
                    claim_key=claim_key,
                )
            )
    # Removes.
    for slug in set(current.keys()) - set(desired.keys()):
        claim_key, value = build_relationship_claim(
            "gameplay_feature", {"gameplay_feature_slug": slug}, exists=False
        )
        specs.append(
            ClaimSpec(
                field_name="gameplay_feature",
                value=value,
                claim_key=claim_key,
            )
        )
    return specs


def plan_abbreviation_claims(
    entity,
    desired_values: list[str],
) -> list[ClaimSpec]:
    """Validate and diff abbreviation changes.

    Normalises input (strip, deduplicate, drop blanks, enforce max length)
    and diffs against current abbreviation rows.

    Shared by MachineModel and Title.
    """
    from apps.catalog.claims import build_relationship_claim

    desired = set(_normalize_abbreviations(desired_values))
    current = set(entity.abbreviations.values_list("value", flat=True))
    specs: list[ClaimSpec] = []

    for value in desired - current:
        claim_key, claim_value = build_relationship_claim(
            "abbreviation", {"value": value}
        )
        specs.append(
            ClaimSpec(field_name="abbreviation", value=claim_value, claim_key=claim_key)
        )

    for value in current - desired:
        claim_key, claim_value = build_relationship_claim(
            "abbreviation", {"value": value}, exists=False
        )
        specs.append(
            ClaimSpec(field_name="abbreviation", value=claim_value, claim_key=claim_key)
        )
    return specs


def plan_credit_claims(
    entity,
    desired_credits: list,
) -> list[ClaimSpec]:
    """Validate and diff credits (person_slug + role) on a MachineModel.

    Each entry has a ``person_slug`` and ``role`` (role slug).  Duplicate
    (person_slug, role) pairs in the input are rejected.

    Assumes ``entity`` has ``credits`` prefetched with
    select_related("person", "role").

    Raises HttpError 422 on invalid input.
    """
    from apps.catalog.claims import build_relationship_claim
    from apps.catalog.models import CreditRole, Person

    # Normalise input into a set of (person_slug, role_slug) and validate.
    desired: set[tuple[str, str]] = set()
    for credit in desired_credits:
        pair = (credit.person_slug, credit.role)
        if pair in desired:
            raise HttpError(
                422,
                f"Duplicate credit: person={credit.person_slug!r}, role={credit.role!r}",
            )
        desired.add(pair)

    if desired:
        desired_person_slugs = {p for p, _ in desired}
        existing_people = set(
            Person.objects.filter(slug__in=desired_person_slugs).values_list(
                "slug", flat=True
            )
        )
        missing_people = desired_person_slugs - existing_people
        if missing_people:
            raise HttpError(422, f"Unknown person slugs: {sorted(missing_people)}")

        desired_role_slugs = {r for _, r in desired}
        existing_roles = set(
            CreditRole.objects.filter(slug__in=desired_role_slugs).values_list(
                "slug", flat=True
            )
        )
        missing_roles = desired_role_slugs - existing_roles
        if missing_roles:
            raise HttpError(422, f"Unknown credit role slugs: {sorted(missing_roles)}")

    # Current state from prefetched credits.
    current: set[tuple[str, str]] = set()
    for credit in entity.credits.all():
        current.add((credit.person.slug, credit.role.slug))

    specs: list[ClaimSpec] = []
    for person_slug, role in desired - current:
        claim_key, value = build_relationship_claim(
            "credit", {"person_slug": person_slug, "role": role}
        )
        specs.append(ClaimSpec(field_name="credit", value=value, claim_key=claim_key))
    for person_slug, role in current - desired:
        claim_key, value = build_relationship_claim(
            "credit", {"person_slug": person_slug, "role": role}, exists=False
        )
        specs.append(ClaimSpec(field_name="credit", value=value, claim_key=claim_key))
    return specs


def _normalize_abbreviations(values: list[str]) -> list[str]:
    """Strip, deduplicate, drop blanks, enforce max length."""
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = raw_value.strip()
        if not value:
            continue
        if len(value) > 50:
            raise HttpError(422, "Abbreviations must be 50 characters or fewer.")
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


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
