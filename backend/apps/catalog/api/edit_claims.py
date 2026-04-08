"""Shared helpers for PATCH claims endpoints.

Provides the plan/execute pattern for entity editing: validate input,
build a list of ClaimSpecs, then execute them atomically in a ChangeSet.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import IntegrityError, models as db_models, transaction
from ninja.errors import HttpError

from apps.catalog.claims import build_relationship_claim
from apps.catalog.models import CreditRole, GameplayFeature, Person
from apps.core.models import get_claim_fields
from apps.provenance.models import ChangeSet, CitationInstance, Claim
from apps.provenance.validation import validate_claim_value

from ..resolve import resolve_after_mutation
from .schemas import EditCitationInput


@dataclass(frozen=True)
class ClaimSpec:
    """A planned claim to be written — separates diffing from execution."""

    field_name: str
    value: object
    claim_key: str = ""


def plan_scalar_field_claims(
    model_class, fields: dict, *, entity=None
) -> list[ClaimSpec]:
    """Validate scalar fields and reject empty/no-op field payloads.

    Shared by PATCH endpoints that only accept scalar ``fields`` payloads.
    """
    if not fields:
        raise HttpError(422, "No changes provided.")

    specs = validate_scalar_fields(model_class, fields, entity=entity)
    if not specs:
        raise HttpError(422, "No changes provided.")
    return specs


def get_field_constraints(model_class) -> dict[str, dict]:
    """Extract min/max/step constraints from numeric claim fields.

    Returns a dict like ``{"year": {"min": 1800, "max": 2100, "step": 1}}``.
    Only fields with at least one validator-derived constraint are included.
    Step is derived from ``DecimalField.decimal_places``.
    """
    numeric_types = (
        db_models.IntegerField,
        db_models.SmallIntegerField,
        db_models.PositiveIntegerField,
        db_models.PositiveSmallIntegerField,
        db_models.DecimalField,
        db_models.FloatField,
    )
    editable = get_claim_fields(model_class)
    constraints: dict[str, dict] = {}

    for field_name in editable:
        field = model_class._meta.get_field(field_name)
        if not isinstance(field, numeric_types):
            continue

        entry: dict[str, float | int] = {}
        # Use _validators (explicitly declared) rather than .validators
        # (which includes DB-range validators like max=9223372036854775807).
        for v in field._validators:
            if isinstance(v, MinValueValidator):
                entry["min"] = v.limit_value
            elif isinstance(v, MaxValueValidator):
                entry["max"] = v.limit_value

        if not entry:
            continue
        if isinstance(field, db_models.DecimalField) and field.decimal_places:
            entry["step"] = float(f"1e-{field.decimal_places}")
        else:
            entry["step"] = 1
        constraints[field_name] = entry

    return constraints


def validate_scalar_fields(
    model_class, fields: dict, *, entity=None
) -> list[ClaimSpec]:
    """Validate scalar fields and return ClaimSpecs.

    Scalar fields are assertion-based: a spec is created for every field in
    the request, even if the value matches the current state. Reasserting
    the same value is meaningful (e.g., a user confirming a machine-sourced
    value). The frontend is responsible for only sending changed fields.

    Raises HttpError 422 on unknown fields or invalid markdown.
    """
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
            value = validate_claim_value(field_name, value, model_class)
        except ValidationError as exc:
            raise HttpError(422, "; ".join(exc.messages)) from exc
        if getattr(field, "unique", False) and value != "":
            conflict_qs = model_class.objects.filter(**{field_name: value})
            if entity is not None and getattr(entity, "pk", None) is not None:
                conflict_qs = conflict_qs.exclude(pk=entity.pk)
            if conflict_qs.exists():
                raise HttpError(422, f"Field '{field_name}' must be unique.")
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
    if entity.slug in desired_slugs:
        raise HttpError(422, f"A {model_class.__name__} cannot be its own parent.")

    # Resolve desired slugs → PKs (also validates existence).
    slug_to_pk = dict(
        model_class.objects.filter(slug__in=desired_slugs).values_list("slug", "pk")
    )
    missing = desired_slugs - slug_to_pk.keys()
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

    # Diff against current M2M state (by PK).
    desired_pks = set(slug_to_pk.values())
    current_pks = set(entity.parents.values_list("pk", flat=True))
    specs: list[ClaimSpec] = []
    for parent_pk in desired_pks - current_pks:
        claim_key, value = build_relationship_claim(
            claim_field_name, {"parent": parent_pk}
        )
        specs.append(
            ClaimSpec(field_name=claim_field_name, value=value, claim_key=claim_key)
        )
    for parent_pk in current_pks - desired_pks:
        claim_key, value = build_relationship_claim(
            claim_field_name, {"parent": parent_pk}, exists=False
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
    m2m_attr: str,
) -> list[ClaimSpec]:
    """Validate and diff a simple slug-set M2M relationship.

    Works for any MachineModel M2M that is resolved by PK (themes, tags,
    reward_types).  The API receives slugs; this function resolves them to
    PKs before building claims.  Unlike ``plan_parent_claims``, no hierarchy
    or cycle checks are needed.

    Raises HttpError 422 on unknown slugs.
    """
    if desired_slugs:
        slug_to_pk = dict(
            target_model.objects.filter(slug__in=desired_slugs).values_list(
                "slug", "pk"
            )
        )
        missing = desired_slugs - slug_to_pk.keys()
        if missing:
            raise HttpError(422, f"Unknown {claim_field_name} slugs: {sorted(missing)}")
        desired_pks = set(slug_to_pk.values())
    else:
        desired_pks = set()

    current_pks = set(getattr(entity, m2m_attr).values_list("pk", flat=True))
    return build_m2m_claim_specs(
        current=current_pks,
        desired=desired_pks,
        claim_field_name=claim_field_name,
    )


def build_m2m_claim_specs(
    *,
    current: set[int],
    desired: set[int],
    claim_field_name: str,
) -> list[ClaimSpec]:
    """Build diff-based ClaimSpecs for simple PK-set M2M relationships."""
    specs: list[ClaimSpec] = []
    for pk in desired - current:
        claim_key, value = build_relationship_claim(
            claim_field_name, {claim_field_name: pk}
        )
        specs.append(
            ClaimSpec(field_name=claim_field_name, value=value, claim_key=claim_key)
        )
    for pk in current - desired:
        claim_key, value = build_relationship_claim(
            claim_field_name, {claim_field_name: pk}, exists=False
        )
        specs.append(
            ClaimSpec(field_name=claim_field_name, value=value, claim_key=claim_key)
        )
    return specs


def normalize_gameplay_feature_inputs(
    desired_features: list[tuple[str, int | None]],
    *,
    available_slugs: set[str] | None = None,
) -> dict[str, int | None]:
    """Normalize gameplay feature input into a slug->count map.

    Duplicate slugs are rejected. Counts, when provided, must be positive.
    When ``available_slugs`` is provided, unknown slugs are rejected without
    touching the database.
    """
    desired: dict[str, int | None] = {}
    for slug, count in desired_features:
        if slug in desired:
            raise HttpError(422, f"Duplicate gameplay feature slug: {slug!r}")
        if count is not None and count <= 0:
            raise HttpError(422, f"Count must be positive for {slug!r}, got {count}")
        desired[slug] = count

    if available_slugs is not None:
        missing = set(desired.keys()) - available_slugs
        if missing:
            raise HttpError(422, f"Unknown gameplay_feature slugs: {sorted(missing)}")

    return desired


def build_gameplay_feature_claim_specs(
    current: dict[int, int | None],
    desired: dict[int, int | None],
) -> list[ClaimSpec]:
    """Build diff-based ClaimSpecs for gameplay feature relationship changes."""
    specs: list[ClaimSpec] = []
    for pk, count in desired.items():
        if pk not in current or current[pk] != count:
            claim_key, value = build_relationship_claim(
                "gameplay_feature", {"gameplay_feature": pk}
            )
            value["count"] = count
            specs.append(
                ClaimSpec(
                    field_name="gameplay_feature",
                    value=value,
                    claim_key=claim_key,
                )
            )
    for pk in current.keys() - desired.keys():
        claim_key, value = build_relationship_claim(
            "gameplay_feature", {"gameplay_feature": pk}, exists=False
        )
        specs.append(
            ClaimSpec(
                field_name="gameplay_feature",
                value=value,
                claim_key=claim_key,
            )
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
    raw_desired = [(feat.slug, feat.count) for feat in desired_features]
    if raw_desired:
        existing = set(
            GameplayFeature.objects.filter(
                slug__in={slug for slug, _ in raw_desired}
            ).values_list("slug", flat=True)
        )
        desired = normalize_gameplay_feature_inputs(
            raw_desired, available_slugs=existing
        )
    else:
        desired = normalize_gameplay_feature_inputs(raw_desired)

    # Resolve slugs → PKs.
    slug_to_pk = dict(
        GameplayFeature.objects.filter(slug__in=desired.keys()).values_list(
            "slug", "pk"
        )
    )
    desired_by_pk: dict[int, int | None] = {
        slug_to_pk[slug]: count for slug, count in desired.items()
    }

    # Current state from prefetched through-table (by PK).
    current_by_pk: dict[int, int | None] = {}
    for row in entity.machinemodelgameplayfeature_set.all():
        current_by_pk[row.gameplayfeature_id] = row.count

    return build_gameplay_feature_claim_specs(current_by_pk, desired_by_pk)


def plan_abbreviation_claims(
    entity,
    desired_values: list[str],
) -> list[ClaimSpec]:
    """Validate and diff abbreviation changes.

    Normalises input (strip, deduplicate, drop blanks, enforce max length)
    and diffs against current abbreviation rows.

    Shared by MachineModel and Title.
    """
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
    raw_desired = [(credit.person_slug, credit.role) for credit in desired_credits]

    if raw_desired:
        desired_person_slugs = {p for p, _ in raw_desired}
        existing_people = set(
            Person.objects.filter(slug__in=desired_person_slugs).values_list(
                "slug", flat=True
            )
        )
        desired_role_slugs = {r for _, r in raw_desired}
        existing_roles = set(
            CreditRole.objects.filter(slug__in=desired_role_slugs).values_list(
                "slug", flat=True
            )
        )
        desired = normalize_credit_inputs(
            raw_desired,
            available_people=existing_people,
            available_roles=existing_roles,
        )
    else:
        desired = normalize_credit_inputs(raw_desired)

    # Resolve slugs → PKs for claim building.
    if desired:
        person_slug_to_pk = dict(
            Person.objects.filter(slug__in={p for p, _ in desired}).values_list(
                "slug", "pk"
            )
        )
        role_slug_to_pk = dict(
            CreditRole.objects.filter(slug__in={r for _, r in desired}).values_list(
                "slug", "pk"
            )
        )
        desired_pks: set[tuple[int, int]] = {
            (person_slug_to_pk[p], role_slug_to_pk[r]) for p, r in desired
        }
    else:
        desired_pks = set()

    # Current state from prefetched credits (by PK).
    current_pks: set[tuple[int, int]] = set()
    for credit in entity.credits.all():
        current_pks.add((credit.person_id, credit.role_id))

    return build_credit_claim_specs(current_pks, desired_pks)


def normalize_credit_inputs(
    desired_credits: list[tuple[str, str]],
    *,
    available_people: set[str] | None = None,
    available_roles: set[str] | None = None,
) -> set[tuple[str, str]]:
    """Normalize credits into unique (person_slug, role_slug) pairs.

    When available slug sets are provided, unknown people or roles are rejected
    without touching the database.
    """
    desired: set[tuple[str, str]] = set()
    for person_slug, role in desired_credits:
        pair = (person_slug, role)
        if pair in desired:
            raise HttpError(
                422,
                f"Duplicate credit: person={person_slug!r}, role={role!r}",
            )
        desired.add(pair)

    if available_people is not None:
        missing_people = {p for p, _ in desired} - available_people
        if missing_people:
            raise HttpError(422, f"Unknown person slugs: {sorted(missing_people)}")

    if available_roles is not None:
        missing_roles = {r for _, r in desired} - available_roles
        if missing_roles:
            raise HttpError(422, f"Unknown credit role slugs: {sorted(missing_roles)}")

    return desired


def build_credit_claim_specs(
    current: set[tuple[int, int]],
    desired: set[tuple[int, int]],
) -> list[ClaimSpec]:
    """Build diff-based ClaimSpecs for credit relationship changes."""
    specs: list[ClaimSpec] = []
    for person_pk, role_pk in desired - current:
        claim_key, value = build_relationship_claim(
            "credit", {"person": person_pk, "role": role_pk}
        )
        specs.append(ClaimSpec(field_name="credit", value=value, claim_key=claim_key))
    for person_pk, role_pk in current - desired:
        claim_key, value = build_relationship_claim(
            "credit", {"person": person_pk, "role": role_pk}, exists=False
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
    citation: EditCitationInput | None = None,
) -> None:
    """Create a ChangeSet + claims atomically, resolve, and invalidate cache.

    Resolution is handled by :func:`resolve_after_mutation` which routes
    to the correct resolver(s) based on entity type and the claim field
    names in *specs*.

    Raises HttpError 422 on IntegrityError (unique constraint violations).
    """
    try:
        with transaction.atomic():
            cs = ChangeSet.objects.create(user=user, note=note)
            created_claims = []
            for spec in specs:
                created_claims.append(
                    Claim.objects.assert_claim(
                        entity,
                        spec.field_name,
                        spec.value,
                        user=user,
                        claim_key=spec.claim_key,
                        changeset=cs,
                    )
                )
            if citation is not None:
                try:
                    template = CitationInstance.objects.select_related(
                        "citation_source"
                    ).get(pk=citation.citation_instance_id)
                except CitationInstance.DoesNotExist as exc:
                    raise HttpError(422, "Unknown citation instance.") from exc

                for claim in created_claims:
                    instance = CitationInstance(
                        citation_source=template.citation_source,
                        claim=claim,
                        locator=template.locator,
                    )
                    instance.full_clean()
                    instance.save()

            field_names = list({s.field_name for s in specs})
            resolve_after_mutation(entity, field_names=field_names)
    except ValidationError as exc:
        raise HttpError(422, "; ".join(exc.messages)) from exc
    except IntegrityError as exc:
        raise HttpError(422, f"Unique constraint violation: {exc}") from exc
