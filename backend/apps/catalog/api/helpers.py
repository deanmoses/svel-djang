"""Shared utility functions for catalog API endpoints."""

from __future__ import annotations

from django.db.models import Prefetch

from apps.core.licensing import (
    UNKNOWN_LICENSE_RANK,
    build_source_field_license_map,
    get_minimum_display_rank,
    resolve_effective_license,
)
from apps.core.markdown import render_markdown_fields
from apps.core.markdown_links import convert_storage_to_authoring
from apps.media.models import EntityMedia
from apps.media.storage import build_public_url, build_storage_key

from ..models import GameplayFeature


# ---------------------------------------------------------------------------
# Generic serialization helpers
# ---------------------------------------------------------------------------


def _serialize_credit(credit) -> dict:
    """Serialize a Credit row into the standard CreditSchema-shaped dict."""
    return {
        "person": {"name": credit.person.name, "slug": credit.person.slug},
        "role": credit.role.slug,
        "role_display": credit.role.name,
        "role_sort_order": credit.role.display_order,
    }


def _first_thumbnail(entities_with_models, *, min_rank: int) -> str | None:
    """Return the first non-None thumbnail URL from nested entity→model prefetches."""
    for entity in entities_with_models:
        for model in entity.models.all():
            if model.extra_data:
                thumb, _ = _extract_image_urls(model.extra_data, min_rank=min_rank)
                if thumb:
                    return thumb
    return None


def _intersect_facet_sets(models, relation_name: str) -> list[dict]:
    """Return the intersection of a slug/name M2M across all *models*.

    Each model's related set is collected as ``frozenset((slug, name))``.
    Only slugs present on **every** model are included.
    Returns ``[]`` when any model has an empty set or models disagree.
    """
    sets = [
        frozenset((obj.slug, obj.name) for obj in getattr(m, relation_name).all())
        for m in models
    ]
    if not sets or not all(sets):
        return []
    common = sets[0]
    for s in sets[1:]:
        common &= s
    return [{"slug": s, "name": n} for s, n in sorted(common)] if common else []


def _serialize_title_ref(title, *, min_rank: int | None = None) -> dict:
    """Serialize a Title for use in franchise/series listing context.

    Expects *title* to have prefetched ``machine_models`` (with
    corporate_entity__manufacturer) and ``abbreviations``, plus an
    annotated ``machine_count``.
    """
    thumbnail_url = None
    manufacturer_name = None
    year = None
    first = next(iter(title.machine_models.all()), None)
    if first is not None:
        thumbnail_url, _ = _extract_image_urls(
            first.extra_data or {}, min_rank=min_rank
        )
        manufacturer_name = (
            first.corporate_entity.manufacturer.name
            if first.corporate_entity and first.corporate_entity.manufacturer
            else None
        )
        year = first.year
    return {
        "name": title.name,
        "slug": title.slug,
        "abbreviations": [a.value for a in title.abbreviations.all()],
        "machine_count": title.machine_count,
        "manufacturer_name": manufacturer_name,
        "year": year,
        "thumbnail_url": thumbnail_url,
    }


# ---------------------------------------------------------------------------
# Media helpers
# ---------------------------------------------------------------------------


def _media_prefetch():
    """Return a Prefetch for ready EntityMedia with assets."""
    return Prefetch(
        "entity_media",
        queryset=EntityMedia.objects.filter(
            asset__status="ready",
        ).select_related("asset", "asset__uploaded_by"),
        to_attr="all_media",
    )


def _serialize_uploaded_media(all_media) -> list[dict]:
    """Serialize EntityMedia rows into the uploaded_media response list."""
    return [
        {
            "asset_uuid": str(em.asset.uuid),
            "category": em.category,
            "is_primary": em.is_primary,
            "uploaded_by_username": (
                em.asset.uploaded_by.username if em.asset.uploaded_by else None
            ),
            "renditions": {
                "thumb": build_public_url(build_storage_key(em.asset.uuid, "thumb")),
                "display": build_public_url(
                    build_storage_key(em.asset.uuid, "display")
                ),
            },
        }
        for em in all_media
    ]


def _uploaded_image_urls(primary_media) -> tuple[str | None, str | None]:
    """Return (thumbnail_url, hero_image_url) from prefetched EntityMedia.

    Prefers ``backglass`` category, then falls back to any primary.
    Returns ``(None, None)`` when no uploaded media is available.
    """
    if not primary_media:
        return None, None

    # Prefer backglass, fall back to first available primary.
    chosen = None
    for em in primary_media:
        if em.category == "backglass":
            chosen = em
            break
    if chosen is None:
        chosen = primary_media[0]

    asset_uuid = chosen.asset.uuid
    thumb = build_public_url(build_storage_key(asset_uuid, "thumb"))
    hero = build_public_url(build_storage_key(asset_uuid, "display"))
    return thumb, hero


