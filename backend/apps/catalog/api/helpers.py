"""Shared utility functions for catalog API endpoints."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from django.db.models import Model, Prefetch

from apps.core.licensing import (
    UNKNOWN_LICENSE_RANK,
    build_source_field_license_map,
    get_minimum_display_rank,
    resolve_effective_license,
)
from apps.core.markdown import render_markdown_field
from apps.core.markdown_links import convert_storage_to_authoring
from apps.core.types import JsonData
from apps.media.models import EntityMedia
from apps.media.schemas import MediaRenditionsSchema, UploadedMediaSchema
from apps.media.storage import build_public_url, build_storage_key
from apps.provenance.models import Claim
from apps.provenance.schemas import (
    AttributionSchema,
    InlineCitationSchema,
    RichTextSchema,
)

from ..models import (
    CorporateEntity,
    Credit,
    GameplayFeature,
    Location,
    MachineModel,
    Title,
)
from .schemas import (
    CorporateEntityLocationAncestorRef,
    CorporateEntityLocationSchema,
    CreditSchema,
    EntityRef,
    RelatedTitleSchema,
    TitleModelSchema,
    TitleModelVariantSchema,
    TitleRef,
)

# ---------------------------------------------------------------------------
# Generic serialization helpers
# ---------------------------------------------------------------------------


def _serialize_credit(credit: Credit) -> CreditSchema:
    """Serialize a Credit row into a CreditSchema."""
    return CreditSchema(
        person=EntityRef(name=credit.person.name, slug=credit.person.slug),
        role=credit.role.slug,
        role_display=credit.role.name,
        role_sort_order=credit.role.display_order,
    )


def _first_thumbnail(
    entities_with_models: Iterable[CorporateEntity], *, min_rank: int
) -> str | None:
    """Return the first non-None thumbnail URL from nested entity→model prefetches."""
    for entity in entities_with_models:
        for model in entity.models.all():
            if model.extra_data:
                thumb, _ = _extract_image_urls(model.extra_data, min_rank=min_rank)
                if thumb:
                    return thumb
    return None


def _intersect_facet_sets(
    models: Iterable[Model], relation_name: str
) -> list[EntityRef]:
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
    return [EntityRef(slug=s, name=n) for s, n in sorted(common)] if common else []


def _serialize_title_ref(title: Title, *, min_rank: int | None = None) -> TitleRef:
    """Serialize a Title for use in franchise/series listing context.

    Expects *title* to have prefetched ``machine_models`` (with
    corporate_entity__manufacturer) and ``abbreviations``, plus an
    annotated ``model_count``.
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
    return TitleRef(
        name=title.name,
        slug=title.slug,
        abbreviations=[a.value for a in title.abbreviations.all()],
        # model_count is a queryset .annotate() attribute, not on Title itself.
        model_count=getattr(title, "model_count", 0),
        manufacturer_name=manufacturer_name,
        year=year,
        thumbnail_url=thumbnail_url,
    )


# ---------------------------------------------------------------------------
# Media helpers
# ---------------------------------------------------------------------------


# Slot 2 is Any because prefetch_related has a single _PrefetchedQuerySetT
# TypeVar it must unify across all heterogeneous Prefetch args at the call
# site; any concrete queryset type here breaks that unification. The Any
# is an artifact of django-stubs' API design, not lost information.
def _media_prefetch() -> Prefetch[str, Any, str]:
    """Return a Prefetch for ready EntityMedia with assets."""
    return Prefetch(
        "entity_media",
        queryset=EntityMedia.objects.filter(
            asset__status="ready",
        ).select_related("asset", "asset__uploaded_by"),
        to_attr="all_media",
    )


def _serialize_uploaded_media(
    all_media: Iterable[EntityMedia],
) -> list[UploadedMediaSchema]:
    """Serialize EntityMedia rows into the uploaded_media response list."""
    return [
        UploadedMediaSchema(
            asset_uuid=str(em.asset.uuid),
            category=em.category,
            is_primary=em.is_primary,
            uploaded_by_username=(
                em.asset.uploaded_by.username if em.asset.uploaded_by else None
            ),
            renditions=MediaRenditionsSchema(
                thumb=build_public_url(build_storage_key(em.asset.uuid, "thumb")),
                display=build_public_url(build_storage_key(em.asset.uuid, "display")),
            ),
        )
        for em in all_media
    ]


def _uploaded_image_urls(
    primary_media: Sequence[EntityMedia] | None,
) -> tuple[str | None, str | None]:
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
    extra_data: JsonData,
    primary_media: Sequence[EntityMedia] | None = None,
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
        effective = rank if isinstance(rank, int) else UNKNOWN_LICENSE_RANK
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


