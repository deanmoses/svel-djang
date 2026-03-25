"""Resolution logic for non-MachineModel entities.

Includes the generic _resolve_single() and _resolve_bulk() helpers,
entity-specific field maps, and public resolve_*() functions for
Manufacturer, Person, Theme, CorporateEntity, System, and Title.
Also handles taxonomy model resolution.
"""

from __future__ import annotations

import logging

from django.utils import timezone

from apps.provenance.models import Claim

from ..models import (
    Cabinet,
    CreditRole,
    DisplaySubtype,
    DisplayType,
    Franchise,
    GameFormat,
    GameplayFeature,
    RewardType,
    Series,
    System,
    Tag,
    TechnologyGeneration,
    TechnologySubgeneration,
    Theme,
    Title,
)
from ._helpers import (
    _annotate_priority,
    _coerce,
    _resolve_fk_generic,
    get_field_defaults,
)

logger = logging.getLogger(__name__)


def _sync_markdown_references(obj) -> None:
    """Sync RecordReference table for all markdown fields on the object.

    Always calls sync_references, even for empty fields, so that stale
    references are cleaned up when a field is blanked.
    """
    from apps.core.markdown_links import sync_references
    from apps.core.models import get_markdown_fields

    for field_name in get_markdown_fields(type(obj)):
        sync_references(obj, getattr(obj, field_name, "") or "")


# ------------------------------------------------------------------
# Entity field maps
# ------------------------------------------------------------------

MANUFACTURER_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "description": "description",
    "logo_url": "logo_url",
    "website": "website",
}

PERSON_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "description": "description",
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

TITLE_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "description": "description",
}

THEME_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "description": "description",
}

GAMEPLAY_FEATURE_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "description": "description",
}

REWARD_TYPE_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "display_order": "display_order",
    "description": "description",
}

CORPORATE_ENTITY_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "description": "description",
    "year_start": "year_start",
    "year_end": "year_end",
}

SYSTEM_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "description": "description",
}

# Taxonomy models: name, display_order, and description are claim-controlled.
TAXONOMY_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "display_order": "display_order",
    "description": "description",
}

# Franchise has no display_order.
FRANCHISE_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "description": "description",
}

SERIES_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "description": "description",
}

# All taxonomy models that go through claim resolution.
TAXONOMY_MODELS: list[tuple[type, dict[str, str]]] = [
    (TechnologyGeneration, TAXONOMY_DIRECT_FIELDS),
    (TechnologySubgeneration, TAXONOMY_DIRECT_FIELDS),
    (DisplayType, TAXONOMY_DIRECT_FIELDS),
    (DisplaySubtype, TAXONOMY_DIRECT_FIELDS),
    (Cabinet, TAXONOMY_DIRECT_FIELDS),
    (GameFormat, TAXONOMY_DIRECT_FIELDS),
    (RewardType, REWARD_TYPE_DIRECT_FIELDS),
    (Tag, TAXONOMY_DIRECT_FIELDS),
    (CreditRole, TAXONOMY_DIRECT_FIELDS),
    (Franchise, FRANCHISE_DIRECT_FIELDS),
    (Series, SERIES_DIRECT_FIELDS),
    (System, SYSTEM_DIRECT_FIELDS),
]


# ------------------------------------------------------------------
# Generic single-object resolver
# ------------------------------------------------------------------


def _resolve_single(
    obj,
    direct_fields: dict[str, str],
) -> None:
    """Resolve active claims onto a single object with only direct fields.

    This is the single-object counterpart to ``_resolve_bulk()``.

    Resolvable fields are reset to their defaults, then active claim
    winners are applied.  UNIQUE fields are preserved when no claim
    exists (resetting them to a shared default like ``""`` would cause
    integrity errors in the bulk path and semantic inconsistency in the
    single path).  Non-unique fields with no active claim are
    blank/null after resolution.

    Mutates *obj* in memory; the caller is responsible for saving.
    """
    claims = _annotate_priority(obj.claims.all()).order_by(
        "field_name", "-effective_priority", "-created_at"
    )

    winners: dict[str, Claim] = {}
    for claim in claims:
        if claim.field_name not in winners:
            winners[claim.field_name] = claim

    # Reset resolvable fields to defaults.  UNIQUE fields are preserved
    # when no winning claim exists — see _resolve_bulk() for rationale.
    field_defaults = get_field_defaults(type(obj), direct_fields)
    unique_attrs: set[str] = set()
    for attr in direct_fields.values():
        if type(obj)._meta.get_field(attr).unique:
            unique_attrs.add(attr)
    winner_attrs = {direct_fields[fn] for fn in winners if fn in direct_fields}
    for attr, default in field_defaults.items():
        if attr in unique_attrs and attr not in winner_attrs:
            continue
        setattr(obj, attr, default)

    # Apply winners.
    model_class = type(obj)
    has_extra_data = hasattr(obj, "extra_data")
    extra_data: dict = {} if has_extra_data else None
    for field_name, claim in winners.items():
        if field_name in direct_fields:
            attr = direct_fields[field_name]
            field = model_class._meta.get_field(attr)
            if field.is_relation:
                setattr(
                    obj,
                    attr,
                    _resolve_fk_generic(
                        model_class,
                        attr,
                        claim.value,
                    ),
                )
            else:
                setattr(obj, attr, _coerce(model_class, attr, claim.value))
        elif has_extra_data:
            extra_data[field_name] = claim.value
    if has_extra_data:
        obj.extra_data = extra_data


