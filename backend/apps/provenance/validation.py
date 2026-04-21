"""Claim-boundary validation: shared rules for all claim write paths.

Provides ``classify_claim`` for structural claim classification,
``validate_claim_value`` for per-field scalar validation (used by both the
interactive PATCH path and bulk ingest), ``validate_claims_batch`` for
batch-mode validation inside ``bulk_assert_claims``, and
``validate_fk_claims_batch`` for batched FK target existence checks,
and ``validate_relationship_claims_batch`` for batched relationship
target checks.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import models

logger = logging.getLogger(__name__)

# Claim classification constants.
DIRECT = "direct"
RELATIONSHIP = "relationship"
EXTRA = "extra"
UNRECOGNIZED = "unrecognized"

# ---------------------------------------------------------------------------
# Relationship target registry
# ---------------------------------------------------------------------------
# Populated by catalog.apps.CatalogConfig.ready() — the provenance layer owns
# the data structure, the catalog layer provides the concrete mappings.
#
# Format: {namespace: [(value_key, target_model, lookup_field), ...]}
#   e.g. {"credit": [("person", Person, "pk"), ("role", CreditRole, "pk")]}
_relationship_target_registry: dict[str, list[tuple[str, type[models.Model], str]]] = {}


def register_relationship_targets(
    mapping: dict[str, list[tuple[str, type[models.Model], str]]],
) -> None:
    """Register target models for relationship claim validation.

    Called once from ``CatalogConfig.ready()``.  Each entry maps a
    relationship namespace to the value-dict keys that reference external
    models and the field used for the existence check.
    """
    _relationship_target_registry.update(mapping)


def classify_claim(
    model_class: type[models.Model],
    field_name: str,
    claim_key: str,
    value: Any,
    *,
    claim_fields: dict[str, str] | None = None,
) -> str:
    """Classify a claim from its structural properties.

    Returns one of ``DIRECT``, ``RELATIONSHIP``, ``EXTRA``, or
    ``UNRECOGNIZED``. Uses only generic provenance conventions — no
    catalog-specific imports.

    - **DIRECT**: ``field_name`` is a concrete claim-controlled Django field.
    - **RELATIONSHIP**: compound ``claim_key``, dict value with ``exists`` key.
    - **EXTRA**: unrecognized field on a model with an ``extra_data`` JSONField.
    - **UNRECOGNIZED**: none of the above — likely a typo or stale field name.

    Pass ``claim_fields`` to avoid repeated ``get_claim_fields()`` calls in
    batch contexts. When omitted, it is computed on each call (fine for
    single-claim use in ``assert_claim``).
    """
    if claim_fields is None:
        from apps.core.models import get_claim_fields

        claim_fields = get_claim_fields(model_class)

    if field_name in claim_fields:
        return DIRECT

    if (
        claim_key
        and claim_key != field_name
        and isinstance(value, dict)
        and "exists" in value
    ):
        return RELATIONSHIP

    if _has_extra_data(model_class):
        return EXTRA

    return UNRECOGNIZED


def _has_extra_data(model_class: type[models.Model]) -> bool:
    """Check whether a model has a concrete ``extra_data`` field.

    Uses ``_meta`` field introspection rather than ``hasattr`` to avoid
    matching non-field attributes (properties, methods, etc.).
    """
    try:
        model_class._meta.get_field("extra_data")
        return True
    except FieldDoesNotExist:
        return False


def validate_claim_value(
    field_name: str,
    value: Any,
    model_class: type[models.Model],
) -> Any:
    """Validate and possibly transform a scalar claim value.

    Returns the (possibly transformed) value on success.
    Raises ``django.core.exceptions.ValidationError`` on failure.

    Validates:
    - Mojibake (encoding corruption)
    - Markdown cross-reference links
    - Type coercion via ``field.to_python()``
    - Django field validator chain (range, URL format, etc.)

    Does NOT validate:
    - Unknown/uneditable field names (request-level concern)
    - Null/blank clearability (request-level concern)
    - FK target existence (see ``validate_fk_claims_batch``)
    """
    from apps.core.markdown_links import prepare_markdown_claim_value
    from apps.core.validators import validate_no_mojibake

    field = model_class._meta.get_field(field_name)

    # FK fields are validated in batch by validate_fk_claims_batch.
    if field.is_relation:
        return value

    # Mojibake check — subsumes the old step-0 check in bulk_assert_claims.
    if isinstance(value, str) and validate_no_mojibake in field.validators:
        validate_no_mojibake(value)

    # Reject whitespace-only strings for required text fields.
    # CharField.to_python() does not strip, so "   " passes through
    # unchallenged.  For blank=False fields, whitespace-only is
    # semantically blank and should be rejected at the claim boundary.
    if isinstance(value, str) and not field.blank and not value.strip():
        raise ValidationError(
            f"Field '{field_name}' cannot be blank (whitespace-only)."
        )

    # Markdown cross-ref conversion (authoring → storage format).
    # Returns value unchanged for non-markdown fields.
    value = prepare_markdown_claim_value(field_name, value, model_class)

    # Type coercion + Django field validators.
    # Always run to_python() for type checking (e.g. BooleanField rejects
    # "maybe"), even on fields with no explicit validators.
    if value != "":
        # JSON has no Decimal type — numeric values arrive as float.
        # to_python(float) produces Decimal with IEEE 754 artifacts
        # (e.g. 8.95 → Decimal('8.950')), which DecimalValidator rejects.
        # Stringify first so to_python("8.95") → Decimal("8.95") cleanly.
        coerce_value = str(value) if isinstance(value, float) else value
        try:
            typed = field.to_python(coerce_value)
        except (ValueError, ValidationError) as exc:
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError(f"Invalid value for '{field_name}': {exc}") from exc
        for validator in field.validators:
            validator(typed)

        # Django's choices validation lives in Field.validate(), not in
        # Field.run_validators().  Check it explicitly so invalid choices
        # (e.g. status='bogus') are caught at the claim boundary.
        if field.choices:
            valid_choices = {k for k, _v in field.flatchoices}
            if typed not in valid_choices:
                raise ValidationError(
                    f"Value {value!r} is not a valid choice for "
                    f"'{field_name}'. Valid: {sorted(valid_choices)}"
                )

    return value


def validate_claims_batch(
    pending_claims: list,
) -> tuple[list, int]:
    """Validate claims in batch mode. Returns ``(valid_claims, rejected_count)``.

    Invalid claims are logged and removed from the list.
    Valid scalar claims may have transformed values (e.g. markdown link
    conversion written back to ``claim.value``).

    Uses ``classify_claim`` to classify each claim structurally, then:

    - **DIRECT** scalar → validate via ``validate_claim_value()``
    - **DIRECT** FK → collect for ``validate_fk_claims_batch()``
    - **RELATIONSHIP** → collect for ``validate_relationship_claims_batch()``
    - **EXTRA** → pass through (free-form staging data)
    - **UNRECOGNIZED** → reject with warning
    """
    from django.contrib.contenttypes.models import ContentType

    from apps.core.models import get_claim_fields

    rejected: list = []
    fk_claims: list[tuple] = []  # (claim, model_class) pairs
    rel_claims: list = []  # relationship claims

    # Cache model_class and claim_fields per content_type_id.
    model_cache: dict[int, type[models.Model]] = {}
    fields_cache: dict[int, dict[str, str]] = {}

    for claim in pending_claims:
        ct_id = claim.content_type_id

        if ct_id not in model_cache:
            model_cache[ct_id] = ContentType.objects.get_for_id(ct_id).model_class()
            fields_cache[ct_id] = get_claim_fields(model_cache[ct_id])

        model_class = model_cache[ct_id]
        fn = claim.field_name

        ct = classify_claim(
            model_class,
            fn,
            claim.claim_key,
            claim.value,
            claim_fields=fields_cache[ct_id],
        )

        if ct == RELATIONSHIP:
            rel_claims.append(claim)
            continue
        if ct == EXTRA:
            continue
        if ct == UNRECOGNIZED:
            logger.warning(
                "Rejected claim with unrecognized field_name %r on %s (object_id=%s)",
                fn,
                model_class.__name__,
                claim.object_id,
            )
            rejected.append(claim)
            continue

        # DIRECT — determine scalar vs FK.
        field = model_class._meta.get_field(fn)
        if field.is_relation:
            fk_claims.append((claim, model_class))
            continue

        # Scalar — validate value.
        try:
            claim.value = validate_claim_value(fn, claim.value, model_class)
        except ValidationError as exc:
            logger.warning(
                "Rejected invalid claim %s.%s (object_id=%s): %s",
                model_class.__name__,
                fn,
                claim.object_id,
                "; ".join(exc.messages),
            )
            rejected.append(claim)

    # Batch FK validation.
    if fk_claims:
        rejected.extend(validate_fk_claims_batch(fk_claims))

    # Batch relationship target validation.
    if rel_claims:
        rejected.extend(validate_relationship_claims_batch(rel_claims))

    rejected_set = {id(c) for c in rejected}
    valid = [c for c in pending_claims if id(c) not in rejected_set]
    return valid, len(rejected)


def validate_fk_claims_batch(
    fk_claims: list[tuple],
) -> list:
    """Batch-validate FK scalar claims. Returns list of rejected claims.

    Groups claims by ``(model_class, field_name)``, then issues one query
    per group to check target existence. Mirrors the ``claim_fk_lookups``
    convention from the resolver.
    """
    groups: dict[tuple, list[tuple]] = defaultdict(list)
    for claim, model_class in fk_claims:
        groups[(model_class, claim.field_name)].append((claim, model_class))

    rejected: list = []
    for (model_class, field_name), group in groups.items():
        field = model_class._meta.get_field(field_name)
        target_model = field.related_model
        fk_lookups_map = getattr(model_class, "claim_fk_lookups", {})
        lookup_key = fk_lookups_map.get(field_name, "slug")

        # Collect all non-empty slug values, keyed by claim identity.
        slug_by_claim: dict[int, str] = {}
        for claim, _mc in group:
            v = claim.value
            if v is not None and v != "":
                slug_by_claim[id(claim)] = str(v).strip()

        slugs = set(slug_by_claim.values())
        if not slugs:
            continue

        existing = set(
            target_model.objects.filter(**{f"{lookup_key}__in": slugs}).values_list(
                lookup_key, flat=True
            )
        )

        for claim, _mc in group:
            slug = slug_by_claim.get(id(claim))
            if slug is None:
                continue
            if slug not in existing:
                logger.warning(
                    "Rejected FK claim %s.%s (object_id=%s): "
                    "target %s with %s=%r does not exist",
                    model_class.__name__,
                    field_name,
                    claim.object_id,
                    target_model.__name__,
                    lookup_key,
                    slug,
                )
                rejected.append(claim)

    return rejected


def validate_relationship_claims_batch(
    rel_claims: list,
) -> list:
    """Batch-validate relationship claim targets. Returns list of rejected claims.

    Groups claims by ``(namespace, value_key)``, then issues one existence
    query per group — the same grouped-query pattern used by
    ``validate_fk_claims_batch`` for FK claims.

    Only namespaces registered via ``register_relationship_targets`` are
    checked. Unregistered namespaces (aliases, abbreviations) pass through
    because their value dicts contain literal data, not foreign references.
    """
    if not _relationship_target_registry:
        return []

    # (namespace, value_key) → [(claim, ref_value), ...]
    groups: dict[tuple[str, str], list[tuple]] = defaultdict(list)
    # Track which (namespace, value_key) → (target_model, lookup_field)
    group_meta: dict[tuple[str, str], tuple[type[models.Model], str]] = {}

    for claim in rel_claims:
        namespace = claim.field_name
        targets = _relationship_target_registry.get(namespace)
        if not targets:
            continue
        value = claim.value
        if not isinstance(value, dict):
            continue
        # Retractions (exists=False) don't need target validation — the
        # target may have been deleted, and the claim is being removed.
        if not value.get("exists", True):
            continue
        for value_key, target_model, lookup_field in targets:
            ref = value.get(value_key)
            if ref is not None:
                key = (namespace, value_key)
                groups[key].append((claim, ref))
                if key not in group_meta:
                    group_meta[key] = (target_model, lookup_field)

    rejected: list = []
    rejected_ids: set[int] = set()

    for key, group in groups.items():
        target_model, lookup_field = group_meta[key]
        namespace, value_key = key

        refs = {ref for _, ref in group}
        existing = set(
            target_model.objects.filter(**{f"{lookup_field}__in": refs}).values_list(
                lookup_field, flat=True
            )
        )

        for claim, ref in group:
            if ref not in existing and id(claim) not in rejected_ids:
                logger.warning(
                    "Rejected relationship claim %s (object_id=%s): "
                    "target %s with %s=%r does not exist",
                    claim.claim_key or namespace,
                    claim.object_id,
                    target_model.__name__,
                    lookup_field,
                    ref,
                )
                rejected.append(claim)
                rejected_ids.add(id(claim))

    return rejected
