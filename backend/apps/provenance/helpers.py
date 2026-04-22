"""Shared helpers for working with provenance claims."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.db.models import Case, F, IntegerField, Prefetch, Value, When

from .models import CitationInstance, Claim


def claims_prefetch(to_attr: str = "active_claims") -> Any:
    """Return a Prefetch for active claims with priority annotation."""
    return Prefetch(
        "claims",
        queryset=Claim.objects.filter(is_active=True)
        .exclude(source__is_enabled=False)
        .select_related("source", "user", "changeset")
        .prefetch_related(
            Prefetch(
                "citation_instances",
                queryset=CitationInstance.objects.select_related(
                    "citation_source"
                ).prefetch_related("citation_source__links"),
                to_attr="prefetched_citation_instances",
            )
        )
        .annotate(
            effective_priority=Case(
                When(source__isnull=False, then=F("source__priority")),
                When(user__isnull=False, then=F("user__profile__priority")),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("claim_key", "-effective_priority", "-created_at"),
        to_attr=to_attr,
    )


def build_sources(active_claims: Iterable[Any]) -> list[dict[str, Any]]:
    """Serialize pre-fetched active claims into the sources list format.

    Claims should be ordered by claim_key, -priority, -created_at. The first
    claim seen per claim_key is marked as the winner.
    """
    winners: set[str] = set()
    sources: list[dict[str, Any]] = []
    for claim in active_claims:
        is_winner = claim.claim_key not in winners
        if is_winner:
            winners.add(claim.claim_key)
        sources.append(
            {
                "source_name": claim.source.name if claim.source else None,
                "source_slug": claim.source.slug if claim.source else None,
                "user_display": claim.user.username if claim.user else None,
                "field_name": claim.field_name,
                "value": claim.value,
                "citation": claim.citation,
                "created_at": claim.created_at.isoformat(),
                "is_winner": is_winner,
                "changeset_note": claim.changeset.note if claim.changeset else None,
            }
        )
    sources.sort(key=lambda c: c["created_at"], reverse=True)
    return sources
