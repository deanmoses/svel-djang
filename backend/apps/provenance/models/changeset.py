"""ChangeSet model: grouped edit sessions."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models.functions import Now


class ChangeSet(models.Model):
    """A grouped edit session that links related claims.

    A ChangeSet is a thin grouping record, not a snapshot of entity state.
    Truth is always derived from claim resolution (highest priority wins).
    Reverting a claim means deactivating it and re-resolving — the
    resolution machinery picks the correct winner from whatever remains.

    All claims in a ChangeSet must share the same actor (same user or same
    source). A CheckConstraint enforces that exactly one of user or
    ingest_run is set; same-actor consistency within those groups is
    enforced by assert_claim().
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="changesets",
        null=True,
        blank=True,
        help_text="The user who made this edit. Null for source-level changesets.",
    )
    ingest_run = models.ForeignKey(
        "provenance.IngestRun",
        on_delete=models.PROTECT,
        related_name="changesets",
        null=True,
        blank=True,
        help_text="The ingest run that produced this changeset. Null for user edits.",
    )
    note = models.TextField(
        blank=True,
        default="",
        help_text="Optional free-text note explaining the edit.",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "-created_at"],
                name="provenance_cs_user_created",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(user__isnull=False, ingest_run__isnull=True)
                    | models.Q(user__isnull=True, ingest_run__isnull=False)
                ),
                name="provenance_changeset_user_xor_ingest_run",
            ),
        ]

    def __str__(self) -> str:
        if self.user_id:
            actor = self.user.username
        else:
            actor = f"ingest:{self.ingest_run.source.name}"
        return f"ChangeSet #{self.pk} by {actor}"
