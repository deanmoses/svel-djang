"""Theme and ThemeAlias models."""

from __future__ import annotations

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models.functions import Lower

from apps.core.models import (
    AliasBase,
    CatalogModel,
    EntityStatusMixin,
    MarkdownField,
    SluggedModel,
    TimeStampedModel,
    field_not_blank,
    slug_not_blank,
    status_valid,
)
from apps.core.validators import validate_no_mojibake

__all__ = ["Theme", "ThemeAlias", "MachineModelTheme"]


class Theme(CatalogModel, EntityStatusMixin, SluggedModel, TimeStampedModel):
    """A thematic tag for pinball machines (e.g., Sports, Horror, Licensed).

    Supports a DAG hierarchy via the ``parents`` M2M (structural, not
    claim-controlled).  The MachineModel-Theme relationship is materialized
    from relationship claims.
    """

    entity_type = "theme"
    entity_type_plural = "themes"

    name = models.CharField(
        max_length=200, unique=True, validators=[validate_no_mojibake]
    )
    description = MarkdownField(blank=True)
    parents = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="children",
        blank=True,
        help_text="Parent themes in the hierarchy (materialized from relationship claims).",
    )

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["name"]
        constraints = [slug_not_blank(), status_valid(), field_not_blank("name")]

    def __str__(self) -> str:
        return self.name


class MachineModelTheme(TimeStampedModel):
    """Through model for MachineModel ↔ Theme (materialized from relationship claims)."""

    machinemodel = models.ForeignKey("MachineModel", on_delete=models.CASCADE)
    theme = models.ForeignKey(Theme, on_delete=models.PROTECT)

    class Meta:
        db_table = "catalog_machinemodel_themes"
        constraints = [
            models.UniqueConstraint(
                fields=["machinemodel", "theme"],
                name="catalog_machinemodeltheme_unique_pair",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.machinemodel} → {self.theme}"


class ThemeAlias(AliasBase):
    """An alternate name for a Theme, used for matching/search."""

    theme = models.ForeignKey(Theme, on_delete=models.CASCADE, related_name="aliases")

    class Meta(AliasBase.Meta):
        constraints = [
            field_not_blank("value"),
            models.UniqueConstraint(
                Lower("value"),
                name="catalog_unique_theme_alias_lower",
            ),
        ]
