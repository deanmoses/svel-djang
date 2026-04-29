"""Shared base models and utilities used across all apps."""

from __future__ import annotations

from typing import Any, ClassVar, TypeVar

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.db.models.functions import Lower, Now
from django.db.models.signals import post_delete
from django.utils.text import slugify

from .validators import validate_no_mojibake as _validate_no_mojibake


class TimeStampedModel(models.Model):
    """Abstract base adding created_at / updated_at timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def field_not_blank(field_name: str) -> models.CheckConstraint:
    """CHECK constraint: field != ''. Use in concrete model Meta.constraints."""
    return models.CheckConstraint(
        condition=~models.Q(**{field_name: ""}),
        name=f"%(app_label)s_%(class)s_{field_name}_not_blank",
    )


def field_lowercase(field_name: str) -> models.CheckConstraint:
    """CHECK constraint: field contains no ASCII uppercase letters.

    The regex matches ``[A-Z]`` only — non-ASCII uppercase (Ñ, É, …)
    would slip through. Acceptable for our current callers because the
    upstream slug validator (``SLUG_RE``) already restricts input to
    ``[a-z0-9-]``, and ``location_path`` is built from slugs.

    Generic helper for any field that must be lowercase by shape (slugs,
    derived path strings like Location.location_path, etc.). For slug
    fields on SluggedModel subclasses use ``slug_lowercase()`` instead —
    the constraint is identical, the helper just hardcodes the field name.

    Once values are guaranteed lowercase, plain ``unique=True`` already
    collapses case-equal rows; no Lower()-wrapped UniqueConstraint needed.
    Pair with ``unique_ci()`` only when the field is mixed-case (names),
    not when it's lowercase-shape (slugs, paths).
    """
    return models.CheckConstraint(
        condition=~models.Q(**{f"{field_name}__regex": r"[A-Z]"}),
        name=f"%(app_label)s_%(class)s_{field_name}_lowercase",
    )


def unique_ci(field_name: str) -> models.UniqueConstraint:
    """Case-insensitive UniqueConstraint on a single field.

    System-wide rule: name-like uniqueness collapses case. Use in Meta
    constraints in place of ``unique=True`` so ``"Bally"`` and ``"BALLY"``
    cannot both exist.
    """
    return models.UniqueConstraint(
        Lower(field_name),
        name=f"%(app_label)s_%(class)s_unique_{field_name}_ci",
    )


def meta_unique_fields(model_class: type[models.Model]) -> set[str]:
    """Names of fields referenced by any Meta ``UniqueConstraint``.

    Covers both ``fields=[...]`` and expression-based forms like
    ``UniqueConstraint(Lower("name"))`` — both make the underlying field
    behave as unique even though ``field.unique`` is False. Walks
    expression trees and picks up ``F`` references; other expression
    nodes are ignored.
    """
    names: set[str] = set()

    def _collect(expr: object) -> None:
        if isinstance(expr, models.F):
            names.add(expr.name)  # type: ignore[attr-defined]  # django-stubs omits F.name
        children = getattr(expr, "get_source_expressions", None)
        if callable(children):
            for child in children():
                _collect(child)

    for constraint in model_class._meta.constraints:
        if not isinstance(constraint, models.UniqueConstraint):
            continue
        for fname in constraint.fields or ():
            names.add(fname)
        for expr in constraint.expressions or ():
            _collect(expr)
    return names


def nullable_id_not_empty(field_name: str) -> models.CheckConstraint:
    """CHECK constraint: nullable string ID is NULL or non-empty.

    Prevents '' on optional unique CharField IDs (opdb_id, wikidata_id),
    which would consume the unique slot while being semantically null.
    """
    return models.CheckConstraint(
        condition=models.Q(**{f"{field_name}__isnull": True})
        | ~models.Q(**{field_name: ""}),
        name=f"%(app_label)s_%(class)s_{field_name}_not_empty",
    )


def unique_slug(obj: models.Model, source: str, fallback: str = "item") -> str:
    """Generate a unique slug with counter disambiguation.

    Appends a counter suffix (-2, -3, …) until the slug is unique within
    the model's table.
    """
    base = slugify(source) or fallback
    slug = base
    counter = 2
    manager = type(obj)._default_manager
    while manager.filter(slug=slug).exclude(pk=obj.pk).exists():
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
            constraints = [slug_not_blank(), slug_lowercase()]

    Use ``slug_not_blank()`` and ``slug_lowercase()`` to generate the
    constraints — system-wide rule is lowercase-only slugs.
    """

    slug = models.SlugField(max_length=200, unique=True)

    class Meta:
        abstract = True


