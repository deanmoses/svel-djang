"""Source models: data origin points and per-field license overrides."""

from __future__ import annotations

from typing import Any

from django.db import models

from apps.core.models import TimeStampedModel, field_not_blank, unique_slug


class Source(TimeStampedModel):
    """A data origin point (external database, book, editorial team, etc.)."""

    class SourceType(models.TextChoices):
        DATABASE = "database", "Database"
        WIKI = "wiki", "Wiki"
        BOOK = "book", "Book"
        EDITORIAL = "editorial", "Editorial"
        OTHER = "other", "Other"

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    source_type = models.CharField(
        max_length=20, choices=SourceType.choices, default=SourceType.DATABASE
    )
    priority = models.PositiveSmallIntegerField(
        default=0,
        help_text="Higher priority wins when claims conflict.",
    )
    url = models.URLField(blank=True)
    description = models.TextField(blank=True)
    is_enabled = models.BooleanField(
        default=True,
        help_text="Disabled sources are excluded from claim resolution.",
    )
    default_license = models.ForeignKey(
        "core.License",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sources",
        help_text="Default license for claims from this source.",
    )

    class Meta:
        ordering = ["-priority", "name"]
        constraints = [
            field_not_blank("name"),
            models.CheckConstraint(
                condition=models.Q(
                    source_type__in=[
                        "database",
                        "wiki",
                        "book",
                        "editorial",
                        "other",
                    ]
                ),
                name="provenance_source_source_type_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            self.slug = unique_slug(self, self.name, "source")
        super().save(*args, **kwargs)


class SourceFieldLicense(models.Model):
    """Per-field license override for a source.

    Wiki-style sources typically have different licenses for text vs images
    (e.g., Fandom: text is CC BY-SA 3.0, images are fair use / not reusable).
    This model captures that relationship without denormalizing to per-claim.
    """

    source_id: int

    source = models.ForeignKey(
        Source,
        on_delete=models.CASCADE,
        related_name="field_licenses",
    )
    field_name = models.CharField(max_length=255)
    license = models.ForeignKey(
        "core.License",
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "field_name"],
                name="provenance_sourcefieldlicense_unique_source_field",
            ),
            field_not_blank("field_name"),
        ]

    def __str__(self) -> str:
        return f"{self.source.name}: {self.field_name} → {self.license.short_name}"
