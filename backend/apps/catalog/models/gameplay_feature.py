"""GameplayFeature and GameplayFeatureAlias models."""

from __future__ import annotations

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models.functions import Lower

from apps.core.models import (
    AliasBase,
    Linkable,
    MarkdownField,
    TimeStampedModel,
    unique_slug,
)

__all__ = ["GameplayFeature", "GameplayFeatureAlias", "MachineModelGameplayFeature"]


class GameplayFeature(Linkable, TimeStampedModel):
    """A gameplay mechanism: Flippers, Pop Bumpers, Ramps, Multiball, etc.

    Supports a DAG hierarchy via the ``parents`` M2M (claim-controlled).
    The MachineModel-GameplayFeature relationship is materialized from claims.
    """

    link_url_pattern = "/gameplay-features/{slug}"

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = MarkdownField(blank=True)
    parents = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="children",
        blank=True,
        help_text="Parent features in the hierarchy (materialized from relationship claims).",
    )

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "feature")
        super().save(*args, **kwargs)


class MachineModelGameplayFeature(TimeStampedModel):
    """Through model for MachineModel ↔ GameplayFeature, carrying optional count."""

    machinemodel = models.ForeignKey("MachineModel", on_delete=models.CASCADE)
    gameplayfeature = models.ForeignKey(GameplayFeature, on_delete=models.CASCADE)
    count = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Quantity from source data, e.g. Flippers (2) → count=2.",
    )

    class Meta:
        unique_together = [("machinemodel", "gameplayfeature")]

    def __str__(self) -> str:
        label = f"{self.machinemodel} → {self.gameplayfeature}"
        if self.count is not None:
            label += f" ({self.count})"
        return label


class GameplayFeatureAlias(AliasBase):
    """An alternate name for a GameplayFeature, used for matching/search."""

    feature = models.ForeignKey(
        GameplayFeature, on_delete=models.CASCADE, related_name="aliases"
    )

    class Meta(AliasBase.Meta):
        constraints = [
            models.UniqueConstraint(
                Lower("value"),
                name="catalog_unique_gameplay_feature_alias_lower",
            ),
        ]
