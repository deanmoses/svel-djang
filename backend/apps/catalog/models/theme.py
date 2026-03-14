"""Theme model."""

from __future__ import annotations

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from apps.core.models import Linkable, MarkdownField, TimeStampedModel, unique_slug

__all__ = ["Theme"]


class Theme(Linkable, TimeStampedModel):
    """A thematic tag for pinball machines (e.g., Sports, Horror, Licensed).

    Flat taxonomy — no hierarchy. Fields are claim-controlled.
    The MachineModel↔Theme relationship is materialized from relationship claims.
    """

    link_url_pattern = "/themes/{slug}"

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = MarkdownField(blank=True)

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "theme")
        super().save(*args, **kwargs)
