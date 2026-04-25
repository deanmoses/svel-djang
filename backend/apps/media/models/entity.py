"""EntityMedia: resolved catalog attachment linking an entity to a media asset."""

from __future__ import annotations

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedModel

from .asset import MediaAsset
from .base import MediaSupported


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