def _extract_image_attribution(
    extra_data: JsonData,
    primary_media: Sequence[EntityMedia] | None = None,
) -> AttributionSchema | None:
    """Return AttributionSchema for the displayed image, or None.

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
        rank_raw = extra_data.get(f"{key}.__permissiveness_rank")
        rank = rank_raw if isinstance(rank_raw, int) else None
        effective = rank if rank is not None else UNKNOWN_LICENSE_RANK
        if effective >= min_rank:
            license_slug_raw = extra_data.get(f"{key}.__license_slug")
            license_slug = (
                license_slug_raw if isinstance(license_slug_raw, str) else None
            )
            return AttributionSchema(
                license_slug=license_slug,
                permissiveness_rank=rank,
            )

    return None


def _extract_description_attribution(
    active_claims: Iterable[Claim],
) -> AttributionSchema | None:
    """Return AttributionSchema for the winning description claim, or None.

    Expects active_claims to be ordered by claim_key, -priority, -created_at
    (the standard prefetch ordering).
    """
    sfl_map = None
    for claim in active_claims:
        if claim.field_name == "description":
            if sfl_map is None:
                sfl_map = build_source_field_license_map()
            lic = resolve_effective_license(claim, sfl_map)
            return AttributionSchema(
                license_slug=lic.slug if lic else None,
                license_name=lic.short_name if lic else None,
                license_url=lic.url if lic else None,
                permissiveness_rank=lic.permissiveness_rank if lic else None,
                requires_attribution=lic.requires_attribution if lic else False,
                source_name=claim.source.name if claim.source else None,
                source_url=claim.source.url if claim.source else None,
                attribution_text=claim.citation or None,
            )
    return None


def _build_rich_text(
    obj: Model,
    field_name: str,
    active_claims: Iterable[Claim] | None = None,
) -> RichTextSchema:
    """Build a RichTextSchema for a text field with attribution.

    Reads the raw text from obj.{field_name}, renders HTML via
    render_markdown_field, and extracts attribution from the winning claim.

    The ``text`` value is returned in authoring format (``[[type:slug]]``)
    so edit forms show human-readable link references.  The ``html`` value
    is rendered from the storage format and is display-ready.
    """
    raw_text = getattr(obj, field_name, "") or ""
    text = convert_storage_to_authoring(raw_text) if raw_text else raw_text
    rendered = render_markdown_field(obj, field_name)
    citations = [InlineCitationSchema.model_validate(c) for c in rendered.citations]

    attribution = None
    if active_claims is not None:
        attribution = _extract_description_attribution(active_claims)

    return RichTextSchema(
        text=text,
        html=rendered.html,
        citations=citations,
        attribution=attribution,
    )


def _collect_titles(
    models: Iterable[MachineModel], *, include_manufacturer: bool = False
) -> list[RelatedTitleSchema]:
    """Group models by title into a deduplicated title list."""
    min_rank = get_minimum_display_rank()
    titles: dict[str, RelatedTitleSchema] = {}
    for m in models:
        if m.title is None:
            continue
        key = m.title.slug
        if key not in titles:
            thumbnail_url = _extract_image_urls(m.extra_data or {}, min_rank=min_rank)[
                0
            ]
            manufacturer_name = None
            if include_manufacturer:
                mfr = (
                    m.corporate_entity.manufacturer
                    if m.corporate_entity and m.corporate_entity.manufacturer
                    else None
                )
                manufacturer_name = mfr.name if mfr else None
            titles[key] = RelatedTitleSchema(
                name=m.title.name,
                slug=m.title.slug,
                year=m.year,
                thumbnail_url=thumbnail_url,
                manufacturer_name=manufacturer_name,
            )
        elif titles[key].thumbnail_url is None:
            thumbnail_url = _extract_image_urls(m.extra_data or {}, min_rank=min_rank)[
                0
            ]
            if thumbnail_url:
                titles[key].thumbnail_url = thumbnail_url
    return sorted(titles.values(), key=lambda t: (t.year is None, -(t.year or 0)))


def _location_ancestors(loc: Location) -> list[CorporateEntityLocationAncestorRef]:
    """Return ancestor locations from immediate parent up to root, in order."""
    ancestors: list[CorporateEntityLocationAncestorRef] = []
    current = loc.parent
    while current is not None:
        ancestors.append(
            CorporateEntityLocationAncestorRef(
                display_name=current.short_name or current.name,
                location_path=current.location_path,
            )
        )
        current = current.parent
    return ancestors


def _serialize_locations(
    entity: CorporateEntity,
) -> list[CorporateEntityLocationSchema]:
    """Serialize CorporateEntityLocation rows with ancestor chains."""
    return [
        CorporateEntityLocationSchema(
            location_path=cel.location.location_path,
            location_type=cel.location.location_type,
            display_name=cel.location.short_name or cel.location.name,
            slug=cel.location.slug,
            ancestors=_location_ancestors(cel.location),
        )
        for cel in entity.locations.all()
    ]


def _extract_variant_features(extra_data: JsonData) -> list[str]:
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


def _serialize_title_machine(
    pm: MachineModel, *, min_rank: int | None = None
) -> TitleModelSchema:
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
        TitleModelVariantSchema(
            name=v.name,
            slug=v.slug,
            year=v.year,
            thumbnail_url=_extract_image_urls(v.extra_data or {}, min_rank=min_rank)[0],
        )
        for v in variant_qs
    ]

    mfr = (
        pm.corporate_entity.manufacturer
        if pm.corporate_entity and pm.corporate_entity.manufacturer
        else None
    )
    return TitleModelSchema(
        name=pm.name,
        slug=pm.slug,
        year=pm.year,
        manufacturer=EntityRef(name=mfr.name, slug=mfr.slug) if mfr else None,
        technology_generation_name=(
            pm.technology_generation.name if pm.technology_generation else None
        ),
        thumbnail_url=thumbnail_url,
        variants=variants,
    )
