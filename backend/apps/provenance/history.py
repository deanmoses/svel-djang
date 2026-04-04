"""Edit-history helpers for provenance changesets."""

from __future__ import annotations

from collections import defaultdict

from django.contrib.contenttypes.models import ContentType
from django.db.models import Prefetch

from .models import ChangeSet, Claim


def build_edit_history(entity) -> list[dict]:
    """Build changeset-grouped edit history with old→new diffs for an entity.

    Returns a list of dicts matching ChangeSetSchema, newest first.
    Uses two queries to avoid N+1: one for changesets with their claims,
    one for all inactive user claims (to look up previous values).
    """
    ct = ContentType.objects.get_for_model(entity)

    # 1. Fetch changesets that have claims for this entity.
    changesets = (
        ChangeSet.objects.filter(
            claims__content_type=ct,
            claims__object_id=entity.pk,
        )
        .distinct()
        .select_related("user")
        .prefetch_related(
            Prefetch(
                "claims",
                queryset=Claim.objects.filter(
                    content_type=ct, object_id=entity.pk
                ).order_by("field_name"),
            )
        )
        .order_by("-created_at")
    )

    # 2. Fetch ALL user claims for this entity (active + inactive) to build
    #    a history chain for old-value lookups.
    all_user_claims = list(
        Claim.objects.filter(
            content_type=ct,
            object_id=entity.pk,
            user__isnull=False,
        ).order_by("claim_key", "user_id", "-created_at")
    )

    # Build lookup: (claim_key, user_id) → list of claims ordered newest-first.
    history: dict[tuple[str, int], list] = defaultdict(list)
    for c in all_user_claims:
        history[(c.claim_key, c.user_id)].append(c)

    # 3. Build response.
    result: list[dict] = []
    for cs in changesets:
        changes: list[dict] = []
        for claim in cs.claims.all():
            chain = history.get((claim.claim_key, claim.user_id), [])
            old_value = None
            for i, c in enumerate(chain):
                if c.pk == claim.pk and i + 1 < len(chain):
                    old_value = chain[i + 1].value
                    break
            changes.append(
                {
                    "field_name": claim.field_name,
                    "claim_key": claim.claim_key,
                    "old_value": old_value,
                    "new_value": claim.value,
                }
            )
        result.append(
            {
                "id": cs.pk,
                "user_display": cs.user.username if cs.user else None,
                "note": cs.note,
                "created_at": cs.created_at.isoformat(),
                "changes": changes,
            }
        )
    return result
