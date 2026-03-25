"""Claim resolution logic.

Given a catalog entity, fetch all active claims, pick the winner per
claim_key (highest source priority, most recent if tied), and write back
the resolved values.
"""

from __future__ import annotations

import logging
from typing import Any

from django.utils import timezone

from apps.core.licensing import (
    IMAGE_FIELDS,
    build_source_field_license_map,
    resolve_effective_license,
)
from apps.provenance.models import Claim

from ..claims import RELATIONSHIP_NAMESPACES
from ..models import (
    Franchise,
    MachineModel,
    Title,
)
from ._helpers import (
    DIRECT_FIELDS,
    FK_FIELDS,
    _annotate_priority,
    _coerce,
    _resolve_fk,
    build_fk_lookups,
    get_field_defaults,
)
from ._relationships import (  # noqa: F401
    resolve_all_aliases,
    resolve_all_corporate_entity_locations,
    resolve_all_credits,
    resolve_all_gameplay_features,
    resolve_all_location_aliases,
    resolve_all_model_abbreviations,
    resolve_all_reward_types,
    resolve_all_tags,
    resolve_all_themes,
    resolve_all_title_abbreviations,
    resolve_corporate_entity_aliases,
    resolve_credits,
    resolve_gameplay_feature_aliases,
    resolve_gameplay_feature_parents,
    resolve_gameplay_features,
    resolve_manufacturer_aliases,
    resolve_model_abbreviations,
    resolve_person_aliases,
    resolve_reward_type_aliases,
    resolve_reward_types,
    resolve_tags,
    resolve_theme_aliases,
    resolve_theme_parents,
    resolve_themes,
)

# Re-exports: explicit `as` aliases satisfy ruff F401 for public API.
from ._entities import (  # noqa: F401
    # Legacy field map constants (still used by some ingest commands and tests).
    CORPORATE_ENTITY_DIRECT_FIELDS as CORPORATE_ENTITY_DIRECT_FIELDS,
    FRANCHISE_DIRECT_FIELDS as FRANCHISE_DIRECT_FIELDS,
    GAMEPLAY_FEATURE_DIRECT_FIELDS as GAMEPLAY_FEATURE_DIRECT_FIELDS,
    MANUFACTURER_DIRECT_FIELDS as MANUFACTURER_DIRECT_FIELDS,
    PERSON_DIRECT_FIELDS as PERSON_DIRECT_FIELDS,
    SERIES_DIRECT_FIELDS as SERIES_DIRECT_FIELDS,
    SYSTEM_DIRECT_FIELDS as SYSTEM_DIRECT_FIELDS,
    TAXONOMY_DIRECT_FIELDS as TAXONOMY_DIRECT_FIELDS,
    TAXONOMY_MODELS as TAXONOMY_MODELS,
    THEME_DIRECT_FIELDS as THEME_DIRECT_FIELDS,
    TITLE_DIRECT_FIELDS as TITLE_DIRECT_FIELDS,
    # Internals used by the orchestrator and tests.
    _resolve_all_taxonomy,
    _resolve_bulk as _resolve_bulk,
    _resolve_single as _resolve_single,
    # Generic resolvers (preferred API).
    resolve_all_entities as resolve_all_entities,
    resolve_entity as resolve_entity,
    # Legacy wrappers (delegate to resolve_entity/resolve_all_entities).
    resolve_all_gameplay_feature_entities as resolve_all_gameplay_feature_entities,
    resolve_all_locations as resolve_all_locations,
    resolve_all_theme_entities as resolve_all_theme_entities,
    resolve_corporate_entity as resolve_corporate_entity,
    resolve_franchise as resolve_franchise,
    resolve_gameplay_feature as resolve_gameplay_feature,
    resolve_manufacturer as resolve_manufacturer,
    resolve_person as resolve_person,
    resolve_series as resolve_series,
    resolve_system as resolve_system,
    resolve_taxonomy as resolve_taxonomy,
    resolve_theme as resolve_theme,
    resolve_title as resolve_title,
)

