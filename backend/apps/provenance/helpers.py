"""Shared helpers for working with provenance claims."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from django.db import models
from django.db.models import Case, F, IntegerField, Prefetch, QuerySet, Value, When

from .models import CitationInstance, Claim
from .schemas import ClaimSchema


def claims_prefetch(
    to_attr: str = "active_claims",
) -> Prefetch[str, QuerySet[Claim], str]:
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


def active_claims(entity: models.Model) -> list[Claim]:
    """Return the list of active claims prefetched onto *entity*.

    Raises AssertionError if the queryset wasn't set up with
    ``claims_prefetch()``.
    """
    claims = getattr(entity, "active_claims", None)
    if claims is None:
        raise AssertionError(
            f"{type(entity).__name__} was not loaded via claims_prefetch()"
        )
    return cast(list[Claim], claims)


def citation_instances(claim: Claim) -> list[CitationInstance]:
    """Return the list of citation instances prefetched onto *claim*.

    Raises AssertionError if the claim wasn't loaded via ``claims_prefetch()``.
    """
    instances = getattr(claim, "prefetched_citation_instances", None)
    if instances is None:
        raise AssertionError(
            "Claim was not loaded via claims_prefetch(); "
            "prefetched_citation_instances is missing."
        )
    return cast(list[CitationInstance], instances)


def build_sources(claims: Iterable[Claim]) -> list[ClaimSchema]:
    """Serialize pre-fetched active claims into the sources list format.

    Claims should be ordered by claim_key, -priority, -created_at. The first
    claim seen per claim_key is marked as the winner.
    """
    winners: set[str] = set()
    sources: list[ClaimSchema] = []
    for claim in claims:
        is_winner = claim.claim_key not in winners
        if is_winner:
            winners.add(claim.claim_key)
        sources.append(
            ClaimSchema(
                source_name=claim.source.name if claim.source else None,
                source_slug=claim.source.slug if claim.source else None,
                user_display=claim.user.username if claim.user else None,
                field_name=claim.field_name,
                value=claim.value,
                citation=claim.citation,
                created_at=claim.created_at.isoformat(),
                is_winner=is_winner,
                changeset_note=claim.changeset.note if claim.changeset else None,
            )
        )
    sources.sort(key=lambda c: c.created_at, reverse=True)
    return sources
