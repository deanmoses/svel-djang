"""Claim resolution logic.

Given a catalog entity, fetch all active claims, pick the winner per
claim_key (highest source priority, most recent if tied), and write back
the resolved values.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import models
from django.db.models import Case, F, IntegerField, Value, When
from django.utils import timezone

from apps.provenance.models import Claim

from ..claims import RELATIONSHIP_NAMESPACES
from ..models import (
    Cabinet,
    DisplaySubtype,
    DisplayType,
    Franchise,
    GameFormat,
    MachineModel,
    TechnologyGeneration,
    Title,
)
from ._helpers import (
    DIRECT_FIELDS,
    _build_cabinet_lookup,
    _build_display_subtype_lookup,
    _build_display_type_lookup,
    _build_game_format_lookup,
    _build_manufacturer_lookup,
    _build_system_lookup,
    _build_technology_generation_lookup,
    _build_title_lookup,
    _coerce,
    _get_field_defaults,
    _resolve_manufacturer,
    _resolve_manufacturer_bulk,
    _resolve_slug_fk,
    _resolve_system,
    _resolve_title_fk,
    _resolve_title_fk_bulk,
)
from ._relationships import (
    _resolve_all_gameplay_features,
    _resolve_all_tags,
    resolve_all_credits,
    resolve_all_model_abbreviations,
    resolve_all_themes,
    resolve_all_title_abbreviations,
    resolve_credits,
    resolve_gameplay_features,
    resolve_model_abbreviations,
    resolve_tags,
    resolve_themes,
)

# Re-exports: explicit `as` aliases satisfy ruff F401 for public API.
from ._entities import (  # noqa: F401
    CORPORATE_ENTITY_DIRECT_FIELDS as CORPORATE_ENTITY_DIRECT_FIELDS,
    FRANCHISE_DIRECT_FIELDS as FRANCHISE_DIRECT_FIELDS,
    MANUFACTURER_DIRECT_FIELDS as MANUFACTURER_DIRECT_FIELDS,
    PERSON_DIRECT_FIELDS as PERSON_DIRECT_FIELDS,
    SYSTEM_DIRECT_FIELDS as SYSTEM_DIRECT_FIELDS,
    TAXONOMY_DIRECT_FIELDS as TAXONOMY_DIRECT_FIELDS,
    TAXONOMY_MODELS as TAXONOMY_MODELS,
    THEME_DIRECT_FIELDS as THEME_DIRECT_FIELDS,
    TITLE_DIRECT_FIELDS as TITLE_DIRECT_FIELDS,
    _MANUFACTURER_INT_FIELDS as _MANUFACTURER_INT_FIELDS,
    _PERSON_INT_FIELDS as _PERSON_INT_FIELDS,
    _TAXONOMY_INT_FIELDS as _TAXONOMY_INT_FIELDS,
    _resolve_all_taxonomy,
    _resolve_bulk as _resolve_bulk,
    _resolve_single as _resolve_single,
    resolve_corporate_entity as resolve_corporate_entity,
    resolve_manufacturer as resolve_manufacturer,
    resolve_person as resolve_person,
    resolve_system as resolve_system,
    resolve_theme as resolve_theme,
    resolve_title as resolve_title,
)

logger = logging.getLogger(__name__)


def resolve_model(machine_model: MachineModel) -> MachineModel:
    """Resolve all active claims into the given MachineModel's fields.

    Picks the winning claim per field_name: highest effective priority
    (from source or user profile), then most recent created_at as tiebreaker.

    Returns the saved MachineModel.
    """
    claims = (
        machine_model.claims.filter(is_active=True)
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

    # Group by claim_key — first claim per group is the winner.
    winners: dict[str, Claim] = {}
    for claim in claims:
        if claim.claim_key not in winners:
            winners[claim.claim_key] = claim

    # Reset all resolvable fields to defaults before applying winners.
    # This ensures deactivated claims don't leave stale values.
    machine_model.manufacturer = None
    machine_model.title = None
    machine_model.system = None
    machine_model.technology_generation = None
    machine_model.display_type = None
    machine_model.display_subtype = None
    machine_model.cabinet = None
    machine_model.game_format = None
    for attr in DIRECT_FIELDS.values():
        field = machine_model._meta.get_field(attr)
        if hasattr(field, "default") and field.default is not models.NOT_PROVIDED:
            setattr(machine_model, attr, field.default)
        elif field.null:
            setattr(machine_model, attr, None)
        else:
            setattr(machine_model, attr, "")
    extra_data: dict = {}

    techgen_lookup = _build_technology_generation_lookup()
    display_type_lookup = _build_display_type_lookup()
    display_subtype_lookup = _build_display_subtype_lookup()
    cabinet_lookup = _build_cabinet_lookup()
    game_format_lookup = _build_game_format_lookup()

    # Apply winners to the model.
    for claim_key, claim in winners.items():
        if claim.field_name in RELATIONSHIP_NAMESPACES:
            continue  # Handled by resolve_credits()
        if claim.field_name == "manufacturer":
            machine_model.manufacturer = _resolve_manufacturer(claim.value)
        elif claim.field_name == "group":
            machine_model.title = _resolve_title_fk(claim.value)
        elif claim.field_name == "system":
            machine_model.system = _resolve_system(claim.value, _build_system_lookup())
        elif claim.field_name == "technology_generation":
            machine_model.technology_generation = _resolve_slug_fk(
                claim.value, techgen_lookup, "technology_generation"
            )
        elif claim.field_name == "display_type":
            machine_model.display_type = _resolve_slug_fk(
                claim.value, display_type_lookup, "display_type"
            )
        elif claim.field_name == "display_subtype":
            machine_model.display_subtype = _resolve_slug_fk(
                claim.value, display_subtype_lookup, "display_subtype"
            )
        elif claim.field_name == "cabinet":
            machine_model.cabinet = _resolve_slug_fk(
                claim.value, cabinet_lookup, "cabinet"
            )
        elif claim.field_name == "game_format":
            machine_model.game_format = _resolve_slug_fk(
                claim.value, game_format_lookup, "game_format"
            )
        elif claim.field_name in DIRECT_FIELDS:
            attr = DIRECT_FIELDS[claim.field_name]
            setattr(machine_model, attr, _coerce(claim.field_name, claim.value))
        else:
            # Goes into extra_data catch-all.
            extra_data[claim.field_name] = claim.value

    machine_model.extra_data = extra_data

    # Guard against UNIQUE constraint on opdb_id: if another model already
    # owns this opdb_id, clear it rather than crashing.
    if machine_model.opdb_id:
        conflict = (
            MachineModel.objects.filter(opdb_id=machine_model.opdb_id)
            .exclude(pk=machine_model.pk)
            .first()
        )
        if conflict:
            logger.warning(
                "Cannot resolve opdb_id=%s onto '%s' (pk=%s): "
                "already owned by '%s' (pk=%s)",
                machine_model.opdb_id,
                machine_model.name,
                machine_model.pk,
                conflict.name,
                conflict.pk,
            )
            machine_model.opdb_id = None

    machine_model.save()

    # Resolve relationship claims after scalar save.
    resolve_credits(machine_model)
    resolve_themes(machine_model)
    resolve_gameplay_features(machine_model)
    resolve_tags(machine_model)
    resolve_model_abbreviations(machine_model)

    return machine_model


def resolve_all() -> int:
    """Re-resolve every MachineModel from its claims (bulk-optimized).

    Pre-fetches all lookup tables and claims in ~4 queries, resolves
    in memory, then writes back with a single bulk_update().
    Also resolves taxonomy models.
    """
    # 0a. Resolve taxonomy models first (they are FK targets).
    _resolve_all_taxonomy()

    # 0b. Resolve titles (they are FK targets for MachineModel).
    franchise_lookup = {f.slug: f for f in Franchise.objects.all()}
    _resolve_bulk(
        Title,
        TITLE_DIRECT_FIELDS,
        fk_handlers={"franchise": ("franchise", franchise_lookup)},
    )

    # 0c. Resolve title abbreviations.
    resolve_all_title_abbreviations(list(Title.objects.all()))

    # 1. Pre-fetch lookup tables.
    mfr_lookup = _build_manufacturer_lookup()
    group_lookup = _build_title_lookup()
    system_lookup = _build_system_lookup()
    techgen_lookup = _build_technology_generation_lookup()
    display_type_lookup = _build_display_type_lookup()
    display_subtype_lookup = _build_display_subtype_lookup()
    cabinet_lookup = _build_cabinet_lookup()
    game_format_lookup = _build_game_format_lookup()
    field_defaults = _get_field_defaults()

    # 2. Pre-fetch all active claims, grouped by object_id (~1 query).
    claims_by_model = _build_claims_by_model()

    # 3. Load all MachineModels (~1 query).
    all_models = list(MachineModel.objects.all())

    # 4. Resolve each model in memory.
    for pm in all_models:
        winners = claims_by_model.get(pm.pk, {})
        _apply_resolution(
            pm,
            winners,
            field_defaults,
            mfr_lookup,
            group_lookup,
            system_lookup,
            techgen_lookup,
            display_type_lookup,
            display_subtype_lookup,
            cabinet_lookup,
            game_format_lookup,
        )

    # 5. Detect opdb_id conflicts across all resolved models.
    _resolve_opdb_conflicts(all_models)

    # 6. Set updated_at (auto_now not triggered by bulk_update).
    now = timezone.now()
    for pm in all_models:
        pm.updated_at = now

    # 7. Bulk write (~1 query, batched).
    update_fields = list(DIRECT_FIELDS.values()) + [
        "manufacturer_id",
        "title_id",
        "system_id",
        "technology_generation_id",
        "display_type_id",
        "display_subtype_id",
        "cabinet_id",
        "game_format_id",
        "extra_data",
        "updated_at",
    ]
    # batch_size=100 is optimal for SQLite (CASE WHEN overhead grows with
    # batch size × field count). PostgreSQL uses a more efficient UPDATE FROM
    # VALUES syntax and handles larger batches fine.
    MachineModel.objects.bulk_update(all_models, update_fields, batch_size=100)

    # 8. Bulk-resolve credit relationships.
    resolve_all_credits(all_models)

    # 9. Bulk-resolve theme relationships.
    resolve_all_themes(all_models)

    # 10. Bulk-resolve gameplay feature relationships.
    _resolve_all_gameplay_features(all_models)

    # 11. Bulk-resolve tag relationships.
    _resolve_all_tags(all_models)

    # 12. Bulk-resolve model abbreviations.
    resolve_all_model_abbreviations(all_models)

    return len(all_models)


# ------------------------------------------------------------------
# Bulk resolution helpers (used by resolve_all)
# ------------------------------------------------------------------


def _build_claims_by_model() -> dict[int, dict[str, Claim]]:
    """Pre-fetch all active claims for MachineModel, pick winner per (object_id, claim_key).

    Returns {object_id: {claim_key: winning_claim}}.
    """
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(MachineModel)
    claims = (
        Claim.objects.filter(is_active=True, content_type=ct)
        .select_related("source", "user__profile")
        .annotate(
            effective_priority=Case(
                When(source__isnull=False, then=F("source__priority")),
                When(user__isnull=False, then=F("user__profile__priority")),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("object_id", "claim_key", "-effective_priority", "-created_at")
    )

    result: dict[int, dict[str, Claim]] = {}
    for claim in claims:
        model_winners = result.setdefault(claim.object_id, {})
        # First claim per (object_id, claim_key) group is the winner.
        if claim.claim_key not in model_winners:
            model_winners[claim.claim_key] = claim

    return result


def _apply_resolution(
    pm: MachineModel,
    winners: dict[str, Claim],
    field_defaults: dict[str, Any],
    mfr_lookup: dict,
    group_lookup: dict,
    system_lookup: dict,
    techgen_lookup: dict[str, TechnologyGeneration] | None = None,
    display_type_lookup: dict[str, DisplayType] | None = None,
    display_subtype_lookup: dict[str, DisplaySubtype] | None = None,
    cabinet_lookup: dict[str, Cabinet] | None = None,
    game_format_lookup: dict[str, GameFormat] | None = None,
) -> None:
    """Apply claim winners to a MachineModel instance in memory."""
    # Reset FK fields.
    pm.manufacturer = None
    pm.title = None
    pm.system = None
    pm.technology_generation = None
    pm.display_type = None
    pm.display_subtype = None
    pm.cabinet = None
    pm.game_format = None

    # Reset all DIRECT_FIELDS to defaults.
    for attr, default in field_defaults.items():
        setattr(pm, attr, default)

    # Fresh extra_data dict (never shared between models).
    extra_data: dict = {}

    # Apply winners.
    for claim_key, claim in winners.items():
        if claim.field_name in RELATIONSHIP_NAMESPACES:
            continue  # Handled by bulk credit/recipient resolution
        if claim.field_name == "manufacturer":
            pm.manufacturer = _resolve_manufacturer_bulk(
                claim.value,
                mfr_lookup=mfr_lookup,
            )
        elif claim.field_name == "group":
            pm.title = _resolve_title_fk_bulk(claim.value, group_lookup)
        elif claim.field_name == "system":
            pm.system = _resolve_system(claim.value, system_lookup)
        elif claim.field_name == "technology_generation":
            if techgen_lookup is not None:
                pm.technology_generation = _resolve_slug_fk(
                    claim.value, techgen_lookup, "technology_generation"
                )
        elif claim.field_name == "display_type":
            if display_type_lookup is not None:
                pm.display_type = _resolve_slug_fk(
                    claim.value, display_type_lookup, "display_type"
                )
        elif claim.field_name == "display_subtype":
            if display_subtype_lookup is not None:
                pm.display_subtype = _resolve_slug_fk(
                    claim.value, display_subtype_lookup, "display_subtype"
                )
        elif claim.field_name == "cabinet":
            if cabinet_lookup is not None:
                pm.cabinet = _resolve_slug_fk(claim.value, cabinet_lookup, "cabinet")
        elif claim.field_name == "game_format":
            if game_format_lookup is not None:
                pm.game_format = _resolve_slug_fk(
                    claim.value, game_format_lookup, "game_format"
                )
        elif claim.field_name in DIRECT_FIELDS:
            attr = DIRECT_FIELDS[claim.field_name]
            setattr(pm, attr, _coerce(claim.field_name, claim.value))
        else:
            extra_data[claim.field_name] = claim.value

    pm.extra_data = extra_data


def _resolve_opdb_conflicts(all_models: list[MachineModel]) -> None:
    """Clear opdb_id on models that would cause UNIQUE constraint violations.

    First model encountered (by queryset order) wins ownership.
    """
    seen_opdb_ids: dict[str, MachineModel] = {}
    for pm in all_models:
        if not pm.opdb_id:
            continue
        if pm.opdb_id in seen_opdb_ids:
            owner = seen_opdb_ids[pm.opdb_id]
            logger.warning(
                "Cannot resolve opdb_id=%s onto '%s' (pk=%s): "
                "already owned by '%s' (pk=%s)",
                pm.opdb_id,
                pm.name,
                pm.pk,
                owner.name,
                owner.pk,
            )
            pm.opdb_id = None
        else:
            seen_opdb_ids[pm.opdb_id] = pm
