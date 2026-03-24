"""Location, LocationAlias, and CorporateEntityLocation models."""

from __future__ import annotations

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models.functions import Lower

from apps.core.models import AliasBase

__all__ = [
    "Location",
    "LocationAlias",
    "CorporateEntityLocation",
]


class Location(models.Model):
    """A canonical geographic location at any level of the hierarchy.

    The hierarchy is self-referential: a city's parent is its subdivision,
    a subdivision's parent is its country, etc.  ``location_path`` encodes
    the full ancestry (e.g., ``"usa/il/chicago"``) and is globally unique.
    ``slug`` is the last path segment only and is NOT globally unique.

    All display fields (name, location_type, code, description, divisions)
    are claim-controlled — pindata is the authoritative source.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    location_path = models.CharField(max_length=500, unique=True)
    slug = models.SlugField(max_length=200)
    name = models.CharField(max_length=300, blank=True)  # claim-controlled
    location_type = models.CharField(max_length=50, blank=True)  # claim-controlled
    code = models.CharField(max_length=20, blank=True)  # claim-controlled
    short_name = models.CharField(
        max_length=100, blank=True
    )  # claim-controlled; e.g. "USA", "UK"
    description = models.TextField(blank=True)  # claim-controlled
    # claim-controlled; list of level-type labels for countries only
    # e.g. ["state", "city"] or ["region", "department", "city"]
    divisions = models.JSONField(null=True, blank=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )
    claims = GenericRelation("provenance.Claim")

    class Meta:
        ordering = ["location_path"]

    def __str__(self) -> str:
        return self.name or self.location_path


class LocationAlias(AliasBase):
    """An alternate name for a Location used to match external source strings.

    Intentional mojibake aliases exist to match incorrectly encoded strings
    from IPDB/OPDB (e.g., ``"Vienne-le-Ch\ufffdteau"``).
    """

    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name="aliases"
    )

    class Meta(AliasBase.Meta):
        constraints = [
            models.UniqueConstraint(
                Lower("value"),
                "location",
                name="catalog_unique_location_alias_per_location",
            )
        ]


class CorporateEntityLocation(models.Model):
    """Associates a CorporateEntity with a canonical Location.

    One-to-many: a CE can have addresses in multiple locations.
    ``location`` points to the most specific known level (city, subdivision,
    or country).  The full hierarchy is accessible via ``location.parent``.

    Existence is controlled by ``"address"`` relationship claims on
    CorporateEntity — do not create or delete rows directly.
    """

    corporate_entity = models.ForeignKey(
        "catalog.CorporateEntity",
        on_delete=models.CASCADE,
        related_name="locations",
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="corporate_entity_locations",
    )

    class Meta:
        unique_together = [("corporate_entity", "location")]
        verbose_name = "corporate entity location"
        verbose_name_plural = "corporate entity locations"

    def __str__(self) -> str:
        return f"{self.corporate_entity} → {self.location}"
