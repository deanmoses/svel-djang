"""Resolution logic for non-MachineModel entities.

Includes the generic _resolve_single() and _resolve_bulk() helpers,
entity-specific field maps, and public resolve_*() functions for
Manufacturer, Person, Theme, CorporateEntity, System, and Title.
Also handles taxonomy model resolution.
"""

from __future__ import annotations

import logging

from django.db.models import Case, F, IntegerField, Value, When
from django.utils import timezone

from apps.provenance.models import Claim

from ..models import (
    Cabinet,
    CorporateEntity,
    CreditRole,
    DisplaySubtype,
    DisplayType,
    Franchise,
    GameFormat,
    GameplayFeature,
    Manufacturer,
    Person,
    Series,
    System,
    Tag,
    TechnologyGeneration,
    TechnologySubgeneration,
    Theme,
    Title,
)
from ._helpers import _coerce, get_field_defaults

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
    (GameplayFeature, TAXONOMY_DIRECT_FIELDS),
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

    All resolvable fields are reset to their defaults first, then active
    claim winners are applied.  Claims are the sole source of truth for
    these fields: a field with no active claim will be blank/null after
    resolution regardless of what was previously stored.

    Mutates *obj* in memory; the caller is responsible for saving.
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
    field_defaults = get_field_defaults(type(obj), direct_fields)
    for attr, default in field_defaults.items():
        setattr(obj, attr, default)

    # Apply winners.
    has_extra_data = hasattr(obj, "extra_data")
    extra_data: dict = {} if has_extra_data else None
    for field_name, claim in winners.items():
        if field_name in direct_fields:
            attr = direct_fields[field_name]
            setattr(obj, attr, _coerce(type(obj), attr, claim.value))
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
    field_defaults = get_field_defaults(model_class, direct_fields)

    # Collect FK attribute names for bulk_update.
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

        # Reset direct fields.
        for attr, default in field_defaults.items():
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
# Public entity resolvers
# ------------------------------------------------------------------


def resolve_manufacturer(mfr: Manufacturer) -> Manufacturer:
    """Resolve active claims into the given Manufacturer's fields."""
    _resolve_single(mfr, MANUFACTURER_DIRECT_FIELDS)
    mfr.save()
    _sync_markdown_references(mfr)
    return mfr


def resolve_person(person: Person) -> Person:
    """Resolve active claims into the given Person's fields."""
    _resolve_single(person, PERSON_DIRECT_FIELDS)
    person.save()
    _sync_markdown_references(person)
    return person


def resolve_theme(theme: Theme) -> Theme:
    """Resolve active claims into the given Theme's fields."""
    _resolve_single(theme, THEME_DIRECT_FIELDS)
    theme.save()
    _sync_markdown_references(theme)
    return theme


def resolve_corporate_entity(entity: CorporateEntity) -> CorporateEntity:
    """Resolve active claims into the given CorporateEntity's fields."""
    _resolve_single(entity, CORPORATE_ENTITY_DIRECT_FIELDS)
    entity.save()
    return entity


def resolve_system(system: System) -> System:
    """Resolve active claims into the given System's fields."""
    _resolve_single(system, SYSTEM_DIRECT_FIELDS)
    system.save()
    _sync_markdown_references(system)
    return system


def resolve_title(title: Title) -> Title:
    """Resolve active claims into the given Title's fields."""
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
    _sync_markdown_references(title)

    # Resolve relationship claims after scalar save.
    from ._relationships import resolve_title_abbreviations

    resolve_title_abbreviations(title)
    return title


# ------------------------------------------------------------------
# Taxonomy resolution
# ------------------------------------------------------------------


def resolve_taxonomy(obj):
    """Resolve active claims into a single taxonomy model instance."""
    _resolve_single(obj, TAXONOMY_DIRECT_FIELDS)
    obj.save()
    _sync_markdown_references(obj)
    return obj


def resolve_franchise(franchise: Franchise) -> Franchise:
    """Resolve active claims into the given Franchise's fields."""
    _resolve_single(franchise, FRANCHISE_DIRECT_FIELDS)
    franchise.save()
    _sync_markdown_references(franchise)
    return franchise


def resolve_series(series: Series) -> Series:
    """Resolve active claims into the given Series's fields."""
    _resolve_single(series, SERIES_DIRECT_FIELDS)
    series.save()
    _sync_markdown_references(series)
    return series


def _resolve_all_taxonomy() -> None:
    """Resolve claims for all taxonomy models."""
    for model_class, direct_fields in TAXONOMY_MODELS:
        _resolve_bulk(model_class, direct_fields)
