"""Shared base models and utilities used across all apps."""

from __future__ import annotations

from typing import ClassVar

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
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


class CatalogQuerySet(models.QuerySet):
    def active(self):
        """Return entities considered live in the catalog.

        Includes ``status='active'`` and ``status IS NULL`` (transitional:
        entities from ingest commands not yet converted to plan/apply don't
        emit status claims).  Tighten to ``status='active'`` only after all
        adapters are converted (Phase 5).
        """
        return self.filter(
            models.Q(status=EntityStatus.ACTIVE) | models.Q(status__isnull=True)
        )


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

    objects = CatalogManager()

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
        name, path, args, kwargs = super().deconstruct()
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
    """Mixin marking a model as a markdown link target.

    Subclasses must define:
    - name: CharField
    - slug: SlugField (unique)

    Class attributes for link registration (all optional):
    - link_type_name: str — overrides the auto-derived type name
    - link_label: str — human-readable label for type picker
    - link_description: str — brief description
    - link_url_pattern: str — URL pattern like "/manufacturers/{slug}"
    - link_sort_order: int — display order in type picker (lower = higher)
    - link_autocomplete_search_fields: tuple[str, ...] — model fields to search
    - link_autocomplete_ordering: tuple[str, ...] — result ordering
    - link_autocomplete_select_related: tuple[str, ...] — eager loading
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
