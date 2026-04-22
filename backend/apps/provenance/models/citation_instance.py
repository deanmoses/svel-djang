"""CitationInstance: a specific use of a CitationSource with a locator."""

from __future__ import annotations

from django.db import models
from django.db.models.functions import Now

from apps.core.validators import validate_no_mojibake


class CitationInstance(models.Model):
    """A specific use of a CitationSource at a point in text, with a locator.

    Immutable: corrections create a new instance (old one becomes orphaned).
    Only has created_at, no updated_at — matching the Claim immutability pattern.

    claim is nullable: null for inline markdown citations (``[[cite:id:...]]``),
    set for scalar claim citations.
    """

    citation_source_id: int
    claim_id: int | None

    citation_source = models.ForeignKey(
        "citation.CitationSource",
        on_delete=models.PROTECT,
        related_name="instances",
    )
    claim = models.ForeignKey(
        "provenance.Claim",
        on_delete=models.PROTECT,
        related_name="citation_instances",
        null=True,
        blank=True,
    )
    locator = models.TextField(
        blank=True, default="", db_default="", validators=[validate_no_mojibake]
    )
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        indexes = [
            models.Index(
                fields=["citation_source"],
                name="prov_citinst_source_idx",
            ),
            models.Index(
                fields=["claim"],
                name="prov_citinst_claim_idx",
            ),
        ]

    def __str__(self) -> str:
        loc = f" @ {self.locator}" if self.locator else ""
        return f"Citation: {self.citation_source_id}{loc}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError(
                "CitationInstance is immutable. Create a new instance instead."
            )
        super().save(*args, **kwargs)
