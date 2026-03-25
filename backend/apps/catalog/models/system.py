"""System model."""

from __future__ import annotations

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from apps.core.models import Linkable, MarkdownField, TimeStampedModel, unique_slug

__all__ = ["System", "SystemMpuString"]


class System(Linkable, TimeStampedModel):
    """An electronic hardware generation for pinball machines.

    e.g. WPC-95, System 6, SAM System, SPIKE.
    MachineModel.system FK is resolved from 'system' slug claims.
    """

    link_url_pattern = "/systems/{slug}"
    claims_exempt = frozenset({"manufacturer", "technology_subgeneration"})

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
    technology_subgeneration = models.ForeignKey(
        "TechnologySubgeneration",
        on_delete=models.SET_NULL,
        related_name="systems",
        null=True,
        blank=True,
        help_text="Technology subgeneration this system belongs to.",
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


class SystemMpuString(TimeStampedModel):
    """An MPU board identifier string used to match machines to a System.

    e.g., "Stern SPIKE System", "Williams WPC-95".
    """

    system = models.ForeignKey(
        System, on_delete=models.CASCADE, related_name="mpu_strings"
    )
    value = models.CharField(max_length=200)

    class Meta:
        ordering = ["value"]
        constraints = [
            models.UniqueConstraint(
                fields=["value"],
                name="catalog_unique_system_mpu_string",
            ),
        ]

    def __str__(self) -> str:
        return self.value
