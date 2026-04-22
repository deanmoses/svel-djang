"""Shared base models and utilities used across all apps."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Self, TypeVar

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.db.models.functions import Now
from django.db.models.signals import post_delete
from django.utils.text import slugify

from .validators import validate_no_mojibake as _validate_no_mojibake


class TimeStampedModel(models.Model):
    """Abstract base adding created_at / updated_at timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AliasBase(TimeStampedModel):
    """Abstract base for alias lookup models.

    Alias values are stored and compared in lowercase (matching the
    UniqueConstraint(Lower("value")) that every subclass must define).
    Claims live on the *parent* object, not on the alias row itself.

    Subclasses must add:
    - A ForeignKey to the parent model (named after the parent, related_name="aliases")
    - A UniqueConstraint on Lower("value") with a table-specific name
    """

    value = models.CharField(max_length=200)

    class Meta(TimeStampedModel.Meta):
        abstract = True
        ordering = ["value"]

    def __str__(self) -> str:
        return self.value


def field_not_blank(field_name):
    """CHECK constraint: field != ''. Use in concrete model Meta.constraints."""
    return models.CheckConstraint(
        condition=~models.Q(**{field_name: ""}),
        name=f"%(app_label)s_%(class)s_{field_name}_not_blank",
    )


def nullable_id_not_empty(field_name):
    """CHECK constraint: nullable string ID is NULL or non-empty.

    Prevents '' on optional unique CharField IDs (opdb_id, wikidata_id),
    which would consume the unique slot while being semantically null.
    """
    return models.CheckConstraint(
        condition=models.Q(**{f"{field_name}__isnull": True})
        | ~models.Q(**{field_name: ""}),
        name=f"%(app_label)s_%(class)s_{field_name}_not_empty",
    )


class License(TimeStampedModel):
    """A content license (e.g., Creative Commons, GFDL, or a policy status).

    Used to track the licensing status of creative/expressive content
    (descriptions, images, logos). Factual fields (names, years, IDs)
    are not copyrightable and are never subject to licensing.
    """

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=50, unique=True, blank=True)
    spdx_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        help_text="Standard SPDX identifier (e.g., CC-BY-SA-4.0). Null for non-standard entries.",
    )
    short_name = models.CharField(max_length=50, unique=True)
    url = models.URLField(blank=True, help_text="Link to canonical license deed.")
    allows_display = models.BooleanField(
        default=False,
        help_text="Informational: does this license permit public display? Not used as a runtime gate.",
    )
    requires_attribution = models.BooleanField(default=False)
    restricts_commercial = models.BooleanField(default=False)
    allows_derivatives = models.BooleanField(default=True)
    requires_share_alike = models.BooleanField(default=False)
    permissiveness_rank = models.PositiveSmallIntegerField(
        default=0,
        help_text="Higher = more permissive. Used by the global display threshold.",
    )

    class Meta:
        ordering = ["-permissiveness_rank", "name"]
        constraints = [
            field_not_blank("name"),
            field_not_blank("short_name"),
        ]

    def __str__(self) -> str:
        return self.short_name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.short_name, "license")
        super().save(*args, **kwargs)


def unique_slug(obj, source: str, fallback: str = "item") -> str:
    """Generate a unique slug with counter disambiguation.

    Appends a counter suffix (-2, -3, …) until the slug is unique within
    the model's table.
    """
    base = slugify(source) or fallback
    slug = base
    counter = 2
    while type(obj).objects.filter(slug=slug).exclude(pk=obj.pk).exists():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


class SluggedModel(models.Model):
    """Abstract base for catalog entities that have a unique, non-empty slug.

    Provides the slug field. Models needing max_length > 200 redeclare it.
    Each concrete subclass must add the CHECK constraint to its own Meta
    because Django does not inherit abstract parent constraints when a
    concrete model defines its own ``class Meta``::

        class Meta:
            constraints = [slug_not_blank()]

    Use ``slug_not_blank()`` to generate the constraint.
    """

    slug = models.SlugField(max_length=200, unique=True)

    class Meta:
        abstract = True


