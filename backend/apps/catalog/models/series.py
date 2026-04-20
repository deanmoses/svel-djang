"""Franchise and Series models — title-grouping entities."""

from __future__ import annotations

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from apps.core.models import (
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

__all__ = ["Franchise", "Series"]


class Franchise(CatalogModel, EntityStatusMixin, SluggedModel, TimeStampedModel):
    """An IP grouping that spans manufacturers and eras.

    e.g., Indiana Jones, Star Trek. Most Titles do not belong to a Franchise.
    """

    entity_type = "franchise"
    entity_type_plural = "franchises"

    name = models.CharField(
        max_length=200, validators=[validate_no_mojibake], unique=True
    )
    description = MarkdownField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["name"]
        constraints = [slug_not_blank(), status_valid(), field_not_blank("name")]

    def __str__(self) -> str:
        return self.name


class Series(CatalogModel, EntityStatusMixin, SluggedModel, TimeStampedModel):
    """A manually-curated grouping of related Titles sharing a thematic lineage.

    e.g., the "Eight Ball" series spans Eight Ball, Eight Ball Deluxe, and
    Eight Ball Champ. Series are sparse — most Titles belong to none. They can
    span multiple manufacturers. No data ingest populates them; they are
    maintained by curators via the admin or seed data.
    """

    entity_type = "series"
    entity_type_plural = "series"

    name = models.CharField(
        max_length=200, validators=[validate_no_mojibake], unique=True
    )
    description = MarkdownField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "series"
        constraints = [slug_not_blank(), status_valid(), field_not_blank("name")]

    def __str__(self) -> str:
        return self.name