logger = logging.getLogger(__name__)


def resolve_model(machine_model: MachineModel) -> MachineModel:
    """Resolve all active claims into the given MachineModel's fields.

    Picks the winning claim per claim_key: highest effective priority
    (from source or user profile), then most recent created_at as tiebreaker.
    Delegates field application to ``_apply_resolution()`` (shared with the
    bulk path in ``resolve_machine_models()``).

    Returns the saved MachineModel.
    """
    # Fetch and pick winners (single-object).
    claims = (
        _annotate_priority(machine_model.claims.all())
        .select_related("source__default_license")
        .order_by("claim_key", "-effective_priority", "-created_at")
    )
    winners: dict[str, Claim] = {}
    for claim in claims:
        if claim.claim_key not in winners:
            winners[claim.claim_key] = claim

    # Apply field values (shared with bulk path).
    field_defaults = get_field_defaults(MachineModel, DIRECT_FIELDS)
    fk_lookups = build_fk_lookups()
    sfl_map = build_source_field_license_map()
    _apply_resolution(machine_model, winners, field_defaults, fk_lookups, sfl_map)

    # Post-resolution guards (single-object only — the bulk path handles
    # these differently via _resolve_opdb_conflicts and a separate loop).
    if machine_model.is_conversion and machine_model.variant_of_id is not None:
        machine_model.variant_of = None
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
    resolve_reward_types(machine_model)
    resolve_tags(machine_model)
    resolve_model_abbreviations(machine_model)

    return machine_model


def resolve_machine_models(stdout=None) -> int:
    """Re-resolve every MachineModel and its dependencies from claims (bulk-optimized).

    Resolves in dependency order: locations → taxonomy → titles → machine models
    + their relationships (credits, themes, gameplay features, etc.).
    Does NOT resolve manufacturers, corporate entities, or people.
    Pre-fetches all lookup tables and claims in ~4 queries, resolves
    in memory, then writes back with a single bulk_update().
    """

    def _status(msg: str) -> None:
        if stdout:
            stdout.write(f"  {msg}")

    # 0. Resolve entity scalars in dependency order (FK targets first).
    from ..models import (
        Location,
        Theme,
        GameplayFeature,
    )
    from ..models.taxonomy import (
        TechnologyGeneration,
        TechnologySubgeneration,
        DisplayType,
        DisplaySubtype,
        Cabinet,
        GameFormat,
        RewardType,
        Tag,
        CreditRole,
    )

    resolve_all_entities(Location)
    resolve_all_location_aliases()
    _status("Locations resolved")

    from ..models import Series, System

    for tax_model in [
        TechnologyGeneration,
        TechnologySubgeneration,
        DisplayType,
        DisplaySubtype,
        Cabinet,
        GameFormat,
        RewardType,
        Tag,
        CreditRole,
        Franchise,
        Series,
        System,
    ]:
        resolve_all_entities(tax_model)
    resolve_all_entities(Theme)
    resolve_all_entities(GameplayFeature)
    _status("Taxonomy, themes, gameplay features resolved")

    resolve_theme_parents()
    resolve_gameplay_feature_parents()
    resolve_all_aliases()
    _status("Hierarchy and aliases resolved")

    resolve_all_corporate_entity_locations()
    _status("Corporate entity locations resolved")

    resolve_all_entities(Title)
    _status("Titles resolved")

    # 0c. Resolve title abbreviations.
    resolve_all_title_abbreviations(list(Title.objects.all()))

    # 1. Pre-fetch lookup tables.
    fk_lookups = build_fk_lookups()
    field_defaults = get_field_defaults(MachineModel, DIRECT_FIELDS)
    sfl_map = build_source_field_license_map()

    # 2. Pre-fetch all active claims, grouped by object_id (~1 query).
    claims_by_model = _build_claims_by_model()
    _status(f"Loaded {sum(len(v) for v in claims_by_model.values())} winning claims")

    # 3. Load all MachineModels (~1 query).
    all_models = list(MachineModel.objects.all())

    # 4. Resolve each model in memory.
    for pm in all_models:
        winners = claims_by_model.get(pm.pk, {})
        _apply_resolution(pm, winners, field_defaults, fk_lookups, sfl_map)

    # 5. Conversions are not variants: clear variant_of on conversion models.
    for pm in all_models:
        if pm.is_conversion and pm.variant_of_id is not None:
            pm.variant_of = None

    # 6. Detect opdb_id conflicts across all resolved models.
    _resolve_opdb_conflicts(all_models)

    # 7. Set updated_at (auto_now not triggered by bulk_update).
    now = timezone.now()
    for pm in all_models:
        pm.updated_at = now

    # 8. Bulk write (~1 query, batched).
    update_fields = (
        list(DIRECT_FIELDS.values())
        + [f"{spec.model_attr}_id" for spec in FK_FIELDS.values()]
        + ["extra_data", "updated_at"]
    )
    # batch_size=100 is optimal for SQLite (CASE WHEN overhead grows with
    # batch size × field count). PostgreSQL uses a more efficient UPDATE FROM
    # VALUES syntax and handles larger batches fine.
    MachineModel.objects.bulk_update(all_models, update_fields, batch_size=100)
    _status(f"Wrote {len(all_models)} models")

    # 9. Bulk-resolve credit relationships.
    resolve_all_credits(all_models)
    _status("Credits resolved")

    # 10. Bulk-resolve theme relationships.
    resolve_all_themes(all_models)

    # 11. Bulk-resolve gameplay feature relationships.
    resolve_all_gameplay_features(all_models)

    # 12. Bulk-resolve reward type relationships.
    resolve_all_reward_types(all_models)

    # 13. Bulk-resolve tag relationships.
    resolve_all_tags(all_models)
    _status("Themes, features, reward types, tags resolved")

    # 14. Bulk-resolve model abbreviations.
    resolve_all_model_abbreviations(all_models)
    _status("Abbreviations resolved")

    return len(all_models)


