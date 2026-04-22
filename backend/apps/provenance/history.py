"""Edit-history helpers for provenance changesets."""

from __future__ import annotations

from collections import defaultdict

from django.contrib.contenttypes.models import ContentType
from django.db.models import Case, F, IntegerField, Prefetch, Q, Value, When

from .models import ChangeSet, Claim


def _compute_winning_claim_ids(ct, entity_pk: int) -> set[int]:
    """Return the set of claim PKs that are current winners for the entity.

    For each ``claim_key``, the winner is the active claim with the highest
    ``effective_priority``, breaking ties by most recent ``created_at``, then
    highest ``pk``.
    """
    active_claims = (
        Claim.objects.filter(
            content_type=ct,
            object_id=entity_pk,
            is_active=True,
        )
        .exclude(source__is_enabled=False)
        .annotate(
            effective_priority=Case(
                When(source__isnull=False, then=F("source__priority")),
                When(user__isnull=False, then=F("user__profile__priority")),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("claim_key", "-effective_priority", "-created_at", "-pk")
    )

    winners: set[int] = set()
    seen_keys: set[str] = set()
    for claim in active_claims:
        if claim.claim_key not in seen_keys:
            seen_keys.add(claim.claim_key)
            winners.add(claim.pk)
    return winners


def build_edit_history(entity) -> list[dict]:
    """Build changeset-grouped edit history with old→new diffs for an entity.

    Returns a list of dicts matching ChangeSetSchema, newest first.
    Uses two queries to avoid N+1: one for changesets with their claims,
    one for all inactive user claims (to look up previous values).
    """
    ct = ContentType.objects.get_for_model(entity)

    # 1. Fetch changesets that have claims OR retracted_claims for this entity.
    changesets = (
        ChangeSet.objects.filter(
            Q(claims__content_type=ct, claims__object_id=entity.pk)
            | Q(
                retracted_claims__content_type=ct,
                retracted_claims__object_id=entity.pk,
            )
        )
        .distinct()
        .select_related("user")
        .prefetch_related(
            Prefetch(
                "claims",
                queryset=Claim.objects.filter(
                    content_type=ct, object_id=entity.pk
                ).order_by("field_name"),
            ),
            Prefetch(
                "retracted_claims",
                queryset=Claim.objects.filter(
                    content_type=ct, object_id=entity.pk
                ).order_by("field_name"),
            ),
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
    history: dict[tuple[str, int], list[Claim]] = defaultdict(list)
    for c in all_user_claims:
        if c.user_id is None:
            continue
        history[(c.claim_key, c.user_id)].append(c)

    # 3. Compute winning claims for is_winning.
    winning_ids = _compute_winning_claim_ids(ct, entity.pk)

    # 4. Build response.
    result: list[dict] = []
    for cs in changesets:
        changes: list[dict] = []
        for claim in cs.claims.all():
            chain = (
                history.get((claim.claim_key, claim.user_id), [])
                if claim.user_id is not None
                else []
            )
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
                    "claim_id": claim.pk,
                    "claim_user_id": claim.user_id,
                    "is_active": claim.is_active,
                    "is_winning": claim.pk in winning_ids,
                    "is_retracted": claim.retracted_by_changeset_id is not None,
                }
            )

        retractions = [
            {
                "claim_id": c.pk,
                "field_name": c.field_name,
                "claim_key": c.claim_key,
                "old_value": c.value,
            }
            for c in cs.retracted_claims.all()
        ]

        result.append(
            {
                "id": cs.pk,
                "user_display": cs.user.username if cs.user else None,
                "note": cs.note,
                "created_at": cs.created_at.isoformat(),
                "changes": changes,
                "retractions": retractions,
            }
        )
    return result
