"""Shared constants, coercion helpers, and lookup builders for claim resolution."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import models

from apps.provenance.models import Claim

from ..models import (
    Cabinet,
    CorporateEntity,
    DisplaySubtype,
    DisplayType,
    GameFormat,
    MachineModel,
    System,
    TechnologyGeneration,
    TechnologySubgeneration,
    Title,
)

logger = logging.getLogger(__name__)

# Fields on MachineModel that can be set directly from a claim value.
# Maps field_name (as stored in Claim.field_name) → model attribute name.
DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "description": "description",
    "year": "year",
    "month": "month",
    "player_count": "player_count",
    "production_quantity": "production_quantity",
    "flipper_count": "flipper_count",
    "ipdb_rating": "ipdb_rating",
    "pinside_rating": "pinside_rating",
    "ipdb_id": "ipdb_id",
    "opdb_id": "opdb_id",
    "pinside_id": "pinside_id",
    "is_conversion": "is_conversion",
    "is_remake": "is_remake",
}


# ------------------------------------------------------------------
# FK field registry
# ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FKFieldSpec:
    """Descriptor for a foreign-key field resolved from claims."""

    model_attr: str  # e.g. "title", "manufacturer"
    target_model: type  # e.g. Title, Manufacturer
    lookup_key: str  # field on target model used for lookup, e.g. "slug" or "opdb_id"


FK_FIELDS: dict[str, FKFieldSpec] = {
    "title": FKFieldSpec("title", Title, "slug"),
    "system": FKFieldSpec("system", System, "slug"),
    "technology_generation": FKFieldSpec(
        "technology_generation", TechnologyGeneration, "slug"
    ),
    "technology_subgeneration": FKFieldSpec(
        "technology_subgeneration", TechnologySubgeneration, "slug"
    ),
    "display_type": FKFieldSpec("display_type", DisplayType, "slug"),
    "display_subtype": FKFieldSpec("display_subtype", DisplaySubtype, "slug"),
    "cabinet": FKFieldSpec("cabinet", Cabinet, "slug"),
    "game_format": FKFieldSpec("game_format", GameFormat, "slug"),
    "corporate_entity": FKFieldSpec("corporate_entity", CorporateEntity, "slug"),
    "variant_of": FKFieldSpec("variant_of", MachineModel, "slug"),
    "converted_from": FKFieldSpec("converted_from", MachineModel, "slug"),
    "remake_of": FKFieldSpec("remake_of", MachineModel, "slug"),
}


def build_fk_lookups() -> dict[str, dict[str, Any]]:
    """Pre-fetch all FK lookup tables. Returns {claim_field_name: {key: instance}}."""
    lookups: dict[str, dict[str, Any]] = {}
    for field_name, spec in FK_FIELDS.items():
        lookups[field_name] = {
            getattr(obj, spec.lookup_key): obj
            for obj in spec.target_model.objects.all()
        }
    return lookups


def _resolve_fk(
    field_name: str,
    value,
    lookup: dict[str, Any] | None = None,
) -> Any | None:
    """Resolve a claim value to an FK instance, optionally using a pre-fetched lookup."""
    if not value:
        return None
    spec = FK_FIELDS[field_name]
    key = str(value).strip()
    if not key:
        return None
    if lookup is not None:
        result = lookup.get(key)
    else:
        result = spec.target_model.objects.filter(**{spec.lookup_key: key}).first()
    if not result:
        logger.warning("Unmatched %s claim value: %r", field_name, value)
    return result


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
        elif field.null:
            defaults[attr] = None
        else:
            defaults[attr] = ""
    return defaults


# ------------------------------------------------------------------
# Relationship winner picking
# ------------------------------------------------------------------


def _pick_relationship_winners(
    obj,
    field_name: str,
) -> dict[str, Claim]:
    """Fetch active relationship claims and pick winner per claim_key.

    Returns {claim_key: winning_claim}.
    """
    claims = _annotate_priority(obj.claims.filter(field_name=field_name)).order_by(
        "claim_key", "-effective_priority", "-created_at"
    )

    winners: dict[str, Claim] = {}
    for claim in claims:
        if claim.claim_key not in winners:
            winners[claim.claim_key] = claim
    return winners
