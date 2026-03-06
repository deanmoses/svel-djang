"""Shared utility functions for catalog API endpoints."""

from __future__ import annotations

from django.db.models import Case, F, IntegerField, Prefetch, Value, When


def _build_activity(active_claims) -> list[dict]:
    """Serialize pre-fetched active claims into the activity list format.

    Claims should be ordered by claim_key, -priority, -created_at. The first
    claim seen per claim_key is marked as the winner.
    """
    winners: set[str] = set()
    activity: list[dict] = []
    for claim in active_claims:
        is_winner = claim.claim_key not in winners
        if is_winner:
            winners.add(claim.claim_key)
        activity.append(
            {
                "source_name": claim.source.name if claim.source else None,
                "source_slug": claim.source.slug if claim.source else None,
                "user_display": claim.user.username if claim.user else None,
                "field_name": claim.field_name,
                "value": claim.value,
                "citation": claim.citation,
                "created_at": claim.created_at.isoformat(),
                "is_winner": is_winner,
            }
        )
    activity.sort(key=lambda c: c["created_at"], reverse=True)
    return activity


def _claims_prefetch(to_attr: str = "active_claims"):
    """Return a Prefetch for active claims with priority annotation."""
    from apps.provenance.models import Claim

    return Prefetch(
        "claims",
        queryset=Claim.objects.filter(is_active=True)
        .select_related("source", "user")
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


def _extract_image_urls(extra_data: dict) -> tuple[str | None, str | None]:
    """Return (thumbnail_url, hero_image_url) from extra_data.

    Tries OPDB structured images first (with size variants), then falls back
    to IPDB flat URL list (same URL used for both thumbnail and hero).
    """
    # Try OPDB structured images first (have size variants).
    images = extra_data.get("images")
    if images and isinstance(images, list):
        img = None
        for candidate in images:
            if isinstance(candidate, dict) and candidate.get("primary"):
                img = candidate
                break
        if img is None:
            img = images[0] if images else None
        if isinstance(img, dict):
            urls = img.get("urls") or {}
            thumbnail = urls.get("medium") or urls.get("small")
            hero = urls.get("large") or urls.get("medium")
            if thumbnail or hero:
                return thumbnail, hero

    # Fall back to IPDB flat URL list.
    image_urls = extra_data.get("image_urls")
    if image_urls and isinstance(image_urls, list):
        first = image_urls[0]
        if isinstance(first, str) and first:
            return first, first

    return None, None


def _extract_variant_features(extra_data: dict) -> list[str]:
    """Return variant feature list from extra_data variant_features claim."""
    features = extra_data.get("variant_features")
    if not features or not isinstance(features, list):
        return []
    return [str(f) for f in features]


def _serialize_title_machine(pm) -> dict:
    """Serialize a MachineModel for use in title/theme/system machine lists."""
    thumbnail_url, _ = _extract_image_urls(pm.extra_data or {})
    return {
        "name": pm.name,
        "slug": pm.slug,
        "year": pm.year,
        "manufacturer_name": pm.manufacturer.name if pm.manufacturer else None,
        "manufacturer_slug": pm.manufacturer.slug if pm.manufacturer else None,
        "technology_generation_name": (
            pm.technology_generation.name if pm.technology_generation else None
        ),
        "thumbnail_url": thumbnail_url,
    }