def _extract_image_urls(
    extra_data: dict,
    primary_media=None,
    *,
    min_rank: int | None = None,
) -> tuple[str | None, str | None]:
    """Return (thumbnail_url, hero_image_url).

    When *primary_media* (prefetched ``EntityMedia`` rows) contains uploaded
    images, those are used unconditionally (no license gating — Pinbase owns
    them).  Otherwise falls back to third-party images in *extra_data*,
    respecting the global Constance display threshold.

    Pass *min_rank* to avoid repeated Constance DB lookups in tight loops.
    """
    # Uploaded media always wins — no license gating.
    thumb, hero = _uploaded_image_urls(primary_media)
    if thumb or hero:
        return thumb, hero

    if min_rank is None:
        min_rank = get_minimum_display_rank()

    def _rank_ok(key: str) -> bool:
        rank = extra_data.get(f"{key}.__permissiveness_rank")
        effective = rank if rank is not None else UNKNOWN_LICENSE_RANK
        return effective >= min_rank

    def _abs(url: str | None) -> str | None:
        """Return *url* only if it's an absolute HTTP(S) URL, else None."""
        if url and (url.startswith("http://") or url.startswith("https://")):
            return url
        return None

    # Try OPDB structured images first (have size variants).
    images = extra_data.get("opdb.images")
    if images and isinstance(images, list) and _rank_ok("opdb.images"):
        img = None
        for candidate in images:
            if isinstance(candidate, dict) and candidate.get("primary"):
                img = candidate
                break
        if img is None:
            img = images[0] if images else None
        if isinstance(img, dict):
            urls = img.get("urls") or {}
            thumbnail = _abs(urls.get("medium") or urls.get("small"))
            hero = _abs(urls.get("large") or urls.get("medium"))
            if thumbnail or hero:
                return thumbnail, hero

    # Fall back to flat URL list (IPDB-sourced or scraped).
    for key in ("ipdb.image_urls", "image_urls"):
        image_urls = extra_data.get(key)
        if image_urls and isinstance(image_urls, list) and _rank_ok(key):
            first = image_urls[0]
            if isinstance(first, str) and _abs(first):
                return first, first

    return None, None


def _extract_image_attribution(extra_data: dict, primary_media=None) -> dict | None:
    """Return AttributionSchema-shaped dict for the displayed image, or None.

    When uploaded media is being used (determined by *primary_media*), returns
    ``None`` — no third-party license to cite.  Otherwise checks each external
    image source in priority order and returns info for the first source that
    passes the display threshold.
    """
    # Uploaded media has no third-party attribution.
    if primary_media:
        return None

    min_rank = get_minimum_display_rank()

    for key in ("opdb.images", "ipdb.image_urls", "image_urls"):
        data = extra_data.get(key)
        if not data:
            continue
        rank = extra_data.get(f"{key}.__permissiveness_rank")
        effective = rank if rank is not None else UNKNOWN_LICENSE_RANK
        if effective >= min_rank:
            return {
                "license_slug": extra_data.get(f"{key}.__license_slug"),
                "permissiveness_rank": rank,
            }

    return None


def _extract_description_attribution(active_claims) -> dict | None:
    """Return AttributionSchema-shaped dict for the winning description claim, or None.

    Expects active_claims to be ordered by claim_key, -priority, -created_at
    (the standard prefetch ordering).
    """
    sfl_map = None
    for claim in active_claims:
        if claim.field_name == "description":
            if sfl_map is None:
                sfl_map = build_source_field_license_map()
            lic = resolve_effective_license(claim, sfl_map)
            return {
                "license_slug": lic.slug if lic else None,
                "license_name": lic.short_name if lic else None,
                "license_url": lic.url if lic else None,
                "permissiveness_rank": (lic.permissiveness_rank if lic else None),
                "requires_attribution": (lic.requires_attribution if lic else False),
                "source_name": claim.source.name if claim.source else None,
                "source_url": claim.source.url if claim.source else None,
                "attribution_text": claim.citation or None,
            }
    return None


def _build_rich_text(obj, field_name: str, active_claims=None) -> dict:
    """Build a RichTextSchema-shaped dict for a text field with attribution.

    Reads the raw text from obj.{field_name}, renders HTML via
    render_markdown_fields, and extracts attribution from the winning claim.

    The ``text`` value is returned in authoring format (``[[type:slug]]``)
    so edit forms show human-readable link references.  The ``html`` value
    is rendered from the storage format and is display-ready.
    """
    raw_text = getattr(obj, field_name, "") or ""
    text = convert_storage_to_authoring(raw_text) if raw_text else raw_text
    html_fields = render_markdown_fields(obj)
    html = html_fields.get(f"{field_name}_html", "")
    citations = html_fields.get(f"{field_name}_citations", [])

    attribution = None
    if active_claims is not None:
        attribution = _extract_description_attribution(active_claims)

    return {
        "text": text,
        "html": html,
        "citations": citations,
        "attribution": attribution,
    }


