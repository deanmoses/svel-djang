"""Media models: storage infrastructure and catalog attachment."""

from __future__ import annotations

import uuid as uuid_lib

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from django.core.exceptions import ValidationError

from apps.core.models import MediaSupported, TimeStampedModel, field_not_blank


# ---------------------------------------------------------------------------
# MediaAsset
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# MediaRendition
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# EntityMedia
# ---------------------------------------------------------------------------


class EntityMedia(TimeStampedModel):
    """Resolved catalog attachment linking an entity to a media asset.

    Materialized from claims — not hand-edited.
    """

    content_type_id: int
    asset_id: int

    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveBigIntegerField()
    entity = GenericForeignKey("content_type", "object_id")

    asset = models.ForeignKey(
        MediaAsset, on_delete=models.CASCADE, related_name="attachments"
    )
    category = models.CharField(max_length=50, null=True, blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["content_type", "object_id", "-is_primary", "created_at"]
        indexes = [
            models.Index(
                fields=["content_type", "object_id"],
                name="media_entitymedia_entity_idx",
            ),
        ]
        constraints = [
            # --- each asset belongs to exactly one entity ---
            models.UniqueConstraint(
                fields=["asset"],
                name="media_entitymedia_unique_asset",
            ),
            # --- at most one primary per entity per category (non-null) ---
            models.UniqueConstraint(
                fields=["content_type", "object_id", "category"],
                condition=models.Q(is_primary=True, category__isnull=False),
                name="media_entitymedia_one_primary_per_category",
            ),
            # --- at most one uncategorized primary per entity ---
            models.UniqueConstraint(
                fields=["content_type", "object_id"],
                condition=models.Q(is_primary=True, category__isnull=True),
                name="media_entitymedia_one_primary_uncategorized",
            ),
            # --- category not blank when set ---
            models.CheckConstraint(
                condition=models.Q(category__isnull=True) | ~models.Q(category=""),
                name="media_entitymedia_category_not_blank",
                violation_error_message="category must be null or non-empty.",
            ),
            # --- object_id > 0 ---
            models.CheckConstraint(
                condition=models.Q(object_id__gt=0),
                name="media_entitymedia_object_id_positive",
                violation_error_message="object_id must be greater than zero.",
            ),
        ]

    def clean(self) -> None:
        model_class = self.content_type.model_class()
        if model_class is None or not issubclass(model_class, MediaSupported):
            raise ValidationError(
                {
                    "content_type": f"Media attachments are not supported for {self.content_type}."
                }
            )

    def __str__(self) -> str:
        return f"EntityMedia {self.pk}: asset {self.asset_id} on {self.content_type_id}:{self.object_id}"
