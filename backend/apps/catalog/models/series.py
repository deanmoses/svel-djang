"""Franchise and Series models — title-grouping entities."""

from __future__ import annotations

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from apps.core.models import Linkable, MarkdownField, TimeStampedModel, unique_slug

__all__ = ["Franchise", "Series"]


class Franchise(Linkable, TimeStampedModel):
    """An IP grouping that spans manufacturers and eras.

    e.g., Indiana Jones, Star Trek. Most Titles do not belong to a Franchise.
    Seeded from franchises.json.
    """

    link_url_pattern = "/franchises/{slug}"

    name = models.CharField(max_length=300, unique=True)
    slug = models.SlugField(max_length=300, unique=True, blank=True)
    description = MarkdownField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "franchise")
        super().save(*args, **kwargs)


class Series(Linkable, TimeStampedModel):
    """A manually-curated grouping of related Titles sharing a thematic lineage.

    e.g., the "Eight Ball" series spans Eight Ball, Eight Ball Deluxe, and
    Eight Ball Champ. Series are sparse — most Titles belong to none. They can
    span multiple manufacturers. No data ingest populates them; they are
    maintained by curators via the admin or seed data.
    """

    link_url_pattern = "/series/{slug}"

    name = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True, blank=True)
    description = MarkdownField(blank=True)
    titles = models.ManyToManyField(
        "Title",
        blank=True,
        related_name="series",
    )

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "series"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "series")
        super().save(*args, **kwargs)