def slug_not_blank():
    """CHECK constraint: slug != ''. Use in each SluggedModel subclass Meta."""
    return models.CheckConstraint(
        condition=~models.Q(slug=""),
        name="%(app_label)s_%(class)s_slug_not_blank",
    )


# ---------------------------------------------------------------------------
# Entity status (claim-controlled lifecycle)
# ---------------------------------------------------------------------------


class EntityStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    DELETED = "deleted", "Deleted"


_CatalogModel = TypeVar("_CatalogModel", bound="EntityStatusMixin")


class CatalogQuerySet(models.QuerySet[_CatalogModel]):
    def active(self) -> CatalogQuerySet[_CatalogModel]:
        """Return entities considered live in the catalog.

        Includes ``status='active'`` and ``status IS NULL`` (transitional:
        entities from ingest commands not yet converted to plan/apply don't
        emit status claims).  Tighten to ``status='active'`` only after all
        adapters are converted (Phase 5).
        """
        return self.filter(
            models.Q(status=EntityStatus.ACTIVE) | models.Q(status__isnull=True)
        )


# `Manager.from_queryset` is a runtime factory that returns an untyped class,
# so basedpyright cannot see the queryset methods (e.g. `.active()`) that it
# copies onto the manager. The TYPE_CHECKING shim below declares the manager
# as a generic subclass of both Manager and the queryset, so `.active()` is
# visible *and* the per-subclass type binding (`Manufacturer.objects` →
# `CatalogManager[Manufacturer]`) carries through via django-types' descriptor.
if TYPE_CHECKING:

    class CatalogManager(
        models.Manager[_CatalogModel],
        CatalogQuerySet[_CatalogModel],
    ):
        pass
else:
    CatalogManager = models.Manager.from_queryset(CatalogQuerySet)


def active_status_q(relation: str) -> models.Q:
    """``Q`` filter for active-status entities reached through *relation*.

    Use inside ``Count(filter=...)`` and similar annotations where the
    queryset ``.active()`` method is not available::

        Count("machine_models", filter=Q(...) & active_status_q("machine_models"))

    Null-inclusive for transitional compatibility — tighten alongside
    ``CatalogQuerySet.active()`` after Phase 5.
    """
    return models.Q(**{f"{relation}__status": EntityStatus.ACTIVE}) | models.Q(
        **{f"{relation}__status__isnull": True}
    )


class EntityStatusMixin(models.Model):
    """Abstract mixin adding claim-controlled entity lifecycle status.

    Add to all independent catalog entity models (not aliases, through
    models, or abbreviations).  Each concrete subclass must also add
    ``status_valid()`` to its ``Meta.constraints``.
    """

    status = models.CharField(
        max_length=10,
        choices=EntityStatus.choices,
        null=True,
        blank=True,
    )

    # `ClassVar[CatalogManager[Self]]` gets us both halves: the custom manager
    # type (so `.active()` is visible) and per-subclass model binding (so
    # `Manufacturer.objects` types as `CatalogManager[Manufacturer]`, not
    # `CatalogManager[EntityStatusMixin]`). Without `Self`, django-types'
    # default descriptor strips the custom manager class.
    objects: ClassVar[CatalogManager[Self]] = CatalogManager()

    class Meta:
        abstract = True


def status_valid():
    """CHECK constraint: status must be 'active', 'deleted', or null."""
    return models.CheckConstraint(
        condition=(
            models.Q(status__in=[EntityStatus.ACTIVE, EntityStatus.DELETED])
            | models.Q(status__isnull=True)
        ),
        name="%(app_label)s_%(class)s_status_valid",
    )


# ---------------------------------------------------------------------------
# Markdown field
# ---------------------------------------------------------------------------


