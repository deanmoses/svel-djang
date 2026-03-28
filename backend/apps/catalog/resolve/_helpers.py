"""Shared helpers for claim resolution: coercion, FK lookup, priority annotation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from django.db import models

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class FKInfo:
    """FK field metadata and pre-fetched lookups for bulk resolution."""

    fk_fields: set[str] = field(default_factory=set)
    lookups: dict[str, dict[str, Any]] = field(default_factory=dict)


# ------------------------------------------------------------------
# Generic FK resolution (model-introspected)
# ------------------------------------------------------------------


def _resolve_fk_generic(
    model_class: type[models.Model],
    field_name: str,
    value,
    lookup: dict[str, Any] | None = None,
) -> Any | None:
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
    fk_lookups_map = getattr(model_class, "claim_fk_lookups", {})
    lookup_key = fk_lookups_map.get(field_name, "slug")

    if lookup is not None:
        result = lookup.get(key)
    else:
        result = target_model.objects.filter(**{lookup_key: key}).first()
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
            info.lookups[attr] = {
                getattr(obj, lookup_key): obj for obj in target_model.objects.all()
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
    """Compute reset values for direct fields by inspecting Django model metadata."""
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
