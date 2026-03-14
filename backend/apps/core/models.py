"""Shared base models and utilities used across all apps."""

from __future__ import annotations

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models.signals import post_delete


class TimeStampedModel(models.Model):
    """Abstract base adding created_at / updated_at timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def unique_slug(obj, source: str, fallback: str = "item") -> str:
    """Generate a unique slug with counter disambiguation.

    Appends a counter suffix (-2, -3, …) until the slug is unique within
    the model's table.
    """
    from django.utils.text import slugify

    base = slugify(source) or fallback
    slug = base
    counter = 2
    while type(obj).objects.filter(slug=slug).exclude(pk=obj.pk).exists():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


# ---------------------------------------------------------------------------
# Markdown field
# ---------------------------------------------------------------------------


class MarkdownField(models.TextField):
    """A TextField containing markdown with ``[[entity:slug]]`` links.

    The system introspects models for MarkdownField instances to:
    - Auto-discover which fields need reference syncing
    - Auto-generate ``{field}_html`` rendered output in API responses
    """

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        return name, "django.db.models.TextField", args, kwargs


def get_markdown_fields(model: type[models.Model]) -> list[str]:
    """Return field names of all MarkdownField instances on a model."""
    return [f.name for f in model._meta.get_fields() if isinstance(f, MarkdownField)]


# ---------------------------------------------------------------------------
# Linkable mixin (link target registration)
# ---------------------------------------------------------------------------


class Linkable(models.Model):
    """Mixin marking a model as a markdown link target.

    Subclasses must define:
    - name: CharField
    - slug: SlugField (unique)

    Class attributes for link registration (all optional):
    - link_type_name: str — overrides the auto-derived type name
    - link_label: str — human-readable label for type picker
    - link_description: str — brief description
    - link_url_pattern: str — URL pattern like "/manufacturers/{slug}"
    - link_sort_order: int — display order in type picker
    """

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
        unique_together = [["source_type", "source_id", "target_type", "target_id"]]
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
