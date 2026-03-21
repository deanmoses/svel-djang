"""Theme and ThemeAlias models."""

from __future__ import annotations

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from apps.core.models import Linkable, MarkdownField, TimeStampedModel, unique_slug

__all__ = ["Theme", "ThemeAlias"]


class Theme(Linkable, TimeStampedModel):
    """A thematic tag for pinball machines (e.g., Sports, Horror, Licensed).

    Supports a DAG hierarchy via the ``parents`` M2M (structural, not
    claim-controlled).  The MachineModel-Theme relationship is materialized
    from relationship claims.
    """

    link_url_pattern = "/themes/{slug}"

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = MarkdownField(blank=True)
    parents = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="children",
        blank=True,
        help_text="Parent themes in the hierarchy (structural, not claim-controlled).",
    )

    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, "theme")
        super().save(*args, **kwargs)


class ThemeAlias(TimeStampedModel):
    """An alternate name for a Theme, used for matching/search."""

    theme = models.ForeignKey(Theme, on_delete=models.CASCADE, related_name="aliases")
    value = models.CharField(max_length=200)

    class Meta:
        ordering = ["value"]
        unique_together = [("theme", "value")]

    def __str__(self) -> str:
        return self.value
