"""MediaRendition: one physical stored file for a media asset."""

from __future__ import annotations

import uuid as uuid_lib

from django.db import models

from apps.core.models import TimeStampedModel, field_not_blank

from .asset import MediaAsset


class MediaRendition(TimeStampedModel):
    """One physical stored file for a media asset (infrastructure)."""

    asset_id: int

    class RenditionType(models.TextChoices):
        ORIGINAL = "original", "Original"
        THUMB = "thumb", "Thumbnail"
        DISPLAY = "display", "Display"

    uuid = models.UUIDField(unique=True, default=uuid_lib.uuid4, editable=False)
    asset = models.ForeignKey(
        MediaAsset, on_delete=models.CASCADE, related_name="renditions"
    )
    rendition_type = models.CharField(max_length=30, choices=RenditionType.choices)
    mime_type = models.CharField(max_length=100)
    byte_size = models.PositiveBigIntegerField()
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    is_ready = models.BooleanField(default=True)

    class Meta:
        ordering = ["asset", "rendition_type"]
        constraints = [
            # --- string not-blank ---
            field_not_blank("rendition_type"),
            field_not_blank("mime_type"),
            # --- byte_size > 0 ---
            models.CheckConstraint(
                condition=models.Q(byte_size__gt=0),
                name="media_mediarendition_byte_size_positive",
                violation_error_message="byte_size must be greater than zero.",
            ),
            # --- width/height both null or both set ---
            models.CheckConstraint(
                condition=(
                    models.Q(width__isnull=True, height__isnull=True)
                    | models.Q(width__isnull=False, height__isnull=False)
                ),
                name="media_mediarendition_dimensions_both_or_neither",
                violation_error_message="width and height must both be null or both be set.",
                violation_error_code="cross_field",
            ),
            # --- width > 0 when set ---
            models.CheckConstraint(
                condition=models.Q(width__isnull=True) | models.Q(width__gt=0),
                name="media_mediarendition_width_positive",
                violation_error_message="width must be greater than zero.",
            ),
            # --- height > 0 when set ---
            models.CheckConstraint(
                condition=models.Q(height__isnull=True) | models.Q(height__gt=0),
                name="media_mediarendition_height_positive",
                violation_error_message="height must be greater than zero.",
            ),
            # --- rendition_type in valid set ---
            models.CheckConstraint(
                condition=models.Q(rendition_type__in=["original", "thumb", "display"]),
                name="media_mediarendition_rendition_type_valid",
                violation_error_message="rendition_type must be 'original', 'thumb', or 'display'.",
            ),
            # --- one rendition per type per asset ---
            models.UniqueConstraint(
                fields=["asset", "rendition_type"],
                name="media_mediarendition_unique_asset_rendition_type",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.rendition_type} for {self.asset_id}"
