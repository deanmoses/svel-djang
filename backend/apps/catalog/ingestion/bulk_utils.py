"""Utilities for bulk ingest operations."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from django.utils.text import slugify

if TYPE_CHECKING:
    from apps.catalog.models import Manufacturer

MAX_NAMES_SHOWN = 10


def format_names(names: list[str]) -> str:
    """Format a list of names for summary output, truncating if long."""
    if len(names) <= MAX_NAMES_SHOWN:
        return ", ".join(names)
    return ", ".join(names[:MAX_NAMES_SHOWN]) + f", ... ({len(names)} total)"


def generate_unique_slug(base_name: str, existing_slugs: set[str]) -> str:
    """Generate a unique slug, tracking used slugs in the provided set.

    Mimics the slug generation in model save() methods but works with
    bulk_create() which skips save(). Mutates ``existing_slugs`` by adding
    the generated slug so subsequent calls won't collide.
    """
    base = slugify(base_name) or "item"
    slug = base
    counter = 2
    while slug in existing_slugs:
        slug = f"{base}-{counter}"
        counter += 1
    existing_slugs.add(slug)
    return slug


# Common business suffixes stripped during normalized name matching.
# Order matters: longer suffixes first to avoid partial matches.
_BUSINESS_SUFFIXES = re.compile(
    r",?\s+(?:Manufacturing|Electronics|Industries|Enterprises"
    r"|Games|Pinball|Technologies|Company|Corporation"
    r"|Incorporated|Limited|Inc\.?|Ltd\.?|Co\.?|LLC|GmbH|S\.?A\.?|s\.?p\.?a\.?)"
    r"$",
    re.IGNORECASE,
)


def normalize_manufacturer_name(name: str) -> str:
    """Strip common business suffixes for fuzzy matching.

    >>> normalize_manufacturer_name("Bally Manufacturing")
    'bally'
    >>> normalize_manufacturer_name("WMS Industries")
    'wms'
    >>> normalize_manufacturer_name("Sega Enterprises, Ltd.")
    'sega'
    """
    stripped = _BUSINESS_SUFFIXES.sub("", name).strip()
    # Apply repeatedly for compound suffixes like "Sega Enterprises, Ltd."
    prev = None
    while stripped != prev:
        prev = stripped
        stripped = _BUSINESS_SUFFIXES.sub("", stripped).strip()
    return stripped.lower()


class ManufacturerResolver:
    """Resolve manufacturer names to slugs, auto-creating on miss.

    Caches name→slug lookups from the database at
    construction time.  Also loads CorporateEntity name→manufacturer slug
    for IPDB's 3-priority resolution cascade.

    Includes a normalized-name fallback that strips common business
    suffixes ("Manufacturing", "Inc.", etc.) and matches when unambiguous.

    All lookups are case-insensitive.
    """

    def __init__(self) -> None:
        from apps.catalog.models import CorporateEntity, Manufacturer

        self._name_to_slug: dict[str, str] = {}
        self._slug_to_mfr: dict[str, Manufacturer] = {}
        self._opdb_id_to_mfr: dict[int, Manufacturer] = {}
        self._wikidata_id_to_mfr: dict[str, Manufacturer] = {}
        self._slugs: set[str] = set()
        for m in Manufacturer.objects.all():
            self._name_to_slug[m.name.lower()] = m.slug
            self._slugs.add(m.slug)
            self._slug_to_mfr[m.slug] = m
            if m.opdb_manufacturer_id is not None:
                self._opdb_id_to_mfr[m.opdb_manufacturer_id] = m
            if m.wikidata_id:
                self._wikidata_id_to_mfr[m.wikidata_id] = m

        self._entity_to_slug: dict[str, str] = {
            ce.name.lower(): ce.manufacturer.slug
            for ce in CorporateEntity.objects.select_related("manufacturer").all()
        }

        # Normalized-name fallback: strip business suffixes.
        # Only usable when the normalized form maps to exactly one record.
        self._normalized_to_slug: dict[str, str | None] = {}
        for m in Manufacturer.objects.all():
            key = normalize_manufacturer_name(m.name)
            if key in self._normalized_to_slug:
                self._normalized_to_slug[key] = None  # ambiguous — disable
            else:
                self._normalized_to_slug[key] = m.slug

    def resolve(self, name: str) -> str | None:
        """Look up a manufacturer by name. Returns slug or None."""
        return self._name_to_slug.get(name.lower())

    def resolve_normalized(self, name: str) -> str | None:
        """Fuzzy lookup: strip business suffixes and match if unambiguous.

        Returns slug or None.  Returns None for ambiguous normalized forms.
        """
        key = normalize_manufacturer_name(name)
        return self._normalized_to_slug.get(key)

    def get_by_slug(self, slug: str) -> Manufacturer | None:
        """Look up a Manufacturer by slug. Returns instance or None."""
        return self._slug_to_mfr.get(slug)

    def get_by_opdb_id(self, opdb_id: int) -> Manufacturer | None:
        """Look up a Manufacturer by OPDB manufacturer ID. Returns instance or None."""
        return self._opdb_id_to_mfr.get(opdb_id)

    def get_by_wikidata_id(self, qid: str) -> Manufacturer | None:
        """Look up a Manufacturer by Wikidata QID. Returns instance or None."""
        return self._wikidata_id_to_mfr.get(qid)

    def resolve_object(self, name: str) -> Manufacturer | None:
        """Look up by name. Returns Manufacturer instance or None."""
        slug = self.resolve(name)
        return self._slug_to_mfr.get(slug) if slug else None

    def resolve_normalized_object(self, name: str) -> Manufacturer | None:
        """Fuzzy lookup returning the Manufacturer instance or None."""
        slug = self.resolve_normalized(name)
        return self._slug_to_mfr.get(slug) if slug else None

    def resolve_entity(self, name: str) -> str | None:
        """Look up a manufacturer via CorporateEntity name. Returns slug or None."""
        return self._entity_to_slug.get(name.lower())

    def resolve_or_create(self, name: str) -> str:
        """Look up or auto-create a manufacturer, returning its slug.

        On miss, creates a Manufacturer row and updates internal caches so
        subsequent calls with the same name won't create duplicates.
        """
        from apps.catalog.models import Manufacturer

        slug = self._name_to_slug.get(name.lower())
        if slug:
            return slug

        slug = generate_unique_slug(name, self._slugs)
        mfr = Manufacturer.objects.create(
            name=name,
            slug=slug,
        )
        self._name_to_slug[name.lower()] = slug
        self._slug_to_mfr[slug] = mfr
        return slug
