"""MachineModel and ModelAbbreviation models."""

from __future__ import annotations

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from apps.core.models import Linkable, TimeStampedModel, unique_slug

__all__ = ["MachineModel", "ModelAbbreviation"]


class MachineModel(Linkable, TimeStampedModel):
    """A pinball machine title/design — the resolved/materialized view.

    Fields are derived from resolving claims. The resolution logic picks the
    winning claim per field (highest priority source, most recent if tied).
    """

    link_url_pattern = "/machines/{slug}"

    # Identity
    name = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True, blank=True)

    # Cross-reference IDs
    ipdb_id = models.PositiveIntegerField(
        unique=True, null=True, blank=True, verbose_name="IPDB ID"
    )
    opdb_id = models.CharField(
        max_length=50, unique=True, null=True, blank=True, verbose_name="OPDB ID"
    )
    pinside_id = models.PositiveIntegerField(
        unique=True, null=True, blank=True, verbose_name="Pinside ID"
    )

    # Hierarchy
    title = models.ForeignKey(
        "Title",
        on_delete=models.SET_NULL,
        related_name="machine_models",
        null=True,
        blank=True,
        help_text="Title this machine belongs to (resolved from claims).",
    )
    variant_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="variants",
        null=True,
        blank=True,
        help_text="Parent machine model if this is a cosmetic/LE variant.",
    )
    converted_from = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="conversions",
        null=True,
        blank=True,
        help_text="Source machine if this is a conversion/retheme (resolved from claims).",
    )
    is_conversion = models.BooleanField(
        default=False,
        help_text="True if this machine is a conversion/retheme (resolved from claims).",
    )

    # Core filterable fields
    manufacturer = models.ForeignKey(
        "Manufacturer",
        on_delete=models.PROTECT,
        related_name="models",
        null=True,
        blank=True,
    )
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    month = models.PositiveSmallIntegerField(null=True, blank=True)
    technology_generation = models.ForeignKey(
        "TechnologyGeneration",
        on_delete=models.SET_NULL,
        related_name="machine_models",
        null=True,
        blank=True,
        help_text="Technology generation (resolved from claims).",
    )
    display_type = models.ForeignKey(
        "DisplayType",
        on_delete=models.SET_NULL,
        related_name="machine_models",
        null=True,
        blank=True,
        help_text="Display type (resolved from claims).",
    )
    display_subtype = models.ForeignKey(
        "DisplaySubtype",
        on_delete=models.SET_NULL,
        related_name="machine_models",
        null=True,
        blank=True,
        help_text="Display subtype (resolved from claims).",
    )
    cabinet = models.ForeignKey(
        "Cabinet",
        on_delete=models.SET_NULL,
        related_name="machine_models",
        null=True,
        blank=True,
        help_text="Cabinet form factor (resolved from claims).",
    )
    game_format = models.ForeignKey(
        "GameFormat",
        on_delete=models.SET_NULL,
        related_name="machine_models",
        null=True,
        blank=True,
        help_text="Game format (resolved from claims).",
    )
    player_count = models.PositiveSmallIntegerField(null=True, blank=True)
    themes = models.ManyToManyField(
        "Theme",
        blank=True,
        related_name="machine_models",
        help_text="Resolved theme tags (materialized from relationship claims).",
    )
    gameplay_features = models.ManyToManyField(
        "GameplayFeature",
        blank=True,
        related_name="machine_models",
        help_text="Gameplay features (materialized from relationship claims).",
    )
    tags = models.ManyToManyField(
        "Tag",
        blank=True,
        related_name="machine_models",
        help_text="Classification tags (materialized from relationship claims).",
    )
    production_quantity = models.CharField(max_length=100, blank=True)
    system = models.ForeignKey(
        "System",
        on_delete=models.SET_NULL,
        related_name="machine_models",
        null=True,
        blank=True,
        help_text="Hardware system (resolved from system claims).",
    )
    flipper_count = models.PositiveSmallIntegerField(null=True, blank=True)

    # Ratings
    ipdb_rating = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )
    pinside_rating = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True
    )

    # Catch-all for fields without dedicated columns
    extra_data = models.JSONField(default=dict, blank=True)

    # Reverse access to provenance claims for this model.
    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["manufacturer", "year"]),
            models.Index(fields=["technology_generation", "year"]),
            models.Index(fields=["display_type"]),
        ]

    def __str__(self) -> str:
        parts = [self.name]
        if self.manufacturer:
            parts.append(f"({self.manufacturer})")
        if self.year:
            parts.append(f"[{self.year}]")
        return " ".join(parts)

    def save(self, *args, **kwargs):
        if not self.slug:
            parts = [self.name]
            if self.manufacturer:
                parts.append(self.manufacturer.trade_name or self.manufacturer.name)
            if self.year:
                parts.append(str(self.year))
            self.slug = unique_slug(self, " ".join(parts), "model")
        super().save(*args, **kwargs)


class ModelAbbreviation(TimeStampedModel):
    """A common abbreviation for a MachineModel, e.g. "TS4LE" for Toy Story 4 LE.

    Materialized from provenance claims; each abbreviation is individually
    tracked with source attribution.
    """

    machine_model = models.ForeignKey(
        MachineModel, on_delete=models.CASCADE, related_name="abbreviations"
    )
    value = models.CharField(max_length=50)

    class Meta:
        ordering = ["value"]
        unique_together = [("machine_model", "value")]

    def __str__(self) -> str:
        return self.value
