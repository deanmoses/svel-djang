"""Per-field claim revert logic."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError

from .constants import REVERT_OTHERS_MIN_EDITS
from .models import ChangeSet, ChangeSetAction, Claim


class RevertError(Exception):
    """Domain error raised by execute_revert().

    Carries a ``status_code`` so the calling view can translate to the
    appropriate HTTP response without coupling revert logic to Django Ninja.
    """

    def __init__(self, message: str, *, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def execute_revert(entity, *, claim_id: int, user, note: str) -> None:
    """Deactivate a single user claim and re-resolve the entity.

    Creates a new ChangeSet recording the revert, deactivates the target
    claim, and delegates to ``resolve_after_mutation()`` for resolution
    and cache invalidation.

    If the same user had a previous (superseded) claim for the same
    claim_key, it is re-activated so the field falls back to their
    prior value rather than dropping to the source default.

    Raises ``RevertError`` on validation or authorisation failures.
    """
    if not note or not note.strip():
        raise RevertError("A note is required when reverting.")

    ct = ContentType.objects.get_for_model(entity)

    try:
        target = Claim.objects.get(pk=claim_id, content_type=ct, object_id=entity.pk)
    except Claim.DoesNotExist:
        raise RevertError("Claim not found for this entity.", status_code=404)

    if target.source_id is not None:
        raise RevertError("Source-attributed claims cannot be reverted.")

    if not target.is_active:
        raise RevertError("This claim is already inactive.")

    if target.user_id != user.pk:
        edit_count = ChangeSet.objects.filter(user=user).count()
        if edit_count < REVERT_OTHERS_MIN_EDITS:
            raise RevertError(
                f"You need at least {REVERT_OTHERS_MIN_EDITS} edits to revert other users' changes.",
                status_code=403,
            )

    from apps.catalog.resolve import resolve_after_mutation

    try:
        with transaction.atomic():
            cs = ChangeSet.objects.create(
                user=user, action=ChangeSetAction.REVERT, note=note
            )
            target.is_active = False
            target.retracted_by_changeset = cs
            target.save(update_fields=["is_active", "retracted_by_changeset"])

            # Re-activate the most recent superseded (not retracted) claim
            # from the same user for the same claim_key.  Without this,
            # reverting a user's latest edit would leave ALL their previous
            # edits for the field inactive (because assert_claim deactivates
            # the predecessor when creating a new claim).
            predecessor = (
                Claim.objects.filter(
                    content_type=ct,
                    object_id=entity.pk,
                    user_id=target.user_id,
                    claim_key=target.claim_key,
                    is_active=False,
                    retracted_by_changeset__isnull=True,
                )
                .exclude(pk=target.pk)
                .order_by("-created_at", "-pk")
                .first()
            )
            if predecessor:
                predecessor.is_active = True
                predecessor.save(update_fields=["is_active"])

            resolve_after_mutation(entity, field_names=[target.field_name])
    except ValidationError as exc:
        raise RevertError("; ".join(exc.messages)) from exc
    except IntegrityError as exc:
        raise RevertError(f"Unique constraint violation: {exc}") from exc
