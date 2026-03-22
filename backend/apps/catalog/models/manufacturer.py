"""Manufacturer, CorporateEntity, and Address models."""

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

__all__ = [
    "Manufacturer",
    "ManufacturerAlias",
    "CorporateEntity",
    "CorporateEntityAlias",
    "Address",
]


class Manufacturer(Linkable, TimeStampedModel):
    """A pinball machine brand (user-facing grouping).

    Corporate incarnations are tracked separately in ManufacturerEntity.
    For example, "Gottlieb" is one Manufacturer with four ManufacturerEntity
    records spanning different ownership eras.
    """

    link_url_pattern = "/manufacturers/{slug}"

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    opdb_manufacturer_id = models.IntegerField(
        unique=True,
        null=True,
        blank=True,
        help_text="OPDB manufacturer_id for this brand.",
    )
    wikidata_id = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        help_text="Wikidata QID, e.g. Q180268",
    )
    description = MarkdownField(blank=True)
    logo_url = models.URLField(null=True, blank=True)
    website = models.URLField(blank=True)

    # Catch-all for fields without dedicated columns (e.g. fandom.description)
    extra_data = models.JSONField(default=dict, blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "manufacturer")
        super().save(*args, **kwargs)


class ManufacturerAlias(AliasBase):
    """An alternate name for a Manufacturer, used to match alternative spellings
    from external sources.
    """

    manufacturer = models.ForeignKey(
        Manufacturer, on_delete=models.CASCADE, related_name="aliases"
    )

    class Meta(AliasBase.Meta):
        constraints = [
            models.UniqueConstraint(
                Lower("value"),
                name="catalog_unique_manufacturer_alias_lower",
            ),
        ]


class CorporateEntity(TimeStampedModel):
    """A specific corporate incarnation of a manufacturer brand.

    IPDB tracks corporate entities (e.g., four separate entries for Gottlieb
    across its ownership eras). Each entity maps to one brand-level Manufacturer.
    """

    manufacturer = models.ForeignKey(
        Manufacturer,
        on_delete=models.CASCADE,
        related_name="entities",
    )
    slug = models.SlugField(max_length=300, unique=True, blank=True)
    description = MarkdownField(blank=True)
    name = models.CharField(
        max_length=300,
        help_text='Full corporate name, e.g., "D. Gottlieb & Company"',
    )
    ipdb_manufacturer_id = models.IntegerField(
        unique=True,
        null=True,
        blank=True,
        help_text="IPDB ManufacturerId for this corporate entity.",
    )
    year_start = models.IntegerField(
        null=True, blank=True, help_text="Year this corporate entity was established."
    )
    year_end = models.IntegerField(
        null=True, blank=True, help_text="Year this corporate entity ceased operations."
    )

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["manufacturer", "year_start"]
        verbose_name = "corporate entity"
        verbose_name_plural = "corporate entities"
        constraints = []

    def __str__(self) -> str:
        if self.year_start:
            end = self.year_end or "present"
            return f"{self.name} ({self.year_start}-{end})"
        return self.name


class CorporateEntityAlias(AliasBase):
    """An alternate name for a CorporateEntity, used to match alternative spellings
    from external sources.
    """

    corporate_entity = models.ForeignKey(
        CorporateEntity, on_delete=models.CASCADE, related_name="aliases"
    )

    class Meta(AliasBase.Meta):
        constraints = [
            models.UniqueConstraint(
                Lower("value"),
                name="catalog_unique_corporate_entity_alias_lower",
            ),
        ]


class Address(models.Model):
    corporate_entity = models.ForeignKey(
        CorporateEntity, on_delete=models.CASCADE, related_name="addresses"
    )
    city = models.CharField(max_length=255, blank=True)
    state = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name_plural = "addresses"

    def __str__(self):
        parts = [p for p in (self.city, self.state, self.country) if p]
        return ", ".join(parts)