def slug_not_blank() -> models.CheckConstraint:
    """CHECK constraint: slug != ''. Use in each SluggedModel subclass Meta."""
    return models.CheckConstraint(
        condition=~models.Q(slug=""),
        name="%(app_label)s_%(class)s_slug_not_blank",
    )


def slug_lowercase() -> models.CheckConstraint:
    """CHECK constraint: slug contains no uppercase letters.

    Slug-specific specialization of :func:`field_lowercase`. Use in each
    SluggedModel subclass Meta alongside ``slug_not_blank()``. Plain
    ``unique=True`` on the slug field is sufficient — case-sensitive
    uniqueness already collapses case-equal rows once values are
    guaranteed lowercase.
    """
    return models.CheckConstraint(
        condition=~models.Q(slug__regex=r"[A-Z]"),
        name="%(app_label)s_%(class)s_slug_lowercase",
    )


class License(SluggedModel, TimeStampedModel):
    """A content license (e.g., Creative Commons, GFDL, or a policy status).

    Used to track the licensing status of creative/expressive content
    (descriptions, images, logos). Factual fields (names, years, IDs)
    are not copyrightable and are never subject to licensing.
    """

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=50, unique=True)
    spdx_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        help_text="Standard SPDX identifier (e.g., CC-BY-SA-4.0). Null for non-standard entries.",
    )
    short_name = models.CharField(max_length=50)
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
            slug_not_blank(),
            slug_lowercase(),
            unique_ci("name"),
            unique_ci("short_name"),
        ]

    def __str__(self) -> str:
        return self.short_name

    def save(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401 - matches Model.save's overloaded signature
        if not self.slug:
            self.slug = unique_slug(self, self.short_name, "license")
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Entity status (claim-controlled lifecycle)
# ---------------------------------------------------------------------------


class EntityStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    DELETED = "deleted", "Deleted"


_LifecycleModel = TypeVar("_LifecycleModel", bound="LifecycleStatusModel")


class CatalogQuerySet(models.QuerySet[_LifecycleModel]):
    def active(self) -> CatalogQuerySet[_LifecycleModel]:
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


class LifecycleStatusModel(models.Model):
    """Abstract base adding claim-controlled entity lifecycle status.

    Add to all independent catalog entity models (not aliases, through
    models, or abbreviations).  Each concrete subclass must also add
    ``status_valid()`` to its ``Meta.constraints``.

    Today the only states are ``active`` and ``deleted`` (soft delete).
    Future lifecycle states (e.g. ``draft``, ``archived``) belong on the
    existing ``status`` field, not a parallel field — this class is the
    designated home for entity lifecycle.
    """

    status = models.CharField(
        max_length=10,
        choices=EntityStatus.choices,
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True


def status_valid() -> models.CheckConstraint:
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


class MarkdownField(models.TextField[str, str]):
    """A TextField containing markdown with ``[[<entity-type>:<public-id>]]`` links.

    The system introspects models for MarkdownField instances to:
    - Auto-discover which fields need reference syncing
    - Auto-generate ``{field}_html`` rendered output in API responses

    Includes ``validate_no_mojibake`` as a default validator to reject
    encoding-corrupted text at the model level.
    """

    default_validators = [_validate_no_mojibake]

    # Django's migration protocol; see Field.deconstruct.
    def deconstruct(self) -> Any:  # noqa: ANN401
        name, _path, args, kwargs = super().deconstruct()
        return name, "django.db.models.TextField", args, kwargs


def get_markdown_fields(model: type[models.Model]) -> list[str]:
    """Return field names of all MarkdownField instances on a model."""
    return [f.name for f in model._meta.get_fields() if isinstance(f, MarkdownField)]


# ---------------------------------------------------------------------------
# LinkableModel (link target registration)
# ---------------------------------------------------------------------------


class LinkableModel(models.Model):
    """Abstract base marking a model as a publicly addressable entity with a canonical identifier.

    Subclasses must define:
    - name: CharField
    - entity_type: str — hyphenated canonical public identifier (e.g. 'corporate-entity')
    - entity_type_plural: str — hyphenated canonical plural form (e.g. 'corporate-entities')

    Subclasses may override:
    - public_id_field: str — name of the field carrying URL identity. Defaults
      to ``"slug"``. Multi-segment models materialize the path into a
      ``unique=True`` field and point this at it (Location: ``"location_path"``).
    - public_id_form_field: str — name of the form input from which
      ``public_id_field`` is derived at create time. Defaults to
      ``public_id_field`` itself (the form input is the public id directly,
      as for every shipped model that uses ``"slug"``). Override on models
      whose public id is server-derived from another input — Location's
      ``location_path`` is built from the user's ``slug`` input plus the
      parent's path. Used by collision pre-checks to surface the error
      keyed under the form field the user can actually fix.

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

    entity_type: ClassVar[str]  # required on concrete subclasses
    entity_type_plural: ClassVar[str]  # required on concrete subclasses
    public_id_field: ClassVar[str] = "slug"
    # Empty default means "use ``public_id_field`` itself". Resolve with
    # ``cls.public_id_form_field or cls.public_id_field`` at the call site.
    public_id_form_field: ClassVar[str] = ""
    # ``name`` is declared per-concrete-subclass (different max_length /
    # validators per entity); the instance-level annotation lets
    # ``type[LinkableModel]`` introspection code read ``.name`` without
    # casting. Django field registration still happens on the concrete
    # subclasses (where ``= models.CharField(...)`` lives), so ``_meta`` is
    # unaffected — but django-stubs's plugin can't see a field here at the
    # abstract level, so ``_meta.get_field("name")`` on ``type[CatalogModel]``
    # needs ``# type: ignore[misc]`` at the one site that calls it.
    name: str
    link_url_pattern: ClassVar[str]

    class Meta:
        abstract = True

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # __init_subclass__ fires before Django's ModelBase sets up ``_meta``,
        # so abstract/concrete cannot be determined via ``_meta.abstract`` here.
        # Instead, treat ``entity_type`` declaration as the concrete-class
        # marker: abstract intermediates (e.g. ``CatalogModel``) must NOT declare
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
        # ``{public_id}`` resolves at format time to whichever field
        # ``public_id_field`` names — ``slug`` for most models,
        # ``location_path`` for Location, etc.
        cls.link_url_pattern = f"/{entity_type_plural}/{{public_id}}"
        # Collision detection and ``public_id_field`` resolution happen in
        # the system check (apps.core.checks), not here, to avoid depending
        # on Django's _meta being fully wired at __init_subclass__ time.

    def get_absolute_url(self) -> str:
        """Format ``link_url_pattern`` with this entity's ``public_id``."""
        return self.link_url_pattern.format(public_id=self.public_id)

    @property
    def public_id(self) -> str:
        """Return this entity's URL-identity value (``self.<public_id_field>``)."""
        value: str = getattr(self, self.public_id_field)
        return value


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

    def __str__(self) -> str:
        return (
            f"{self.source_type.model}:{self.source_id}"
            f" \u2192 {self.target_type.model}:{self.target_id}"
        )


def register_reference_cleanup(*model_classes: type[models.Model]) -> None:
    """Connect post_delete signals to clean up RecordReference rows for the given models.

    Call from AppConfig.ready() for every model whose text fields can contain
    ``[[<entity-type>:<public-id>]]`` markdown links (i.e. any model passed to ``sync_references``).
    """

    def _cleanup_references(
        sender: type[models.Model], instance: models.Model, **kwargs: object
    ) -> None:
        ct = ContentType.objects.get_for_model(sender)
        RecordReference.objects.filter(source_type=ct, source_id=instance.pk).delete()

    for model_class in model_classes:
        post_delete.connect(
            _cleanup_references,
            sender=model_class,
            dispatch_uid=f"cleanup_refs_{model_class._meta.label_lower}",
        )