# ------------------------------------------------------------------
# Generic bulk resolver
# ------------------------------------------------------------------


def _resolve_bulk(
    model_class,
    direct_fields: dict[str, str],
    fk_handlers: dict[str, tuple[str, dict]] | None = None,
    object_ids: set[int] | None = None,
) -> int:
    """Bulk-resolve claims for all (or selected) instances of a model class.

    Pre-fetches all active claims in one query, resolves in memory, then
    writes back with a single bulk_update(). This is the bulk counterpart
    to _resolve_single().

    UNIQUE fields are preserved when no winning claim exists — resetting
    them to a shared default (e.g. ``""``) would cause IntegrityError
    when multiple objects lack claims for that field.

    Parameters:
        model_class: The Django model class to resolve.
        direct_fields: Maps claim field_name to model attribute name.
        fk_handlers: Maps claim field_name to (fk_field_name, slug_lookup_dict).
            For each matching claim, resolves value via the lookup dict and
            sets the FK attribute. The lookup dict maps slug to model instance.
        object_ids: If provided, only resolve these object IDs. If None,
            resolve all instances.

    Returns the number of objects updated.
    """
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(model_class)

    # 1. Pre-fetch all active claims for this model class.
    claims_qs = _annotate_priority(Claim.objects.filter(content_type=ct)).order_by(
        "object_id", "field_name", "-effective_priority", "-created_at"
    )
    if object_ids is not None:
        claims_qs = claims_qs.filter(object_id__in=object_ids)

    # Group by object_id, pick winner per field_name.
    claims_by_obj: dict[int, dict[str, Claim]] = {}
    for claim in claims_qs:
        obj_winners = claims_by_obj.setdefault(claim.object_id, {})
        if claim.field_name not in obj_winners:
            obj_winners[claim.field_name] = claim

    # 2. Load objects.
    objs_qs = model_class.objects.all()
    if object_ids is not None:
        objs_qs = objs_qs.filter(pk__in=object_ids)
    all_objs = list(objs_qs)

    if not all_objs:
        return 0

    # 3. Compute field defaults once.
    field_defaults = get_field_defaults(model_class, direct_fields)

    # Identify UNIQUE direct fields — these must NOT be reset to their
    # default when no claim exists, or bulk_update will crash with a
    # UNIQUE constraint violation when multiple objects share the default.
    unique_attrs: set[str] = set()
    # Identify FK fields in direct_fields and pre-build lookups.
    fk_fields: set[str] = set()
    fk_lookups: dict[str, dict[str, object]] = {}
    fk_lookups_map = getattr(model_class, "claim_fk_lookups", {})
    for claim_field, attr in direct_fields.items():
        field = model_class._meta.get_field(attr)
        if field.unique:
            unique_attrs.add(attr)
        if field.is_relation:
            fk_fields.add(attr)
            lookup_key = fk_lookups_map.get(attr, "slug")
            target_model = field.related_model
            fk_lookups[attr] = {
                getattr(obj, lookup_key): obj for obj in target_model.objects.all()
            }

    # Collect FK attribute names for bulk_update (legacy fk_handlers).
    fk_update_fields: list[str] = []
    if fk_handlers:
        for fk_field, _lookup in fk_handlers.values():
            fk_update_fields.append(f"{fk_field}_id")

    # Check if model has extra_data field for unmatched claims.
    has_extra_data = hasattr(model_class, "extra_data")

    # 4. Resolve each object in memory.
    now = timezone.now()
    for obj in all_objs:
        winners = claims_by_obj.get(obj.pk, {})

        # Reset direct fields (skip UNIQUE fields — they keep their
        # existing value unless a winning claim explicitly sets them).
        winner_attrs = {direct_fields[fn] for fn in winners if fn in direct_fields}
        for attr, default in field_defaults.items():
            if attr in unique_attrs and attr not in winner_attrs:
                continue
            setattr(obj, attr, default)

        # Reset FK fields.
        if fk_handlers:
            for fk_field, _lookup in fk_handlers.values():
                setattr(obj, fk_field, None)

        # Apply winners.
        extra_data: dict = {} if has_extra_data else None
        for field_name, claim in winners.items():
            if field_name in direct_fields:
                attr = direct_fields[field_name]
                if attr in fk_fields:
                    setattr(
                        obj,
                        attr,
                        _resolve_fk_generic(
                            model_class,
                            attr,
                            claim.value,
                            lookup=fk_lookups.get(attr),
                        ),
                    )
                else:
                    setattr(obj, attr, _coerce(model_class, attr, claim.value))
            elif fk_handlers and field_name in fk_handlers:
                fk_field, lookup = fk_handlers[field_name]
                slug = str(claim.value).strip() if claim.value else ""
                if slug:
                    resolved = lookup.get(slug)
                    if resolved:
                        setattr(obj, fk_field, resolved)
                    else:
                        logger.warning(
                            "Unmatched %s claim slug: %r",
                            field_name,
                            claim.value,
                        )
            elif has_extra_data:
                extra_data[field_name] = claim.value
        if has_extra_data:
            obj.extra_data = extra_data

        obj.updated_at = now

    # 5. Bulk write.
    update_fields = (
        list(set(direct_fields.values())) + fk_update_fields + ["updated_at"]
    )
    if has_extra_data:
        update_fields.append("extra_data")
    model_class.objects.bulk_update(all_objs, update_fields, batch_size=100)

    # Sync markdown backlinks (RecordReference) for bulk-resolved objects.
    from apps.core.models import get_markdown_fields

    if get_markdown_fields(model_class):
        for obj in all_objs:
            _sync_markdown_references(obj)

    return len(all_objs)


