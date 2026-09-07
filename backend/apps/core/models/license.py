"""License model: content licensing for creative/expressive fields."""

from __future__ import annotations

from typing import Any, override

from django.db import models

from .constraints import (
    field_not_blank,
    slug_lowercase,
    slug_not_blank,
    unique_ci,
)
from .mixins import SluggedModel, TimeStampedModel, unique_slug


class License(SluggedModel, TimeStampedModel):
    """A content license (e.g., Creative Commons, GFDL, or a policy status).

    Used to track the licensing status of creative/expressive content
    (descriptions, images, logos). Factual fields (names, years, IDs)
    are not copyrightable and are never subject to licensing.
    """

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=50, unique=True)
    spdx_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        help_text="Standard SPDX identifier (e.g., CC-BY-SA-4.0). Null for non-standard entries.",
    )
    short_name = models.CharField(max_length=50)
    url = models.URLField(blank=True, help_text="Link to canonical license deed.")
    allows_display = models.BooleanField(
        default=False,
        help_text="Informational: does this license permit public display? Not used as a runtime gate.",
    )
    requires_attribution = models.BooleanField(default=False)
    restricts_commercial = models.BooleanField(default=False)
    allows_derivatives = models.BooleanField(default=True)
    requires_share_alike = models.BooleanField(default=False)
    permissiveness_rank = models.PositiveSmallIntegerField(
        default=0,
        help_text="Higher = more permissive. Used by the global display threshold.",
    )

    class Meta:
        ordering = ["-permissiveness_rank", "name"]
        constraints = [
            field_not_blank("name"),
            field_not_blank("short_name"),
            slug_not_blank(),
            slug_lowercase(),
            unique_ci("name"),
            unique_ci("short_name"),
        ]

    @override
    def __str__(self) -> str:
        return self.short_name

    @override
    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            self.slug = unique_slug(self, self.short_name, "license")
        super().save(*args, **kwargs)