def _collect_titles(models, *, include_manufacturer: bool = False) -> list[dict]:
    """Group models by title into a deduplicated title list."""
    min_rank = get_minimum_display_rank()
    titles: dict[str, dict] = {}
    for m in models:
        if m.title is None:
            continue
        key = m.title.slug
        if key not in titles:
            thumbnail_url = _extract_image_urls(m.extra_data or {}, min_rank=min_rank)[
                0
            ]
            entry: dict = {
                "name": m.title.name,
                "slug": m.title.slug,
                "year": m.year,
                "thumbnail_url": thumbnail_url,
            }
            if include_manufacturer:
                mfr = (
                    m.corporate_entity.manufacturer
                    if m.corporate_entity and m.corporate_entity.manufacturer
                    else None
                )
                entry["manufacturer_name"] = mfr.name if mfr else None
            titles[key] = entry
        elif titles[key]["thumbnail_url"] is None:
            thumbnail_url = _extract_image_urls(m.extra_data or {}, min_rank=min_rank)[
                0
            ]
            if thumbnail_url:
                titles[key]["thumbnail_url"] = thumbnail_url
    return sorted(titles.values(), key=lambda t: (t["year"] is None, -(t["year"] or 0)))


def _location_ancestors(loc) -> list[dict]:
    """Return ancestor locations from immediate parent up to root, in order."""
    ancestors = []
    current = loc.parent
    while current is not None:
        ancestors.append(
            {
                "display_name": current.short_name or current.name,
                "location_path": current.location_path,
            }
        )
        current = current.parent
    return ancestors


def _serialize_locations(entity) -> list[dict]:
    """Serialize CorporateEntityLocation rows with ancestor chains."""
    return [
        {
            "location_path": cel.location.location_path,
            "location_type": cel.location.location_type,
            "display_name": cel.location.short_name or cel.location.name,
            "slug": cel.location.slug,
            "ancestors": _location_ancestors(cel.location),
        }
        for cel in entity.locations.all()
    ]


def _extract_variant_features(extra_data: dict) -> list[str]:
    """Return variant feature list from extra_data variant_features claim."""
    features = extra_data.get("opdb.variant_features")
    if not features or not isinstance(features, list):
        return []
    return [str(f) for f in features]


def _get_feature_descendant_slugs(slug: str) -> set[str]:
    """Return *slug* plus all transitive child feature slugs.

    Two queries: one for all features, one for the children M2M.  The BFS
    then runs entirely in Python.  For a leaf feature this returns {slug}.
    For an unknown slug it still returns {slug} (the filter just won't match).
    """
    features = list(
        GameplayFeature.objects.prefetch_related("children").only("pk", "slug")
    )
    children_map: dict[str, list[str]] = {
        f.slug: [c.slug for c in f.children.all()] for f in features
    }
    result: set[str] = {slug}
    stack = [slug]
    while stack:
        current = stack.pop()
        for child_slug in children_map.get(current, []):
            if child_slug not in result:
                result.add(child_slug)
                stack.append(child_slug)
    return result


def _serialize_title_machine(pm, *, min_rank: int | None = None) -> dict:
    """Serialize a MachineModel for use in title/theme/system machine lists."""
    if min_rank is None:
        min_rank = get_minimum_display_rank()

    thumbnail_url, _ = _extract_image_urls(pm.extra_data or {}, min_rank=min_rank)

    # Include variants only when prefetched to avoid N+1 queries.
    variant_qs = (
        pm.variants.all()
        if "variants" in getattr(pm, "_prefetched_objects_cache", {})
        else []
    )
    variants = [
        {
            "name": v.name,
            "slug": v.slug,
            "year": v.year,
            "thumbnail_url": _extract_image_urls(v.extra_data or {}, min_rank=min_rank)[
                0
            ],
        }
        for v in variant_qs
    ]

    mfr = (
        pm.corporate_entity.manufacturer
        if pm.corporate_entity and pm.corporate_entity.manufacturer
        else None
    )
    return {
        "name": pm.name,
        "slug": pm.slug,
        "year": pm.year,
        "manufacturer": {"name": mfr.name, "slug": mfr.slug} if mfr else None,
        "technology_generation_name": (
            pm.technology_generation.name if pm.technology_generation else None
        ),
        "thumbnail_url": thumbnail_url,
        "variants": variants,
    }