class MarkdownField(models.TextField):
    """A TextField containing markdown with ``[[entity:slug]]`` links.

    The system introspects models for MarkdownField instances to:
    - Auto-discover which fields need reference syncing
    - Auto-generate ``{field}_html`` rendered output in API responses

    Includes ``validate_no_mojibake`` as a default validator to reject
    encoding-corrupted text at the model level.
    """

    default_validators = [_validate_no_mojibake]

    def deconstruct(self):
        name, _path, args, kwargs = super().deconstruct()
        return name, "django.db.models.TextField", args, kwargs


def get_markdown_fields(model: type[models.Model]) -> list[str]:
    """Return field names of all MarkdownField instances on a model."""
    return [f.name for f in model._meta.get_fields() if isinstance(f, MarkdownField)]


# Infrastructure fields exempt from claims on every model.
_CLAIMS_EXEMPT_NAMES = frozenset(
    {"id", "uuid", "created_at", "updated_at", "extra_data"}
)


def get_claim_fields(model_class: type[models.Model]) -> dict[str, str]:
    """Discover claim-controlled fields by introspecting a Django model.

    Returns ``{field_name: field_name}`` for every concrete field that is
    claim-controlled.  Fields are excluded if they are:

    * primary keys
    * in ``_CLAIMS_EXEMPT_NAMES`` (infrastructure fields)
    * listed in the model's ``claims_exempt`` class attribute
    * GenericForeignKey helper columns (``content_type``, ``object_id``)

    FK fields are included — the resolver handles slug lookup automatically.
    """
    per_model_exempt = getattr(model_class, "claims_exempt", frozenset())
    fields: dict[str, str] = {}
    for f in model_class._meta.get_fields():
        if not isinstance(f, models.Field):
            continue
        if not getattr(f, "concrete", False):
            continue
        if f.primary_key:
            continue
        if f.name in _CLAIMS_EXEMPT_NAMES:
            continue
        if f.name in per_model_exempt:
            continue
        # Skip GenericForeignKey helper columns (content_type_id, object_id).
        if f.name in ("content_type", "object_id"):
            continue
        fields[f.name] = f.name
    return fields


# ---------------------------------------------------------------------------
# LinkableModel mixin (link target registration)
# ---------------------------------------------------------------------------


class LinkableModel(models.Model):
    """Mixin marking a model as a publicly addressable entity with a canonical identifier.

    Subclasses must define:
    - name: CharField
    - slug: SlugField (unique)
    - entity_type: str — hyphenated canonical public identifier (e.g. 'corporate-entity')
    - entity_type_plural: str — hyphenated canonical plural form (e.g. 'corporate-entities')

    ``entity_type`` and ``entity_type_plural`` together are the linguistic
    identity of a kind of entity — the single source of truth consumed by
    ``get_linkable_model`` and ``export_catalog_meta``. All URL shapes and
    UI labels derive from them; they do not drive backend behavior beyond
    URL and UI consistency.

    Class attributes for link registration (all optional):
    - link_type_name: str — overrides the auto-derived type name
    - link_label: str — human-readable label for type picker
    - link_description: str — brief description
    - link_sort_order: int — display order in type picker (lower = higher)
    - link_autocomplete_search_fields: tuple[str, ...] — model fields to search
    - link_autocomplete_ordering: tuple[str, ...] — result ordering
    - link_autocomplete_select_related: tuple[str, ...] — eager loading

    ``link_url_pattern`` is derived from ``entity_type_plural`` at subclass
    creation time — do not declare it by hand.
    """

    entity_type: str  # required on concrete subclasses
    entity_type_plural: str  # required on concrete subclasses

    class Meta:
        abstract = True

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # __init_subclass__ fires before Django's ModelBase sets up ``_meta``,
        # so abstract/concrete cannot be determined via ``_meta.abstract`` here.
        # Instead, treat ``entity_type`` declaration as the concrete-class
        # marker: abstract intermediates (CatalogModel) must NOT declare
        # ``entity_type``; any subclass that does is treated as concrete and
        # must also declare ``entity_type_plural``. If a future abstract
        # intermediate needs ``entity_type`` set for some reason, this hook's
        # invariant will need revisiting.
        if "entity_type" not in cls.__dict__:
            # Abstract intermediate; nothing to validate or derive.
            return
        entity_type = cls.__dict__["entity_type"]
        if not isinstance(entity_type, str) or not entity_type:
            raise ImproperlyConfigured(
                f"{cls.__name__} inherits LinkableModel but declares "
                f"entity_type as something other than a non-empty string."
            )
        entity_type_plural = cls.__dict__.get("entity_type_plural")
        if not isinstance(entity_type_plural, str) or not entity_type_plural:
            raise ImproperlyConfigured(
                f"{cls.__name__} inherits LinkableModel but does not declare "
                f"entity_type_plural as a non-empty string."
            )
        # Derive link_url_pattern from entity_type_plural. This hook fires
        # once at class creation, so entity_type_plural must be a class-body
        # literal; post-hoc assignment will not re-derive link_url_pattern.
        cls.link_url_pattern = f"/{entity_type_plural}/{{slug}}"
        # Collision detection happens lazily in get_linkable_model's map
        # builder, not here, to avoid depending on import order.


