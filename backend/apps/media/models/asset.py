"""MediaAsset: one logical Pinbase-owned uploaded media item."""

from __future__ import annotations

import uuid as uuid_lib
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel, field_not_blank

if TYPE_CHECKING:
    from .rendition import MediaRendition


class MediaAsset(TimeStampedModel):
    """One logical Pinbase-owned uploaded media item (infrastructure)."""

    renditions: models.Manager[MediaRendition]

    class Kind(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    class Status(models.TextChoices):
        READY = "ready", "Ready"
        PROCESSING = "processing", "Processing"
        FAILED = "failed", "Failed"

    uuid = models.UUIDField(unique=True, default=uuid_lib.uuid4, editable=False)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    byte_size = models.PositiveBigIntegerField()
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="media_assets",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # --- string not-blank ---
            field_not_blank("original_filename"),
            field_not_blank("mime_type"),
            # --- original_filename must have an extension ---
            models.CheckConstraint(
                condition=models.Q(original_filename__contains="."),
                name="media_mediaasset_original_filename_has_ext",
                violation_error_message="original_filename must contain a file extension.",
            ),
            # --- byte_size > 0 ---
            models.CheckConstraint(
                condition=models.Q(byte_size__gt=0),
                name="media_mediaasset_byte_size_positive",
                violation_error_message="byte_size must be greater than zero.",
            ),
            # --- kind in valid set ---
            models.CheckConstraint(
                condition=models.Q(kind__in=["image", "video"]),
                name="media_mediaasset_kind_valid",
                violation_error_message="kind must be 'image' or 'video'.",
            ),
            # --- status in valid set ---
            models.CheckConstraint(
                condition=models.Q(status__in=["ready", "processing", "failed"]),
                name="media_mediaasset_status_valid",
                violation_error_message="status must be 'ready', 'processing', or 'failed'.",
            ),
            # --- width/height both null or both set ---
            models.CheckConstraint(
                condition=(
                    models.Q(width__isnull=True, height__isnull=True)
                    | models.Q(width__isnull=False, height__isnull=False)
                ),
                name="media_mediaasset_dimensions_both_or_neither",
                violation_error_message="width and height must both be null or both be set.",
                violation_error_code="cross_field",
            ),
            # --- width > 0 when set ---
            models.CheckConstraint(
                condition=models.Q(width__isnull=True) | models.Q(width__gt=0),
                name="media_mediaasset_width_positive",
                violation_error_message="width must be greater than zero.",
            ),
            # --- height > 0 when set ---
            models.CheckConstraint(
                condition=models.Q(height__isnull=True) | models.Q(height__gt=0),
                name="media_mediaasset_height_positive",
                violation_error_message="height must be greater than zero.",
            ),
            # --- ready image must have dimensions ---
            models.CheckConstraint(
                condition=(
                    ~models.Q(status="ready", kind="image")
                    | models.Q(width__isnull=False)
                ),
                name="media_mediaasset_ready_image_has_dimensions",
                violation_error_message="A ready image must have width and height.",
                violation_error_code="cross_field",
            ),
            # --- image status cannot be 'processing' ---
            models.CheckConstraint(
                condition=~models.Q(kind="image") | ~models.Q(status="processing"),
                name="media_mediaasset_image_not_processing",
                violation_error_message="Images are processed synchronously and cannot have status 'processing'.",
                violation_error_code="cross_field",
            ),
            # --- mime_type consistent with kind ---
            models.CheckConstraint(
                condition=(
                    models.Q(kind="image", mime_type__startswith="image/")
                    | models.Q(kind="video", mime_type__startswith="video/")
                ),
                name="media_mediaasset_mime_type_matches_kind",
                violation_error_message="mime_type must be consistent with kind.",
                violation_error_code="cross_field",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.original_filename} ({self.uuid})"
