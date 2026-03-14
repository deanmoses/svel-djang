"""System model."""

from __future__ import annotations

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from apps.core.models import Linkable, MarkdownField, TimeStampedModel, unique_slug

__all__ = ["System"]


class System(Linkable, TimeStampedModel):
    """An electronic hardware generation for pinball machines.

    e.g. WPC-95, System 6, SAM System, SPIKE.
    MachineModel.system FK is resolved from 'system' slug claims,
    created by IPDB ingest (via mpu_strings mapping) or admin.
    """

    link_url_pattern = "/systems/{slug}"

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = MarkdownField(blank=True)
    manufacturer = models.ForeignKey(
        "Manufacturer",
        on_delete=models.SET_NULL,
        related_name="systems",
        null=True,
        blank=True,
    )
    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "system")
        super().save(*args, **kwargs)
