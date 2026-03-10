"""Resolution logic for non-MachineModel entities.

Includes the generic _resolve_single() and _resolve_bulk() helpers,
entity-specific field maps, and public resolve_*() functions for
Manufacturer, Person, Theme, CorporateEntity, System, and Title.
Also handles taxonomy model resolution.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import models
from django.db.models import Case, F, IntegerField, Value, When
from django.utils import timezone

from apps.provenance.models import Claim

from ..models import (
    Cabinet,
    CorporateEntity,
    DisplaySubtype,
    DisplayType,
    Franchise,
    GameFormat,
    GameplayFeature,
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


# ------------------------------------------------------------------
# Entity field maps
# ------------------------------------------------------------------

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

TITLE_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "description": "description",
}

THEME_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "description": "description",
}

CORPORATE_ENTITY_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "years_active": "years_active",
}

SYSTEM_DIRECT_FIELDS: dict[str, str] = {
    "name": "name",
    "description": "description",
}

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


# ------------------------------------------------------------------
# Generic single-object resolver
# ------------------------------------------------------------------


def _resolve_single(
    obj,
    direct_fields: dict[str, str],
    int_fields: frozenset[str] | None = None,
) -> None:
    """Resolve active claims onto a single object with only direct fields.

    This is the single-object counterpart to ``_resolve_bulk()``.

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


# ------------------------------------------------------------------
# Generic bulk resolver
# ------------------------------------------------------------------


def _resolve_bulk(
    model_class,
    direct_fields: dict[str, str],
    int_fields: frozenset[str] | None = None,
    fk_handlers: dict[str, tuple[str, dict]] | None = None,
    object_ids: set[int] | None = None,
) -> int:
    """Bulk-resolve claims for all (or selected) instances of a model class.

    Pre-fetches all active claims in one query, resolves in memory, then
    writes back with a single bulk_update(). This is the bulk counterpart
    to _resolve_single().

    Parameters:
        model_class: The Django model class to resolve.
        direct_fields: Maps claim field_name to model attribute name.
        int_fields: Claim field names whose values should be coerced to int.
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
    claims_qs = (
        Claim.objects.filter(content_type=ct, is_active=True)
        .select_related("source", "user__profile")
        .annotate(
            effective_priority=Case(
                When(source__isnull=False, then=F("source__priority")),
                When(user__isnull=False, then=F("user__profile__priority")),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("object_id", "field_name", "-effective_priority", "-created_at")
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
    field_defaults: dict[str, Any] = {}
    for attr in direct_fields.values():
        field = model_class._meta.get_field(attr)
        if hasattr(field, "default") and field.default is not models.NOT_PROVIDED:
            field_defaults[attr] = (
                field.default() if callable(field.default) else field.default
            )
        elif field.null:
            field_defaults[attr] = None
        else:
            field_defaults[attr] = ""

    # Collect FK attribute names for bulk_update.
    fk_update_fields: list[str] = []
    if fk_handlers:
        for fk_field, _lookup in fk_handlers.values():
            fk_update_fields.append(f"{fk_field}_id")

    # 4. Resolve each object in memory.
    now = timezone.now()
    for obj in all_objs:
        winners = claims_by_obj.get(obj.pk, {})

        # Reset direct fields.
        for attr, default in field_defaults.items():
            setattr(obj, attr, default)

        # Reset FK fields.
        if fk_handlers:
            for fk_field, _lookup in fk_handlers.values():
                setattr(obj, fk_field, None)

        # Apply winners.
        for field_name, claim in winners.items():
            if field_name in direct_fields:
                attr = direct_fields[field_name]
                value = claim.value
                if int_fields and field_name in int_fields:
                    if value is None:
                        setattr(obj, attr, None)
                    else:
                        try:
                            setattr(obj, attr, int(value))
                        except ValueError, TypeError:
                            logger.warning(
                                "Cannot coerce %r to int for %s.%s",
                                value,
                                model_class.__name__,
                                field_name,
                            )
                else:
                    setattr(obj, attr, "" if value is None else value)
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

        obj.updated_at = now

    # 5. Bulk write.
    update_fields = (
        list(set(direct_fields.values())) + fk_update_fields + ["updated_at"]
    )
    model_class.objects.bulk_update(all_objs, update_fields, batch_size=100)

    return len(all_objs)


# ------------------------------------------------------------------
# Public entity resolvers
# ------------------------------------------------------------------


def resolve_manufacturer(mfr: Manufacturer) -> Manufacturer:
    """Resolve active claims into the given Manufacturer's fields.

    Returns the saved Manufacturer.
    """
    _resolve_single(
        mfr, MANUFACTURER_DIRECT_FIELDS, int_fields=_MANUFACTURER_INT_FIELDS
    )
    mfr.save()
    return mfr


def resolve_person(person: Person) -> Person:
    """Resolve active claims into the given Person's fields.

    Returns the saved Person.
    """
    _resolve_single(person, PERSON_DIRECT_FIELDS, int_fields=_PERSON_INT_FIELDS)
    person.save()
    return person


def resolve_theme(theme: Theme) -> Theme:
    """Resolve active claims into the given Theme's fields.

    Returns the saved Theme.
    """
    _resolve_single(theme, THEME_DIRECT_FIELDS)
    theme.save()
    return theme


def resolve_corporate_entity(entity: CorporateEntity) -> CorporateEntity:
    """Resolve active claims into the given CorporateEntity's fields.

    Returns the saved CorporateEntity.
    """
    _resolve_single(entity, CORPORATE_ENTITY_DIRECT_FIELDS)
    entity.save()
    return entity


def resolve_system(system: System) -> System:
    """Resolve active claims into the given System's fields.

    Returns the saved System.
    """
    _resolve_single(system, SYSTEM_DIRECT_FIELDS)
    system.save()
    return system


def resolve_title(title: Title) -> Title:
    """Resolve active claims into the given Title's fields.

    Returns the saved Title.
    """
    _resolve_single(title, TITLE_DIRECT_FIELDS)
    # Handle franchise FK.
    franchise_claim = (
        title.claims.filter(field_name="franchise", is_active=True)
        .select_related("source", "user__profile")
        .annotate(
            effective_priority=Case(
                When(source__isnull=False, then=F("source__priority")),
                When(user__isnull=False, then=F("user__profile__priority")),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("-effective_priority", "-created_at")
        .first()
    )
    if franchise_claim:
        slug = str(franchise_claim.value).strip()
        title.franchise = Franchise.objects.filter(slug=slug).first()
        if not title.franchise:
            logger.warning("Unmatched franchise claim slug: %r", franchise_claim.value)
    else:
        title.franchise = None
    title.save()

    # Resolve relationship claims after scalar save.
    from ._relationships import resolve_title_abbreviations

    resolve_title_abbreviations(title)
    return title


# ------------------------------------------------------------------
# Taxonomy resolution
# ------------------------------------------------------------------


def _resolve_all_taxonomy() -> None:
    """Resolve claims for all taxonomy models."""
    for model_class, direct_fields, int_fields in TAXONOMY_MODELS:
        _resolve_bulk(model_class, direct_fields, int_fields=int_fields)
