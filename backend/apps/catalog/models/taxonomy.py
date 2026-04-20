"""Taxonomy lookup models — technology, display, cabinet, game format, etc."""

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

__all__ = [
    "TechnologyGeneration",
    "TechnologySubgeneration",
    "DisplayType",
    "DisplaySubtype",
    "Cabinet",
    "GameFormat",
    "RewardType",
    "RewardTypeAlias",
    "MachineModelRewardType",
    "Tag",
    "MachineModelTag",
    "CreditRole",
]


class TechnologyGeneration(
    CatalogModel, EntityStatusMixin, SluggedModel, TimeStampedModel
):
    """A major technological era: Pure Mechanical, Electromechanical, Solid State.

    Name and display_order are claim-controlled; description is direct editorial.
    """

    entity_type = "technology-generation"
    entity_type_plural = "technology-generations"

    name = models.CharField(
        max_length=200, unique=True, validators=[validate_no_mojibake]
    )
    display_order = models.PositiveSmallIntegerField(default=0)
    description = MarkdownField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]
        constraints = [slug_not_blank(), status_valid(), field_not_blank("name")]

    def __str__(self) -> str:
        return self.name


class TechnologySubgeneration(
    CatalogModel, EntityStatusMixin, SluggedModel, TimeStampedModel
):
    """A subdivision within a TechnologyGeneration.

    e.g., Solid State → Discrete Logic, Integrated (MPU), PC-Based.
    """

    entity_type = "technology-subgeneration"
    entity_type_plural = "technology-subgenerations"

    name = models.CharField(
        max_length=200, unique=True, validators=[validate_no_mojibake]
    )
    display_order = models.PositiveSmallIntegerField(default=0)
    description = MarkdownField(blank=True)
    technology_generation = models.ForeignKey(
        TechnologyGeneration,
        on_delete=models.CASCADE,
        related_name="subgenerations",
    )

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]
        constraints = [slug_not_blank(), status_valid(), field_not_blank("name")]

    def __str__(self) -> str:
        return self.name


class DisplayType(CatalogModel, EntityStatusMixin, SluggedModel, TimeStampedModel):
    """A display technology category: Score Reels, DMD, LCD, etc.

    Replaces the old DisplayType enum.
    """

    entity_type = "display-type"
    entity_type_plural = "display-types"

    name = models.CharField(
        max_length=200, unique=True, validators=[validate_no_mojibake]
    )
    display_order = models.PositiveSmallIntegerField(default=0)
    description = MarkdownField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]
        constraints = [slug_not_blank(), status_valid(), field_not_blank("name")]

    def __str__(self) -> str:
        return self.name


class DisplaySubtype(CatalogModel, EntityStatusMixin, SluggedModel, TimeStampedModel):
    """A subdivision within a DisplayType.

    e.g., LCD → Standard LCD, HD LCD.
    """

    entity_type = "display-subtype"
    entity_type_plural = "display-subtypes"

    name = models.CharField(
        max_length=200, unique=True, validators=[validate_no_mojibake]
    )
    display_order = models.PositiveSmallIntegerField(default=0)
    description = MarkdownField(blank=True)
    display_type = models.ForeignKey(
        DisplayType,
        on_delete=models.CASCADE,
        related_name="subtypes",
    )

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]
        constraints = [slug_not_blank(), status_valid(), field_not_blank("name")]

    def __str__(self) -> str:
        return self.name


class Cabinet(CatalogModel, EntityStatusMixin, SluggedModel, TimeStampedModel):
    """Physical cabinet form factor: Floor, Tabletop, Countertop, Cocktail."""

    entity_type = "cabinet"
    entity_type_plural = "cabinets"

    name = models.CharField(
        max_length=200, unique=True, validators=[validate_no_mojibake]
    )
    display_order = models.PositiveSmallIntegerField(default=0)
    description = MarkdownField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]
        constraints = [slug_not_blank(), status_valid(), field_not_blank("name")]

    def __str__(self) -> str:
        return self.name


