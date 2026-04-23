"""Shared helpers for claim resolution: coercion, FK lookup, priority annotation."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, cast

from django.db import models

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def validate_check_constraints(obj):
    """Validate cross-field CheckConstraints before save/bulk_update.

    Only validates constraints tagged with ``violation_error_code`` — these
    are cross-field invariants (year ordering, month-requires-year, self-ref
    anti-cycle) that the resolver can violate by combining independent claim
    winners.  Single-field constraints (non-blank, range) are DB safety nets
    for external writes and are not checked here — the resolver legitimately
    resets unclaimed fields to defaults like ``""``.

    Skips UniqueConstraints entirely — their ``validate()`` fires a DB query
    per constraint, which is O(n * constraints) in a bulk loop.
    """
    for constraint in obj._meta.constraints:
        if not isinstance(constraint, models.CheckConstraint):
            continue

        violation_error_code = getattr(constraint, "violation_error_code", None)
        validate = getattr(constraint, "validate", None)
        if violation_error_code is not None and callable(validate):
            validate(type(obj), obj)


@dataclass
class FKInfo:
    """FK field metadata and pre-fetched lookups for bulk resolution."""

    fk_fields: set[str] = field(default_factory=set)
    # {attr: {lookup_value: related_instance}} — inner dict maps the claim's
    # string payload (typically slug) to the fully-fetched target model row.
    lookups: dict[str, dict[str, models.Model]] = field(default_factory=dict)


# ------------------------------------------------------------------
# Generic FK resolution (model-introspected)
# ------------------------------------------------------------------


def _resolve_fk_generic(
    model_class: type[models.Model],
    field_name: str,
    value,
    lookup: dict[str, models.Model] | None = None,
) -> models.Model | None:
    """Resolve a claim value to an FK instance by introspecting the Django field.

    Uses ``slug`` as the default lookup key on the target model.  Models can
    override this per-FK via a ``claim_fk_lookups`` class attribute::

        class Location(models.Model):
            claim_fk_lookups = {"parent": "location_path"}

    If *lookup* is provided (pre-fetched slug→instance dict), it is used
    instead of hitting the database.
    """
    if not value:
        return None
    key = str(value).strip()
    if not key:
        return None

    field = model_class._meta.get_field(field_name)
    target_model = field.related_model
    if target_model is None:
        logger.warning(
            "FK field %s on %s has no related model", field_name, model_class
        )
        return None
    fk_lookups_map = getattr(model_class, "claim_fk_lookups", {})
    lookup_key = fk_lookups_map.get(field_name, "slug")

    if lookup is not None:
        result = lookup.get(key)
    else:
        assert isinstance(target_model, type)
        assert issubclass(target_model, models.Model)
        result = target_model._default_manager.filter(**{lookup_key: key}).first()
    if not result:
        logger.warning("Unmatched %s claim value: %r", field_name, value)
    return result


def build_fk_info(
    model_class: type[models.Model],
    claim_fields: dict[str, str],
) -> FKInfo:
    """Identify FK fields and pre-build slug-to-instance lookups for bulk resolution."""
    info = FKInfo()
    fk_lookups_map = getattr(model_class, "claim_fk_lookups", {})
    for attr in claim_fields.values():
        f = model_class._meta.get_field(attr)
        if f.is_relation:
            info.fk_fields.add(attr)
            lookup_key = fk_lookups_map.get(attr, "slug")
            target_model = f.related_model
            if target_model is None:
                continue
            assert isinstance(target_model, type)
            assert issubclass(target_model, models.Model)
            info.lookups[attr] = {
                getattr(obj, lookup_key): obj
                for obj in target_model._default_manager.all()
            }
    return info


# ------------------------------------------------------------------
# Type coercion (auto-detected from Django model field)
# ------------------------------------------------------------------


def _coerce(model_class: type[models.Model], attr: str, value):
    """Coerce a JSON claim value to the type expected by the model field."""
    if value is None or value == "":
        field = model_class._meta.get_field(attr)
        return None if field.null else ""

    field = model_class._meta.get_field(attr)

    if isinstance(
        field,
        models.IntegerField
        | models.SmallIntegerField
        | models.PositiveIntegerField
        | models.PositiveSmallIntegerField
        | models.BigIntegerField,
    ):
        try:
            return int(value)
        except ValueError, TypeError:
            logger.warning("Cannot coerce %r to int for field %s", value, attr)
            return None if field.null else 0

    if isinstance(field, models.DecimalField):
        try:
            return Decimal(str(value))
        except InvalidOperation, ValueError, TypeError:
            logger.warning("Cannot coerce %r to Decimal for field %s", value, attr)
            return None if field.null else Decimal(0)

    if isinstance(field, models.BooleanField):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return bool(value)

    return value


# ------------------------------------------------------------------
# Claim query helpers
# ------------------------------------------------------------------


def _annotate_priority(qs):
    """Filter to active claims from enabled sources, annotate effective_priority.

    Returns a queryset with ``effective_priority`` annotation (highest wins)
    and ``select_related("source", "user__profile")``.  Callers supply their
    own ``.order_by()`` and may chain additional ``.select_related()`` or
    ``.filter()`` calls.
    """
    from django.db.models import Case, F, IntegerField, Value, When

    return (
        qs.filter(is_active=True)
        .exclude(source__is_enabled=False)
        .select_related("source", "user__profile")
        .annotate(
            effective_priority=Case(
                When(source__isnull=False, then=F("source__priority")),
                When(user__isnull=False, then=F("user__profile__priority")),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
    )


# ------------------------------------------------------------------
# Field defaults
# ------------------------------------------------------------------


def get_field_defaults(
    model_class: type[models.Model],
    direct_fields: dict[str, str],
) -> dict[str, Any]:
    """Compute reset values for direct fields by inspecting Django model metadata.

    The returned values are ``dict[str, Any]`` because Django field defaults
    are genuinely heterogeneous — any Python scalar, ``None``, or the return
    of an arbitrary callable.  Narrowing further would require per-field
    type variance that callers don't need.
    """
    # Values are Django field defaults — scalars, None, or callable output.
    defaults: dict[str, Any] = {}
    for attr in direct_fields.values():
        field = model_class._meta.get_field(attr)
        if hasattr(field, "default") and field.default is not models.NOT_PROVIDED:
            defaults[attr] = (
                field.default() if callable(field.default) else field.default
            )
        elif field.null or field.is_relation:
            # null fields default to None.  FK fields also default to None
            # as a safe transient value — Django's FK descriptor rejects ""
            # on assignment.  For non-nullable FKs, preserve_when_unclaimed
            # prevents this None from reaching the DB.
            defaults[attr] = None
        else:
            defaults[attr] = ""
    return defaults


def get_preserve_fields(
    model_class: type[models.Model],
    direct_fields: dict[str, str],
) -> set[str]:
    """Identify fields that must keep their existing value when no claim exists.

    These fields cannot safely be reset to a shared default during resolution:

    * **UNIQUE** — resetting multiple objects to ``""`` causes IntegrityError.
    * **Non-nullable FK** — Django's FK descriptor rejects ``""`` on assignment,
      and ``None`` violates the NOT NULL constraint.

    Returns a set of attribute names (values from *direct_fields*).
    """
    preserve: set[str] = set()
    for attr in direct_fields.values():
        field = model_class._meta.get_field(attr)
        is_unique = bool(getattr(field, "unique", False))
        if is_unique or (field.many_to_one and not field.null):
            preserve.add(attr)
    return preserve


def resolve_unique_conflicts(
    all_objs: Sequence[models.Model],
    field_name: str,
    model_class: type[models.Model],
    pre_values: dict[int, Any] | None = None,
) -> None:
    """Detect and fix duplicate values for a UNIQUE field after resolution.

    Handles both nullable and non-nullable fields:

    * **Nullable** (e.g. ``opdb_id``): loser is cleared to ``None``.
    * **Non-nullable** (e.g. ``slug``): loser reverts to its pre-resolution
      value. Requires *pre_values* (``{pk: value}`` captured before resolution).
      When a preserver (unchanged value) conflicts with a changer (new value),
      the preserver wins — it's the rightful owner. Pre-resolution values are
      guaranteed unique by the DB constraint, so reverting never creates a
      secondary conflict.

    Mutates objects in place. The losing claim stays in the DB for manual
    inspection.
    """
    nullable = model_class._meta.get_field(field_name).null
    seen: dict[Any, models.Model] = {}
    for obj in all_objs:
        value = getattr(obj, field_name)
        if not value:
            continue
        if value not in seen:
            seen[value] = obj
            continue

        owner = seen[value]
        if nullable:
            # Nullable: first encountered wins, loser clears to None.
            obj_name = getattr(obj, "name", f"<{type(obj).__name__}>")
            owner_name = getattr(owner, "name", f"<{type(owner).__name__}>")
            logger.warning(
                "Cannot resolve %s=%r onto '%s' (pk=%s): already owned by '%s' (pk=%s)",
                field_name,
                value,
                obj_name,
                obj.pk,
                owner_name,
                owner.pk,
            )
            setattr(obj, field_name, None)
        else:
            # Non-nullable: preserver wins over changer.
            if pre_values is None:
                raise ValueError(
                    "pre_values is required for non-nullable unique fields"
                )

            owner_changed = (
                getattr(owner, field_name) != pre_values[cast(int, owner.pk)]
            )
            obj_changed = value != pre_values[cast(int, obj.pk)]
            if owner_changed and not obj_changed:
                loser, winner = owner, obj
            else:
                loser, winner = obj, owner
            winner_name = getattr(winner, "name", f"<{type(winner).__name__}>")
            loser_name = getattr(loser, "name", f"<{type(loser).__name__}>")
            logger.warning(
                "%s conflict %r: keeping on '%s' (pk=%s), "
                "reverting '%s' (pk=%s) to previous value %r",
                field_name,
                getattr(winner, field_name),
                winner_name,
                winner.pk,
                loser_name,
                loser.pk,
                pre_values[cast(int, loser.pk)],
            )
            setattr(loser, field_name, pre_values[cast(int, loser.pk)])
            seen[getattr(winner, field_name)] = winner
