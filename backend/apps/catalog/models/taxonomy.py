"""Taxonomy lookup models — technology, display, cabinet, game format, etc."""

from __future__ import annotations

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models.functions import Lower

from apps.core.validators import validate_no_mojibake

from apps.core.models import (
    AliasBase,
    Linkable,
    MarkdownField,
    TimeStampedModel,
    unique_slug,
)

__all__ = [
    "TechnologyGeneration",
    "TechnologySubgeneration",
    "DisplayType",
    "DisplaySubtype",
    "Cabinet",
    "GameFormat",
    "RewardType",
    "RewardTypeAlias",
    "Tag",
    "CreditRole",
]


class TechnologyGeneration(Linkable, TimeStampedModel):
    """A major technological era: Pure Mechanical, Electromechanical, Solid State.

    Name and display_order are claim-controlled; description is direct editorial.
    """

    link_url_pattern = "/technology-generations/{slug}"

    name = models.CharField(
        max_length=200, unique=True, validators=[validate_no_mojibake]
    )
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    description = MarkdownField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "techgen")
        super().save(*args, **kwargs)


class TechnologySubgeneration(Linkable, TimeStampedModel):
    """A subdivision within a TechnologyGeneration.

    e.g., Solid State → Discrete Logic, Integrated (MPU), PC-Based.
    """

    link_url_pattern = "/technology-subgenerations/{slug}"

    name = models.CharField(max_length=200, validators=[validate_no_mojibake])
    slug = models.SlugField(max_length=200, unique=True, blank=True)
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

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "techsubgen")
        super().save(*args, **kwargs)


class DisplayType(Linkable, TimeStampedModel):
    """A display technology category: Score Reels, DMD, LCD, etc.

    Replaces the old DisplayType enum.
    """

    link_url_pattern = "/display-types/{slug}"

    name = models.CharField(
        max_length=200, unique=True, validators=[validate_no_mojibake]
    )
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    description = MarkdownField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "displaytype")
        super().save(*args, **kwargs)


class DisplaySubtype(Linkable, TimeStampedModel):
    """A subdivision within a DisplayType.

    e.g., LCD → Standard LCD, HD LCD.
    """

    link_url_pattern = "/display-subtypes/{slug}"

    name = models.CharField(max_length=200, validators=[validate_no_mojibake])
    slug = models.SlugField(max_length=200, unique=True, blank=True)
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

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "displaysubtype")
        super().save(*args, **kwargs)


class Cabinet(Linkable, TimeStampedModel):
    """Physical cabinet form factor: Floor, Tabletop, Countertop, Cocktail."""

    link_url_pattern = "/cabinets/{slug}"

    name = models.CharField(
        max_length=200, unique=True, validators=[validate_no_mojibake]
    )
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    description = MarkdownField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "cabinet")
        super().save(*args, **kwargs)


class GameFormat(Linkable, TimeStampedModel):
    """Game format: Pinball, Bagatelle, Shuffle Alley, Pitch-and-Bat."""

    link_url_pattern = "/game-formats/{slug}"

    name = models.CharField(
        max_length=200, unique=True, validators=[validate_no_mojibake]
    )
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    description = MarkdownField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "gameformat")
        super().save(*args, **kwargs)


class RewardType(Linkable, TimeStampedModel):
    """A pinball reward mechanism: replay, add-a-ball, free-play, etc.

    Reward types are the payoff mechanic for achieving a goal, distinct from
    gameplay features (the mechanisms used to earn that payoff).
    """

    link_url_pattern = "/reward-types/{slug}"

    name = models.CharField(
        max_length=200, unique=True, validators=[validate_no_mojibake]
    )
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    description = MarkdownField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "rewardtype")
        super().save(*args, **kwargs)


class RewardTypeAlias(AliasBase):
    """An alternate name for a RewardType, used for matching/search."""

    reward_type = models.ForeignKey(
        RewardType, on_delete=models.CASCADE, related_name="aliases"
    )

    class Meta(AliasBase.Meta):
        constraints = [
            models.UniqueConstraint(
                Lower("value"),
                name="catalog_unique_reward_type_alias_lower",
            ),
        ]


class Tag(Linkable, TimeStampedModel):
    """A classification tag: Home Use, Prototype, Widebody, Remake, etc.

    Linked to MachineModel via M2M relationship claims.
    """

    link_url_pattern = "/tags/{slug}"

    name = models.CharField(
        max_length=200, unique=True, validators=[validate_no_mojibake]
    )
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    description = MarkdownField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "tag")
        super().save(*args, **kwargs)


class CreditRole(Linkable, TimeStampedModel):
    """A credit role category: Design, Art, Software, etc."""

    link_url_pattern = "/credit-roles/{slug}"

    name = models.CharField(
        max_length=200, unique=True, validators=[validate_no_mojibake]
    )
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    description = MarkdownField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["display_order"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "creditrole")
        super().save(*args, **kwargs)
