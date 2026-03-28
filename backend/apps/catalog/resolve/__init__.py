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
    MachineModel,
    Title,
)
from ._helpers import (
    FKInfo,
    _annotate_priority,
    _coerce,
    _resolve_fk_generic,
    build_fk_info,
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
    resolve_all_series_titles,
    resolve_all_tags,
    resolve_all_themes,
    resolve_all_title_abbreviations,
    resolve_corporate_entity_aliases,
    resolve_gameplay_feature_aliases,
    resolve_gameplay_feature_parents,
    resolve_manufacturer_aliases,
    resolve_person_aliases,
    resolve_reward_type_aliases,
    resolve_theme_aliases,
    resolve_theme_parents,
)

from ._entities import (  # noqa: F401
    _resolve_bulk as _resolve_bulk,
    _resolve_single as _resolve_single,
    resolve_all_entities as resolve_all_entities,
    resolve_entity as resolve_entity,
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
    from apps.core.models import get_claim_fields

    claim_fields = get_claim_fields(MachineModel)
    field_defaults = get_field_defaults(MachineModel, claim_fields)
    fk_info = build_fk_info(MachineModel, claim_fields)
    sfl_map = build_source_field_license_map()
    _apply_resolution(
        machine_model, winners, claim_fields, field_defaults, fk_info, sfl_map
    )

    # Post-resolution guards (single-object only — the bulk path handles
    # opdb_id conflicts differently via _resolve_opdb_conflicts).
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
    model_ids = {machine_model.pk}
    resolve_all_credits(model_ids=model_ids)
    resolve_all_themes(model_ids=model_ids)
    resolve_all_gameplay_features(model_ids=model_ids)
    resolve_all_reward_types(model_ids=model_ids)
    resolve_all_tags(model_ids=model_ids)
    resolve_all_model_abbreviations(model_ids=model_ids)

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

    from ..models import Franchise, Series, System

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
    resolve_all_series_titles()
    _status("Series titles resolved")
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
    from apps.core.models import get_claim_fields

    claim_fields = get_claim_fields(MachineModel)
    field_defaults = get_field_defaults(MachineModel, claim_fields)
    fk_info = build_fk_info(MachineModel, claim_fields)
    sfl_map = build_source_field_license_map()

    # 2. Pre-fetch all active claims, grouped by object_id (~1 query).
    claims_by_model = _build_claims_by_model()
    _status(f"Loaded {sum(len(v) for v in claims_by_model.values())} winning claims")

    # 3. Load all MachineModels (~1 query).
    all_models = list(MachineModel.objects.all())

    # 4. Resolve each model in memory.
    for pm in all_models:
        winners = claims_by_model.get(pm.pk, {})
        _apply_resolution(pm, winners, claim_fields, field_defaults, fk_info, sfl_map)

    # 5. Detect opdb_id conflicts across all resolved models.
    _resolve_opdb_conflicts(all_models)

    # 7. Set updated_at (auto_now not triggered by bulk_update).
    now = timezone.now()
    for pm in all_models:
        pm.updated_at = now

    # 8. Bulk write (~1 query, batched).
    update_fields = list(claim_fields.values()) + ["extra_data", "updated_at"]
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
    claim_fields: dict[str, str],
    field_defaults: dict[str, Any],
    fk_info: FKInfo,
    sfl_map: dict | None = None,
) -> None:
    """Apply claim winners to a MachineModel instance in memory."""
    # Reset all claim-controlled fields to defaults.
    for attr, default in field_defaults.items():
        setattr(pm, attr, default)

    # Fresh extra_data dict (never shared between models).
    extra_data: dict = {}

    # Apply winners.
    for claim_key, claim in winners.items():
        if claim.field_name in RELATIONSHIP_NAMESPACES:
            continue
        if claim.field_name in claim_fields:
            attr = claim_fields[claim.field_name]
            if attr in fk_info.fk_fields:
                setattr(
                    pm,
                    attr,
                    _resolve_fk_generic(
                        MachineModel,
                        attr,
                        claim.value,
                        lookup=fk_info.lookups.get(attr),
                    ),
                )
            else:
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