# ------------------------------------------------------------------
# Generic entity resolvers (model-driven)
# ------------------------------------------------------------------


def resolve_entity(obj):
    """Resolve all claim-controlled fields on any entity.

    Discovers claim-controlled fields by introspecting the model (via
    ``get_claim_fields``), resolves winners, applies them (including FK
    fields), saves, and syncs markdown references.
    """
    from apps.core.models import get_claim_fields

    fields = get_claim_fields(type(obj))
    _resolve_single(obj, fields)
    obj.save()
    _sync_markdown_references(obj)
    return obj


def resolve_all_entities(model_class, *, object_ids=None) -> int:
    """Bulk-resolve all claim-controlled fields for all instances of a model.

    Discovers claim-controlled fields by introspecting the model.
    """
    from apps.core.models import get_claim_fields

    fields = get_claim_fields(model_class)
    return _resolve_bulk(model_class, fields, object_ids=object_ids)


# ------------------------------------------------------------------
# Legacy entity resolvers (delegate to resolve_entity/resolve_all_entities)
#
# These thin wrappers preserve backward compatibility for existing callers
# (tests, ingest commands). New code should use resolve_entity() and
# resolve_all_entities() directly.
# ------------------------------------------------------------------


# fmt: off
def resolve_manufacturer(mfr):          return resolve_entity(mfr)  # noqa: E704
def resolve_person(person):             return resolve_entity(person)  # noqa: E704
def resolve_gameplay_feature(feature):  return resolve_entity(feature)  # noqa: E704
def resolve_theme(theme):               return resolve_entity(theme)  # noqa: E704
def resolve_corporate_entity(entity):   return resolve_entity(entity)  # noqa: E704
def resolve_system(system):             return resolve_entity(system)  # noqa: E704
def resolve_taxonomy(obj):              return resolve_entity(obj)  # noqa: E704
def resolve_franchise(franchise):       return resolve_entity(franchise)  # noqa: E704
def resolve_series(series):             return resolve_entity(series)  # noqa: E704
def resolve_all_gameplay_feature_entities(): return resolve_all_entities(GameplayFeature)  # noqa: E704
def resolve_all_theme_entities():       return resolve_all_entities(Theme)  # noqa: E704
# fmt: on


def resolve_title(title: Title) -> Title:
    """Resolve Title scalars."""
    return resolve_entity(title)


def _resolve_all_taxonomy() -> None:
    """Resolve claims for all taxonomy models (legacy)."""
    for model_class, _direct_fields in TAXONOMY_MODELS:
        resolve_all_entities(model_class)


def resolve_all_locations() -> int:
    """Bulk-resolve claims for all Location instances."""
    from ..models import Location

    return resolve_all_entities(Location)