class GameFormat(CatalogModel, EntityStatusMixin, SluggedModel, TimeStampedModel):
    """Game format: Pinball, Bagatelle, Shuffle Alley, Pitch-and-Bat."""

    entity_type = "game-format"
    entity_type_plural = "game-formats"

    name = models.CharField(
        max_length=200, unique=True, validators=[validate_no_mojibake]
    )
    display_order = models.PositiveSmallIntegerField(default=0)
    description = MarkdownField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]
        constraints = [slug_not_blank(), status_valid(), field_not_blank("name")]

    def __str__(self) -> str:
        return self.name


class RewardType(CatalogModel, EntityStatusMixin, SluggedModel, TimeStampedModel):
    """A pinball reward mechanism: replay, add-a-ball, free-play, etc.

    Reward types are the payoff mechanic for achieving a goal, distinct from
    gameplay features (the mechanisms used to earn that payoff).
    """

    entity_type = "reward-type"
    entity_type_plural = "reward-types"

    name = models.CharField(
        max_length=200, unique=True, validators=[validate_no_mojibake]
    )
    display_order = models.PositiveSmallIntegerField(default=0)
    description = MarkdownField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order", "name"]
        constraints = [slug_not_blank(), status_valid(), field_not_blank("name")]

    def __str__(self) -> str:
        return self.name


class MachineModelRewardType(TimeStampedModel):
    """Through model for MachineModel ↔ RewardType (materialized from relationship claims)."""

    machinemodel = models.ForeignKey("MachineModel", on_delete=models.CASCADE)
    rewardtype = models.ForeignKey(RewardType, on_delete=models.PROTECT)

    class Meta:
        db_table = "catalog_machinemodel_reward_types"
        constraints = [
            models.UniqueConstraint(
                fields=["machinemodel", "rewardtype"],
                name="catalog_machinemodelrewardtype_unique_pair",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.machinemodel} → {self.rewardtype}"


class RewardTypeAlias(AliasBase):
    """An alternate name for a RewardType, used for matching/search."""

    reward_type = models.ForeignKey(
        RewardType, on_delete=models.CASCADE, related_name="aliases"
    )

    class Meta(AliasBase.Meta):
        constraints = [
            field_not_blank("value"),
            models.UniqueConstraint(
                Lower("value"),
                name="catalog_unique_reward_type_alias_lower",
            ),
        ]


class Tag(CatalogModel, EntityStatusMixin, SluggedModel, TimeStampedModel):
    """A classification tag: Home Use, Prototype, Widebody, Remake, etc.

    Linked to MachineModel via M2M relationship claims.
    """

    entity_type = "tag"
    entity_type_plural = "tags"

    name = models.CharField(
        max_length=200, unique=True, validators=[validate_no_mojibake]
    )
    display_order = models.PositiveSmallIntegerField(default=0)
    description = MarkdownField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]
        constraints = [slug_not_blank(), status_valid(), field_not_blank("name")]

    def __str__(self) -> str:
        return self.name


class MachineModelTag(TimeStampedModel):
    """Through model for MachineModel ↔ Tag (materialized from relationship claims)."""

    machinemodel = models.ForeignKey("MachineModel", on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.PROTECT)

    class Meta:
        db_table = "catalog_machinemodel_tags"
        constraints = [
            models.UniqueConstraint(
                fields=["machinemodel", "tag"],
                name="catalog_machinemodeltag_unique_pair",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.machinemodel} → {self.tag}"


class CreditRole(CatalogModel, EntityStatusMixin, SluggedModel, TimeStampedModel):
    """A credit role category: Design, Art, Software, etc."""

    entity_type = "credit-role"
    entity_type_plural = "credit-roles"

    name = models.CharField(
        max_length=200, unique=True, validators=[validate_no_mojibake]
    )
    display_order = models.PositiveSmallIntegerField(default=0)
    description = MarkdownField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]
        constraints = [slug_not_blank(), status_valid(), field_not_blank("name")]

    def __str__(self) -> str:
        return self.name