# ---------------------------------------------------------------------------
# CatalogModel abstract base — marker for catalog-specific code paths
# ---------------------------------------------------------------------------


class CatalogModel(LinkableModel):
    """Abstract marker for top-level catalog entities.

    Field-less subclass of ``LinkableModel`` that exists purely to identify
    catalog-specific code paths (e.g. ``ingest_pinbase``, soft-delete wire
    format) that must not widen to other ``LinkableModel`` subclasses.

    All fields and validation now live on ``LinkableModel``.
    """

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# MediaSupported mixin (media attachment target registration)
# ---------------------------------------------------------------------------


class MediaSupported(models.Model):
    """Mixin marking a model as a valid target for media attachments.

    Any model that inherits this mixin can have EntityMedia rows pointing
    at it via GenericFK. EntityMedia.clean() rejects content types that
    are not MediaSupported.

    Subclasses should set ``MEDIA_CATEGORIES`` to the list of allowed
    category strings for that entity type (e.g. ``["backglass", "playfield"]``).
    An empty list means the entity supports media but has no category vocabulary.
    """

    MEDIA_CATEGORIES: ClassVar[list[str]] = []

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Generic link tracking
# ---------------------------------------------------------------------------


class RecordReference(models.Model):
    """Tracks links between records for 'what links here' queries.

    Uses Django's contenttypes framework for polymorphic source/target.
    GenericForeignKey doesn't support on_delete, so all target deletions
    are allowed. Broken links render as 'broken link' text.
    """

    # Source (the record containing the link)
    source_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="+"
    )
    source_id = models.PositiveBigIntegerField()
    source = GenericForeignKey("source_type", "source_id")

    # Target (the record being linked to)
    target_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="+"
    )
    target_id = models.PositiveBigIntegerField()
    target = GenericForeignKey("target_type", "target_id")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source_type", "source_id", "target_type", "target_id"],
                name="core_recordreference_unique_source_target",
            ),
        ]
        indexes = [
            models.Index(fields=["target_type", "target_id"]),  # "What links here"
            models.Index(fields=["source_type", "source_id"]),  # Cleanup on delete
        ]

    def __str__(self):
        return (
            f"{self.source_type.model}:{self.source_id}"
            f" \u2192 {self.target_type.model}:{self.target_id}"
        )


def register_reference_cleanup(*model_classes: type[models.Model]) -> None:
    """Connect post_delete signals to clean up RecordReference rows for the given models.

    Call from AppConfig.ready() for every model whose text fields can contain
    ``[[type:ref]]`` markdown links (i.e. any model passed to ``sync_references``).
    """

    def _cleanup_references(sender, instance, **kwargs):
        ct = ContentType.objects.get_for_model(sender)
        RecordReference.objects.filter(source_type=ct, source_id=instance.pk).delete()

    for model_class in model_classes:
        post_delete.connect(
            _cleanup_references,
            sender=model_class,
            dispatch_uid=f"cleanup_refs_{model_class._meta.label_lower}",
        )
