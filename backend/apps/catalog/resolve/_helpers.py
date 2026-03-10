"""Shared constants, coercion helpers, and lookup builders for claim resolution."""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import models

from apps.provenance.models import Claim

from ..models import (
    Cabinet,
    DisplaySubtype,
    DisplayType,
    GameFormat,
    MachineModel,
    Manufacturer,
    System,
    TechnologyGeneration,
    Title,
)

logger = logging.getLogger(__name__)

# Fields on MachineModel that can be set directly from a claim value.
# Maps field_name (as stored in Claim.field_name) → model attribute name.
DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
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
}

# Fields that should be coerced to int (nullable).
_INT_FIELDS = {
    "year",
    "month",
    "player_count",
    "flipper_count",
    "ipdb_id",
    "pinside_id",
}

# Fields that should be coerced to Decimal (nullable).
_DECIMAL_FIELDS = {"ipdb_rating", "pinside_rating"}

# Fields that should be coerced to bool.
_BOOL_FIELDS = {"is_conversion"}


def _coerce(field_name: str, value):
    """Coerce a JSON claim value to the type expected by the model field."""
    if value is None or value == "":
        return None

    if field_name in _INT_FIELDS:
        try:
            return int(value)
        except ValueError, TypeError:
            logger.warning("Cannot coerce %r to int for field %s", value, field_name)
            return None

    if field_name in _DECIMAL_FIELDS:
        try:
            return Decimal(str(value))
        except InvalidOperation, ValueError, TypeError:
            logger.warning(
                "Cannot coerce %r to Decimal for field %s", value, field_name
            )
            return None

    if field_name in _BOOL_FIELDS:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return bool(value)

    return value


def _resolve_title_fk(value) -> Title | None:
    """Resolve a group claim value to a Title instance.

    The value is expected to be an OPDB group ID string (e.g., "G5pe4").
    """
    if value is None or value == "":
        return None
    title = Title.objects.filter(opdb_id=str(value)).first()
    if not title:
        logger.warning("Unmatched group claim value: %r", value)
    return title


def _resolve_manufacturer(value) -> Manufacturer | None:
    """Resolve a manufacturer claim value (slug) to a Manufacturer instance."""
    if value is None or value == "":
        return None
    slug = str(value).strip()
    if not slug:
        return None
    mfr = Manufacturer.objects.filter(slug=slug).first()
    if not mfr:
        logger.warning("Unmatched manufacturer claim slug: %r", value)
    return mfr


# ------------------------------------------------------------------
# Lookup builders (used by bulk resolution)
# ------------------------------------------------------------------


def _build_manufacturer_lookup() -> dict[str, Manufacturer]:
    """Pre-fetch all manufacturers into {slug: Manufacturer}."""
    return {m.slug: m for m in Manufacturer.objects.all()}


def _build_title_lookup() -> dict[str, Title]:
    """Pre-fetch all titles into {opdb_id: Title}."""
    return {t.opdb_id: t for t in Title.objects.all()}


def _build_system_lookup() -> dict[str, System]:
    """Pre-fetch all systems into {slug: System}."""
    return {s.slug: s for s in System.objects.all()}


def _resolve_system(value, system_lookup: dict[str, System]) -> System | None:
    if not value:
        return None
    result = system_lookup.get(str(value))
    if not result:
        logger.warning("Unmatched system claim slug: %r", value)
    return result


def _build_technology_generation_lookup() -> dict[str, TechnologyGeneration]:
    """Pre-fetch all technology generations into {slug: TechnologyGeneration}."""
    return {t.slug: t for t in TechnologyGeneration.objects.all()}


def _build_display_type_lookup() -> dict[str, DisplayType]:
    """Pre-fetch all display types into {slug: DisplayType}."""
    return {d.slug: d for d in DisplayType.objects.all()}


def _build_display_subtype_lookup() -> dict[str, DisplaySubtype]:
    """Pre-fetch all display subtypes into {slug: DisplaySubtype}."""
    return {d.slug: d for d in DisplaySubtype.objects.all()}


def _build_cabinet_lookup() -> dict[str, Cabinet]:
    """Pre-fetch all cabinets into {slug: Cabinet}."""
    return {c.slug: c for c in Cabinet.objects.all()}


def _build_game_format_lookup() -> dict[str, GameFormat]:
    """Pre-fetch all game formats into {slug: GameFormat}."""
    return {g.slug: g for g in GameFormat.objects.all()}


def _build_converted_from_lookup() -> dict[str, MachineModel]:
    """Pre-fetch all machine models into {slug: MachineModel}."""
    return {m.slug: m for m in MachineModel.objects.all()}


def _resolve_slug_fk(value, lookup: dict[str, Any], label: str):
    """Resolve a slug claim value to a model instance via a pre-fetched lookup."""
    if not value:
        return None
    result = lookup.get(str(value))
    if not result:
        logger.warning("Unmatched %s claim slug: %r", label, value)
    return result


def _resolve_manufacturer_bulk(
    value,
    mfr_lookup: dict[str, Manufacturer],
) -> Manufacturer | None:
    """Resolve a manufacturer slug to a Manufacturer using pre-fetched dict."""
    if value is None or value == "":
        return None
    result = mfr_lookup.get(str(value))
    if not result:
        logger.warning("Unmatched manufacturer claim slug: %r", value)
    return result


def _resolve_title_fk_bulk(value, group_lookup: dict[str, Title]) -> Title | None:
    """Same logic as _resolve_title_fk() but uses pre-fetched dict."""
    if value is None or value == "":
        return None
    title = group_lookup.get(str(value))
    if not title:
        logger.warning("Unmatched group claim value: %r", value)
    return title


# ------------------------------------------------------------------
# Field defaults cache (used by bulk resolution)
# ------------------------------------------------------------------

_field_defaults: dict[str, Any] | None = None


def _get_field_defaults() -> dict[str, Any]:
    """Compute reset values for all DIRECT_FIELDS (cached after first call)."""
    global _field_defaults
    if _field_defaults is not None:
        return _field_defaults
    defaults: dict[str, Any] = {}
    for attr in DIRECT_FIELDS.values():
        field = MachineModel._meta.get_field(attr)
        if hasattr(field, "default") and field.default is not models.NOT_PROVIDED:
            defaults[attr] = (
                field.default() if callable(field.default) else field.default
            )
        elif field.null:
            defaults[attr] = None
        else:
            defaults[attr] = ""
    _field_defaults = defaults
    return _field_defaults


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
    from django.db.models import Case, F, IntegerField, Value, When

    claims = (
        obj.claims.filter(is_active=True, field_name=field_name)
        .select_related("source", "user__profile")
        .annotate(
            effective_priority=Case(
                When(source__isnull=False, then=F("source__priority")),
                When(user__isnull=False, then=F("user__profile__priority")),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("claim_key", "-effective_priority", "-created_at")
    )

    winners: dict[str, Claim] = {}
    for claim in claims:
        if claim.claim_key not in winners:
            winners[claim.claim_key] = claim
    return winners
