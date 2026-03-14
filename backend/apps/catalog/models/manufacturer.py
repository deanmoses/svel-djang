"""Manufacturer, CorporateEntity, and Address models."""

from __future__ import annotations

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from apps.core.models import Linkable, MarkdownField, TimeStampedModel, unique_slug

__all__ = ["Manufacturer", "CorporateEntity", "Address"]


class Manufacturer(Linkable, TimeStampedModel):
    """A pinball machine brand (user-facing grouping).

    Corporate incarnations are tracked separately in ManufacturerEntity.
    For example, "Gottlieb" is one Manufacturer with four ManufacturerEntity
    records spanning different ownership eras.
    """

    link_url_pattern = "/manufacturers/{slug}"

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    trade_name = models.CharField(
        max_length=200,
        blank=True,
        help_text='Brand name if different (e.g., "Bally" for Midway Manufacturing)',
    )
    wikidata_id = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        help_text="Wikidata QID, e.g. Q180268",
    )
    description = MarkdownField(blank=True)
    founded_year = models.IntegerField(null=True, blank=True)
    dissolved_year = models.IntegerField(null=True, blank=True)
    country = models.CharField(max_length=200, null=True, blank=True)
    headquarters = models.CharField(max_length=200, null=True, blank=True)
    logo_url = models.URLField(null=True, blank=True)
    website = models.URLField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        if self.trade_name and self.trade_name != self.name:
            return f"{self.trade_name} ({self.name})"
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.trade_name or self.name, "manufacturer")
        super().save(*args, **kwargs)


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
    name = models.CharField(
        max_length=300,
        help_text='Full corporate name, e.g., "D. Gottlieb & Company"',
    )
    years_active = models.CharField(
        max_length=50,
        blank=True,
        help_text='Operating period, e.g., "1931-1977"',
    )

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["manufacturer", "years_active"]
        verbose_name = "corporate entity"
        verbose_name_plural = "corporate entities"
        constraints = [
            models.UniqueConstraint(
                fields=["manufacturer", "name"],
                name="catalog_unique_corporate_entity_per_manufacturer",
            ),
        ]

    def __str__(self) -> str:
        if self.years_active:
            return f"{self.name} ({self.years_active})"
        return self.name


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