# ------------------------------------------------------------------
# Bulk resolution helpers (used by resolve_machine_models)
# ------------------------------------------------------------------


def _build_claims_by_model() -> dict[int, dict[str, Claim]]:
    """Pre-fetch all active claims for MachineModel, pick winner per (object_id, claim_key).

    Returns {object_id: {claim_key: winning_claim}}.
    """
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(MachineModel)
    claims = (
        _annotate_priority(Claim.objects.filter(content_type=ct))
        .select_related("source__default_license")
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
    fk_lookups: dict[str, dict[str, Any]],
    sfl_map: dict | None = None,
) -> None:
    """Apply claim winners to a MachineModel instance in memory."""
    # Reset FK fields.
    for spec in FK_FIELDS.values():
        setattr(pm, spec.model_attr, None)

    # Reset all DIRECT_FIELDS to defaults.
    for attr, default in field_defaults.items():
        setattr(pm, attr, default)

    # Fresh extra_data dict (never shared between models).
    extra_data: dict = {}

    # Apply winners.
    for claim_key, claim in winners.items():
        if claim.field_name in RELATIONSHIP_NAMESPACES:
            continue
        if claim.field_name in FK_FIELDS:
            spec = FK_FIELDS[claim.field_name]
            setattr(
                pm,
                spec.model_attr,
                _resolve_fk(
                    claim.field_name, claim.value, fk_lookups.get(claim.field_name)
                ),
            )
        elif claim.field_name in DIRECT_FIELDS:
            attr = DIRECT_FIELDS[claim.field_name]
            setattr(pm, attr, _coerce(MachineModel, attr, claim.value))
        else:
            extra_data[claim.field_name] = claim.value
            if claim.field_name in IMAGE_FIELDS:
                lic = resolve_effective_license(claim, sfl_map)
                extra_data[f"{claim.field_name}.__license_slug"] = (
                    lic.slug if lic else None
                )
                extra_data[f"{claim.field_name}.__permissiveness_rank"] = (
                    lic.permissiveness_rank if lic else None
                )

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
