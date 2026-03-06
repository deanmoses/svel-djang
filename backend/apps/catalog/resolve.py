"""Claim resolution logic.

Given a catalog entity, fetch all active claims, pick the winner per
claim_key (highest source priority, most recent if tied), and write back
the resolved values.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import models
from django.db.models import Case, F, IntegerField, Value, When
from django.utils import timezone

from apps.provenance.models import Claim

from .claims import RELATIONSHIP_NAMESPACES
from .models import (
    Cabinet,
    CorporateEntity,
    DesignCredit,
    DisplaySubtype,
    DisplayType,
    Franchise,
    GameFormat,
    GameplayFeature,
    MachineModel,
    Manufacturer,
    Person,
    System,
    Tag,
    TechnologyGeneration,
    TechnologySubgeneration,
    Theme,
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
    "educational_text": "educational_text",
    "sources_notes": "sources_notes",
    "ipdb_id": "ipdb_id",
    "opdb_id": "opdb_id",
    "pinside_id": "pinside_id",
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

    return value


def _resolve_title(value) -> Title | None:
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
            machine_model.title = _resolve_title(claim.value)
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

    return machine_model


def resolve_all() -> int:
    """Re-resolve every MachineModel from its claims (bulk-optimized).

    Pre-fetches all lookup tables and claims in ~4 queries, resolves
    in memory, then writes back with a single bulk_update().
    Also resolves taxonomy models.
    """
    # 0. Resolve taxonomy models first (they are FK targets).
    _resolve_all_taxonomy()

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
    _resolve_all_credits(all_models)

    # 9. Bulk-resolve theme relationships.
    _resolve_all_themes(all_models)

    # 10. Bulk-resolve gameplay feature relationships.
    _resolve_all_gameplay_features(all_models)

    # 11. Bulk-resolve tag relationships.
    _resolve_all_tags(all_models)

    return len(all_models)


# ------------------------------------------------------------------
# Bulk resolution helpers (used by resolve_all)
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


def _resolve_slug_fk(value, lookup: dict[str, Any], label: str):
    """Resolve a slug claim value to a model instance via a pre-fetched lookup."""
    if not value:
        return None
    result = lookup.get(str(value))
    if not result:
        logger.warning("Unmatched %s claim slug: %r", label, value)
    return result


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


def _resolve_title_bulk(value, group_lookup: dict[str, Title]) -> Title | None:
    """Same logic as _resolve_title() but uses pre-fetched dict."""
    if value is None or value == "":
        return None
    title = group_lookup.get(str(value))
    if not title:
        logger.warning("Unmatched group claim value: %r", value)
    return title


def _apply_resolution(
    pm: MachineModel,
    winners: dict[str, Claim],
    field_defaults: dict[str, Any],
    mfr_lookup: dict[str, Manufacturer],
    group_lookup: dict[str, Title],
    system_lookup: dict[str, System],
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
            pm.title = _resolve_title_bulk(claim.value, group_lookup)
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


MANUFACTURER_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "trade_name": "trade_name",
    "description": "description",
    "founded_year": "founded_year",
    "dissolved_year": "dissolved_year",
    "country": "country",
    "headquarters": "headquarters",
    "logo_url": "logo_url",
    "website": "website",
}

_MANUFACTURER_INT_FIELDS: frozenset[str] = frozenset({"founded_year", "dissolved_year"})

PERSON_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "bio": "bio",
    "birth_year": "birth_year",
    "birth_month": "birth_month",
    "birth_day": "birth_day",
    "death_year": "death_year",
    "death_month": "death_month",
    "death_day": "death_day",
    "birth_place": "birth_place",
    "nationality": "nationality",
    "photo_url": "photo_url",
}

_PERSON_INT_FIELDS: frozenset[str] = frozenset(
    {
        "birth_year",
        "birth_month",
        "birth_day",
        "death_year",
        "death_month",
        "death_day",
    }
)


def _resolve_simple(
    obj,
    direct_fields: dict[str, str],
    int_fields: frozenset[str] | None = None,
) -> None:
    """Resolve active claims onto an object with only direct fields.

    All resolvable fields are reset to their defaults first, then active
    claim winners are applied.  Claims are the sole source of truth for
    these fields: a field with no active claim will be blank/null after
    resolution regardless of what was previously stored.

    Mutates *obj* in memory; the caller is responsible for saving.
    Pass *int_fields* to coerce matching claim values to ``int``.
    """
    claims = (
        obj.claims.filter(is_active=True)
        .select_related("source", "user__profile")
        .annotate(
            effective_priority=Case(
                When(source__isnull=False, then=F("source__priority")),
                When(user__isnull=False, then=F("user__profile__priority")),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("field_name", "-effective_priority", "-created_at")
    )

    winners: dict[str, Claim] = {}
    for claim in claims:
        if claim.field_name not in winners:
            winners[claim.field_name] = claim

    # Reset resolvable fields to defaults.
    for attr in direct_fields.values():
        field = obj._meta.get_field(attr)
        if hasattr(field, "default") and field.default is not models.NOT_PROVIDED:
            default = field.default() if callable(field.default) else field.default
            setattr(obj, attr, default)
        elif field.null:
            setattr(obj, attr, None)
        else:
            setattr(obj, attr, "")

    # Apply winners.
    for field_name, claim in winners.items():
        if field_name in direct_fields:
            attr = direct_fields[field_name]
            value = claim.value
            if int_fields and field_name in int_fields:
                setattr(obj, attr, None if value is None else int(value))
            else:
                setattr(obj, attr, "" if value is None else value)


def resolve_manufacturer(mfr: Manufacturer) -> Manufacturer:
    """Resolve active claims into the given Manufacturer's fields.

    Returns the saved Manufacturer.
    """
    _resolve_simple(
        mfr, MANUFACTURER_DIRECT_FIELDS, int_fields=_MANUFACTURER_INT_FIELDS
    )
    mfr.save()
    return mfr


def resolve_person(person: Person) -> Person:
    """Resolve active claims into the given Person's fields.

    Returns the saved Person.
    """
    _resolve_simple(person, PERSON_DIRECT_FIELDS, int_fields=_PERSON_INT_FIELDS)
    person.save()
    return person


THEME_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "description": "description",
}


def resolve_theme(theme: Theme) -> Theme:
    """Resolve active claims into the given Theme's fields.

    Returns the saved Theme.
    """
    _resolve_simple(theme, THEME_DIRECT_FIELDS)
    theme.save()
    return theme


CORPORATE_ENTITY_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "years_active": "years_active",
}


def resolve_corporate_entity(entity: CorporateEntity) -> CorporateEntity:
    """Resolve active claims into the given CorporateEntity's fields.

    Returns the saved CorporateEntity.
    """
    _resolve_simple(entity, CORPORATE_ENTITY_DIRECT_FIELDS)
    entity.save()
    return entity


SYSTEM_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "description": "description",
}


def resolve_system(system: System) -> System:
    """Resolve active claims into the given System's fields.

    Returns the saved System.
    """
    _resolve_simple(system, SYSTEM_DIRECT_FIELDS)
    system.save()
    return system


# Taxonomy models: name and display_order are claim-controlled.
TAXONOMY_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "display_order": "display_order",
}

_TAXONOMY_INT_FIELDS: frozenset[str] = frozenset({"display_order"})

# Franchise has no display_order.
FRANCHISE_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
}

# All taxonomy models that go through claim resolution.
TAXONOMY_MODELS: list[tuple[type, dict[str, str], frozenset[str] | None]] = [
    (TechnologyGeneration, TAXONOMY_DIRECT_FIELDS, _TAXONOMY_INT_FIELDS),
    (TechnologySubgeneration, TAXONOMY_DIRECT_FIELDS, _TAXONOMY_INT_FIELDS),
    (DisplayType, TAXONOMY_DIRECT_FIELDS, _TAXONOMY_INT_FIELDS),
    (DisplaySubtype, TAXONOMY_DIRECT_FIELDS, _TAXONOMY_INT_FIELDS),
    (Cabinet, TAXONOMY_DIRECT_FIELDS, _TAXONOMY_INT_FIELDS),
    (GameFormat, TAXONOMY_DIRECT_FIELDS, _TAXONOMY_INT_FIELDS),
    (GameplayFeature, TAXONOMY_DIRECT_FIELDS, _TAXONOMY_INT_FIELDS),
    (Tag, TAXONOMY_DIRECT_FIELDS, _TAXONOMY_INT_FIELDS),
    (Franchise, FRANCHISE_DIRECT_FIELDS, None),
]


def _resolve_all_taxonomy() -> None:
    """Resolve claims for all taxonomy models."""
    for model_class, direct_fields, int_fields in TAXONOMY_MODELS:
        for obj in model_class.objects.all():
            _resolve_simple(obj, direct_fields, int_fields=int_fields)
            obj.save()


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


# ------------------------------------------------------------------
# Relationship claim resolution (credits, themes)
# ------------------------------------------------------------------


def _pick_relationship_winners(
    obj,
    field_name: str,
) -> dict[str, Claim]:
    """Fetch active relationship claims and pick winner per claim_key.

    Returns {claim_key: winning_claim}.
    """
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


def resolve_credits(machine_model: MachineModel) -> None:
    """Resolve credit claims into DesignCredit rows for a single machine.

    Picks the winning claim per claim_key. Where ``value["exists"]`` is
    True, looks up the Person by slug and materializes a DesignCredit.
    """
    winners = _pick_relationship_winners(machine_model, "credit")

    # Desired credits from winning claims.
    desired: set[tuple[int, str]] = set()  # (person_id, role)
    for claim in winners.values():
        val = claim.value
        if not val.get("exists", True):
            continue
        person = Person.objects.filter(slug=val["person_slug"]).first()
        if not person:
            logger.warning(
                "Unresolved person slug %r in credit claim for %s",
                val["person_slug"],
                machine_model.name,
            )
            continue
        desired.add((person.pk, val["role"]))

    # Existing credits.
    existing = set(machine_model.credits.values_list("person_id", "role"))

    # Diff and apply.
    to_create = desired - existing
    to_delete = existing - desired

    if to_delete:
        for person_id, role in to_delete:
            machine_model.credits.filter(person_id=person_id, role=role).delete()

    if to_create:
        DesignCredit.objects.bulk_create(
            [
                DesignCredit(model=machine_model, person_id=person_id, role=role)
                for person_id, role in to_create
            ]
        )


def resolve_themes(machine_model: MachineModel) -> None:
    """Resolve theme claims into the M2M for a single machine.

    Picks the winning claim per claim_key. Where ``value["exists"]`` is
    True, looks up the Theme by slug and sets the M2M.
    """
    winners = _pick_relationship_winners(machine_model, "theme")

    desired_pks: set[int] = set()
    for claim in winners.values():
        val = claim.value
        if not val.get("exists", True):
            continue
        theme = Theme.objects.filter(slug=val["theme_slug"]).first()
        if not theme:
            logger.warning(
                "Unresolved theme slug %r in theme claim for %s",
                val["theme_slug"],
                machine_model.name,
            )
            continue
        desired_pks.add(theme.pk)

    machine_model.themes.set(desired_pks)


def resolve_gameplay_features(machine_model: MachineModel) -> None:
    """Resolve gameplay feature claims into the M2M for a single machine.

    Picks the winning claim per claim_key. Where ``value["exists"]`` is
    True, looks up the GameplayFeature by slug and sets the M2M.
    """
    winners = _pick_relationship_winners(machine_model, "gameplay_feature")

    desired_pks: set[int] = set()
    for claim in winners.values():
        val = claim.value
        if not val.get("exists", True):
            continue
        feature = GameplayFeature.objects.filter(
            slug=val["gameplay_feature_slug"]
        ).first()
        if not feature:
            logger.warning(
                "Unresolved gameplay feature slug %r in claim for %s",
                val["gameplay_feature_slug"],
                machine_model.name,
            )
            continue
        desired_pks.add(feature.pk)

    machine_model.gameplay_features.set(desired_pks)


def resolve_tags(machine_model: MachineModel) -> None:
    """Resolve tag claims into the M2M for a single machine.

    Picks the winning claim per claim_key. Where ``value["exists"]`` is
    True, looks up the Tag by slug and sets the M2M.
    """
    winners = _pick_relationship_winners(machine_model, "tag")

    desired_pks: set[int] = set()
    for claim in winners.values():
        val = claim.value
        if not val.get("exists", True):
            continue
        tag = Tag.objects.filter(slug=val["tag_slug"]).first()
        if not tag:
            logger.warning(
                "Unresolved tag slug %r in tag claim for %s",
                val["tag_slug"],
                machine_model.name,
            )
            continue
        desired_pks.add(tag.pk)

    machine_model.tags.set(desired_pks)


# ------------------------------------------------------------------
# Bulk resolution for credits (used by resolve_all)
# ------------------------------------------------------------------


def _resolve_all_credits(all_models: list[MachineModel]) -> None:
    """Bulk-resolve credit claims into DesignCredit rows for all models."""
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(MachineModel)

    # Pre-fetch person slug→pk lookup.
    person_lookup: dict[str, int] = {}
    for slug, pk in Person.objects.values_list("slug", "pk"):
        person_lookup[slug] = pk

    # Pre-fetch all active credit claims with priority annotation.
    credit_claims = (
        Claim.objects.filter(is_active=True, content_type=ct, field_name="credit")
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

    # Pick winner per (object_id, claim_key).
    winners_by_model: dict[int, list[Claim]] = {}
    seen: set[tuple[int, str]] = set()
    for claim in credit_claims:
        key = (claim.object_id, claim.claim_key)
        if key not in seen:
            seen.add(key)
            winners_by_model.setdefault(claim.object_id, []).append(claim)

    # Desired credits from winning claims.
    desired_by_model: dict[int, set[tuple[int, str]]] = {}
    for model_id, claims_list in winners_by_model.items():
        desired: set[tuple[int, str]] = set()
        for claim in claims_list:
            val = claim.value
            if not val.get("exists", True):
                continue
            person_pk = person_lookup.get(val["person_slug"])
            if person_pk is None:
                logger.warning(
                    "Unresolved person slug %r in credit claim (model pk=%s)",
                    val["person_slug"],
                    model_id,
                )
                continue
            desired.add((person_pk, val["role"]))
        desired_by_model[model_id] = desired

    # Pre-fetch existing DesignCredit rows (model-linked only, not series credits).
    existing_by_model: dict[int, set[tuple[int, str]]] = {}
    for dc in DesignCredit.objects.filter(model_id__isnull=False).values_list(
        "model_id", "person_id", "role"
    ):
        existing_by_model.setdefault(dc[0], set()).add((dc[1], dc[2]))

    # Diff and apply.
    all_model_ids = {pm.pk for pm in all_models}
    to_create: list[DesignCredit] = []
    to_delete_pks: list[int] = []

    for model_id in all_model_ids:
        desired = desired_by_model.get(model_id, set())
        existing = existing_by_model.get(model_id, set())

        for person_id, role in desired - existing:
            to_create.append(
                DesignCredit(model_id=model_id, person_id=person_id, role=role)
            )

    # Build a lookup for deletions.
    for dc in DesignCredit.objects.filter(model_id__in=all_model_ids).values_list(
        "pk", "model_id", "person_id", "role"
    ):
        pk, model_id, person_id, role = dc
        desired = desired_by_model.get(model_id, set())
        if (person_id, role) not in desired:
            to_delete_pks.append(pk)

    if to_delete_pks:
        DesignCredit.objects.filter(pk__in=to_delete_pks).delete()
    if to_create:
        DesignCredit.objects.bulk_create(to_create, batch_size=2000)


def _resolve_all_themes(all_models: list[MachineModel]) -> None:
    """Bulk-resolve theme claims into M2M rows for all models.

    Follows the same pattern as ``_resolve_all_credits()``: queries the M2M
    through table directly, diffs desired vs existing for ALL model IDs
    (including those with empty desired sets to clear stale rows), then
    bulk-creates additions and bulk-deletes removals.
    """
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(MachineModel)

    # Pre-fetch theme slug→pk lookup.
    theme_lookup: dict[str, int] = dict(Theme.objects.values_list("slug", "pk"))

    # Pre-fetch all active theme claims with priority annotation.
    theme_claims = (
        Claim.objects.filter(is_active=True, content_type=ct, field_name="theme")
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

    # Pick winner per (object_id, claim_key).
    winners_by_model: dict[int, list[Claim]] = {}
    seen: set[tuple[int, str]] = set()
    for claim in theme_claims:
        key = (claim.object_id, claim.claim_key)
        if key not in seen:
            seen.add(key)
            winners_by_model.setdefault(claim.object_id, []).append(claim)

    # Desired themes from winning claims.
    desired_by_model: dict[int, set[int]] = {}
    for model_id, claims_list in winners_by_model.items():
        desired: set[int] = set()
        for claim in claims_list:
            val = claim.value
            if not val.get("exists", True):
                continue
            theme_pk = theme_lookup.get(val["theme_slug"])
            if theme_pk is None:
                logger.warning(
                    "Unresolved theme slug %r in theme claim (model pk=%s)",
                    val["theme_slug"],
                    model_id,
                )
                continue
            desired.add(theme_pk)
        desired_by_model[model_id] = desired

    # Pre-fetch existing M2M through-table rows.
    through = MachineModel.themes.through
    existing_by_model: dict[int, set[int]] = {}
    for row in through.objects.values_list("machinemodel_id", "theme_id"):
        existing_by_model.setdefault(row[0], set()).add(row[1])

    # Diff and apply for ALL models.
    all_model_ids = {pm.pk for pm in all_models}
    to_create = []
    to_delete_pks: list[int] = []

    for model_id in all_model_ids:
        desired = desired_by_model.get(model_id, set())
        existing = existing_by_model.get(model_id, set())

        for theme_pk in desired - existing:
            to_create.append(through(machinemodel_id=model_id, theme_id=theme_pk))

    # Build a lookup for deletions.
    for row in through.objects.filter(machinemodel_id__in=all_model_ids).values_list(
        "pk", "machinemodel_id", "theme_id"
    ):
        pk, model_id, theme_id = row
        desired = desired_by_model.get(model_id, set())
        if theme_id not in desired:
            to_delete_pks.append(pk)

    if to_delete_pks:
        through.objects.filter(pk__in=to_delete_pks).delete()
    if to_create:
        through.objects.bulk_create(to_create, batch_size=2000)


def _resolve_all_gameplay_features(all_models: list[MachineModel]) -> None:
    """Bulk-resolve gameplay feature claims into M2M rows for all models.

    Follows the same pattern as ``_resolve_all_themes()``.
    """
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(MachineModel)

    # Pre-fetch gameplay feature slug→pk lookup.
    feature_lookup: dict[str, int] = dict(
        GameplayFeature.objects.values_list("slug", "pk")
    )

    # Pre-fetch all active gameplay feature claims with priority annotation.
    feature_claims = (
        Claim.objects.filter(
            is_active=True, content_type=ct, field_name="gameplay_feature"
        )
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

    # Pick winner per (object_id, claim_key).
    winners_by_model: dict[int, list[Claim]] = {}
    seen: set[tuple[int, str]] = set()
    for claim in feature_claims:
        key = (claim.object_id, claim.claim_key)
        if key not in seen:
            seen.add(key)
            winners_by_model.setdefault(claim.object_id, []).append(claim)

    # Desired features from winning claims.
    desired_by_model: dict[int, set[int]] = {}
    for model_id, claims_list in winners_by_model.items():
        desired: set[int] = set()
        for claim in claims_list:
            val = claim.value
            if not val.get("exists", True):
                continue
            feature_pk = feature_lookup.get(val["gameplay_feature_slug"])
            if feature_pk is None:
                logger.warning(
                    "Unresolved gameplay feature slug %r in claim (model pk=%s)",
                    val["gameplay_feature_slug"],
                    model_id,
                )
                continue
            desired.add(feature_pk)
        desired_by_model[model_id] = desired

    # Pre-fetch existing M2M through-table rows.
    through = MachineModel.gameplay_features.through
    existing_by_model: dict[int, set[int]] = {}
    for row in through.objects.values_list("machinemodel_id", "gameplayfeature_id"):
        existing_by_model.setdefault(row[0], set()).add(row[1])

    # Diff and apply for ALL models.
    all_model_ids = {pm.pk for pm in all_models}
    to_create = []
    to_delete_pks: list[int] = []

    for model_id in all_model_ids:
        desired = desired_by_model.get(model_id, set())
        existing = existing_by_model.get(model_id, set())

        for feature_pk in desired - existing:
            to_create.append(
                through(machinemodel_id=model_id, gameplayfeature_id=feature_pk)
            )

    # Build a lookup for deletions.
    for row in through.objects.filter(machinemodel_id__in=all_model_ids).values_list(
        "pk", "machinemodel_id", "gameplayfeature_id"
    ):
        pk, model_id, feature_id = row
        desired = desired_by_model.get(model_id, set())
        if feature_id not in desired:
            to_delete_pks.append(pk)

    if to_delete_pks:
        through.objects.filter(pk__in=to_delete_pks).delete()
    if to_create:
        through.objects.bulk_create(to_create, batch_size=2000)


def _resolve_all_tags(all_models: list[MachineModel]) -> None:
    """Bulk-resolve tag claims into M2M rows for all models.

    Follows the same pattern as ``_resolve_all_themes()``.
    """
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(MachineModel)

    # Pre-fetch tag slug→pk lookup.
    tag_lookup: dict[str, int] = dict(Tag.objects.values_list("slug", "pk"))

    # Pre-fetch all active tag claims with priority annotation.
    tag_claims = (
        Claim.objects.filter(is_active=True, content_type=ct, field_name="tag")
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

    # Pick winner per (object_id, claim_key).
    winners_by_model: dict[int, list[Claim]] = {}
    seen: set[tuple[int, str]] = set()
    for claim in tag_claims:
        key = (claim.object_id, claim.claim_key)
        if key not in seen:
            seen.add(key)
            winners_by_model.setdefault(claim.object_id, []).append(claim)

    # Desired tags from winning claims.
    desired_by_model: dict[int, set[int]] = {}
    for model_id, claims_list in winners_by_model.items():
        desired: set[int] = set()
        for claim in claims_list:
            val = claim.value
            if not val.get("exists", True):
                continue
            tag_pk = tag_lookup.get(val["tag_slug"])
            if tag_pk is None:
                logger.warning(
                    "Unresolved tag slug %r in tag claim (model pk=%s)",
                    val["tag_slug"],
                    model_id,
                )
                continue
            desired.add(tag_pk)
        desired_by_model[model_id] = desired

    # Pre-fetch existing M2M through-table rows.
    through = MachineModel.tags.through
    existing_by_model: dict[int, set[int]] = {}
    for row in through.objects.values_list("machinemodel_id", "tag_id"):
        existing_by_model.setdefault(row[0], set()).add(row[1])

    # Diff and apply for ALL models.
    all_model_ids = {pm.pk for pm in all_models}
    to_create = []
    to_delete_pks: list[int] = []

    for model_id in all_model_ids:
        desired = desired_by_model.get(model_id, set())
        existing = existing_by_model.get(model_id, set())

        for tag_pk in desired - existing:
            to_create.append(through(machinemodel_id=model_id, tag_id=tag_pk))

    # Build a lookup for deletions.
    for row in through.objects.filter(machinemodel_id__in=all_model_ids).values_list(
        "pk", "machinemodel_id", "tag_id"
    ):
        pk, model_id, tag_id = row
        desired = desired_by_model.get(model_id, set())
        if tag_id not in desired:
            to_delete_pks.append(pk)

    if to_delete_pks:
        through.objects.filter(pk__in=to_delete_pks).delete()
    if to_create:
        through.objects.bulk_create(to_create, batch_size=2000)
