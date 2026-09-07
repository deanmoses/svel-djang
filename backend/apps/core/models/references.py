"""RecordReference graph: tracks links between records for 'what links here'."""

from __future__ import annotations

from typing import override

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models.signals import post_delete


class RecordReference(models.Model):
    """Tracks links between records for 'what links here' queries.

    Uses Django's contenttypes framework for polymorphic source/target.
    GenericForeignKey doesn't support on_delete, so all target deletions
    are allowed. Broken links render as 'broken link' text.
    """

    # Source (the record containing the link)
    source_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="+"
    )
    source_id = models.PositiveBigIntegerField()
    source = GenericForeignKey("source_type", "source_id")

    # Target (the record being linked to)
    target_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="+"
    )
    target_id = models.PositiveBigIntegerField()
    target = GenericForeignKey("target_type", "target_id")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source_type", "source_id", "target_type", "target_id"],
                name="core_recordreference_unique_source_target",
            ),
        ]
        indexes = [
            models.Index(fields=["target_type", "target_id"]),  # "What links here"
            models.Index(fields=["source_type", "source_id"]),  # Cleanup on delete
        ]

    @override
    def __str__(self) -> str:
        return (
            f"{self.source_type.model}:{self.source_id}"
            f" → {self.target_type.model}:{self.target_id}"
        )


def register_reference_cleanup(*model_classes: type[models.Model]) -> None:
    """Connect post_delete signals to clean up RecordReference rows for the given models.

    Call from AppConfig.ready() for every model whose text fields can contain
    ``[[<entity-type>:<public-id>]]`` markdown links (i.e. any model passed to ``sync_references``).
    """

    def _cleanup_references(
        sender: type[models.Model], instance: models.Model, **kwargs: object
    ) -> None:
        ct = ContentType.objects.get_for_model(sender)
        RecordReference.objects.filter(source_type=ct, source_id=instance.pk).delete()

    for model_class in model_classes:
        post_delete.connect(
            _cleanup_references,
            sender=model_class,
            dispatch_uid=f"cleanup_refs_{model_class._meta.label_lower}",
        )
