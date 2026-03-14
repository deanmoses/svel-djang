"""Taxonomy lookup models — technology, display, cabinet, game format, etc."""

from __future__ import annotations

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from apps.core.models import Linkable, MarkdownField, TimeStampedModel, unique_slug

__all__ = [
    "TechnologyGeneration",
    "TechnologySubgeneration",
    "DisplayType",
    "DisplaySubtype",
    "Cabinet",
    "GameFormat",
    "GameplayFeature",
    "Tag",
    "CreditRole",
]


class TechnologyGeneration(Linkable, TimeStampedModel):
    """A major technological era: Pure Mechanical, Electromechanical, Solid State.

    Replaces the old MachineType enum. Seeded from technology_generations.json.
    Name and display_order are claim-controlled; description is direct editorial.
    """

    link_url_pattern = "/technology-generations/{slug}"

    name = models.CharField(max_length=200, unique=True)
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
    Seeded from technology_subgenerations.json.
    """

    link_url_pattern = "/technology-subgenerations/{slug}"

    name = models.CharField(max_length=200)
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

    Replaces the old DisplayType enum. Seeded from display_types.json.
    """

    link_url_pattern = "/display-types/{slug}"

    name = models.CharField(max_length=200, unique=True)
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

    e.g., LCD → Standard LCD, HD LCD. Seeded from display_subtypes.json.
    """

    link_url_pattern = "/display-subtypes/{slug}"

    name = models.CharField(max_length=200)
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
    """Physical cabinet form factor: Floor, Tabletop, Countertop, Cocktail.

    Seeded from cabinets.json.
    """

    link_url_pattern = "/cabinets/{slug}"

    name = models.CharField(max_length=200, unique=True)
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
    """Game format: Pinball, Bagatelle, Shuffle Alley, Pitch-and-Bat.

    Seeded from game_formats.json.
    """

    link_url_pattern = "/game-formats/{slug}"

    name = models.CharField(max_length=200, unique=True)
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


class GameplayFeature(Linkable, TimeStampedModel):
    """A gameplay mechanism: Flippers, Pop Bumpers, Ramps, Multiball, etc.

    Seeded from gameplay_features.json. Linked to MachineModel via M2M.
    """

    link_url_pattern = "/gameplay-features/{slug}"

    name = models.CharField(max_length=200, unique=True)
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
            self.slug = unique_slug(self, self.name, "feature")
        super().save(*args, **kwargs)


class Tag(Linkable, TimeStampedModel):
    """A classification tag: Home Use, Prototype, Widebody, Remake, etc.

    Seeded from tags.json. Linked to MachineModel via M2M relationship claims.
    """

    link_url_pattern = "/tags/{slug}"

    name = models.CharField(max_length=200, unique=True)
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
    """A credit role category: Design, Art, Software, etc.

    Seeded from credit_roles.json.
    """

    link_url_pattern = "/credit-roles/{slug}"

    name = models.CharField(max_length=200, unique=True)
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
