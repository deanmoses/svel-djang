"""Tests for ManufacturerResolver shared utility."""

from __future__ import annotations

import pytest

from apps.catalog.ingestion.bulk_utils import (
    ManufacturerResolver,
    normalize_manufacturer_name,
)
from apps.catalog.models import CorporateEntity, Manufacturer


@pytest.mark.django_db
class TestManufacturerResolver:
    def test_resolve_by_name(self):
        Manufacturer.objects.create(name="Williams", slug="williams")
        resolver = ManufacturerResolver()
        assert resolver.resolve("Williams") == "williams"

    def test_resolve_case_insensitive(self):
        Manufacturer.objects.create(name="Gottlieb", slug="gottlieb")
        resolver = ManufacturerResolver()
        assert resolver.resolve("GOTTLIEB") == "gottlieb"
        assert resolver.resolve("gottlieb") == "gottlieb"

    def test_resolve_unknown_returns_none(self):
        resolver = ManufacturerResolver()
        assert resolver.resolve("Nonexistent") is None

    def test_resolve_entity(self):
        mfr = Manufacturer.objects.create(name="Williams", slug="williams")
        CorporateEntity.objects.create(
            name="Williams Electronic Games",
            manufacturer=mfr,
        )
        resolver = ManufacturerResolver()
        assert resolver.resolve_entity("Williams Electronic Games") == "williams"

    def test_resolve_entity_unknown_returns_none(self):
        resolver = ManufacturerResolver()
        assert resolver.resolve_entity("Nonexistent Corp") is None

    def test_resolve_or_create_existing(self):
        Manufacturer.objects.create(name="Stern", slug="stern")
        resolver = ManufacturerResolver()
        assert resolver.resolve_or_create("Stern") == "stern"
        # No new manufacturer created.
        assert Manufacturer.objects.count() == 1

    def test_resolve_or_create_new(self):
        resolver = ManufacturerResolver()
        slug = resolver.resolve_or_create("Jersey Jack")
        assert slug == "jersey-jack"
        mfr = Manufacturer.objects.get(slug=slug)
        assert mfr.name == "Jersey Jack"

    def test_resolve_or_create_caches_result(self):
        resolver = ManufacturerResolver()
        slug1 = resolver.resolve_or_create("Spooky Pinball")
        slug2 = resolver.resolve_or_create("Spooky Pinball")
        assert slug1 == slug2
        assert Manufacturer.objects.filter(name="Spooky Pinball").count() == 1

    def test_resolve_or_create_handles_slug_collision(self):
        Manufacturer.objects.create(name="Acme", slug="acme")
        resolver = ManufacturerResolver()
        # Creating another "Acme" should get a unique slug.
        slug = resolver.resolve_or_create("Acme Corp")
        assert slug != "acme"
        assert Manufacturer.objects.count() == 2

    # --- resolve_normalized ---

    def test_resolve_normalized_strips_suffix(self):
        Manufacturer.objects.create(name="Bally", slug="bally")
        resolver = ManufacturerResolver()
        assert resolver.resolve_normalized("Bally Manufacturing") == "bally"

    def test_resolve_normalized_compound_suffix(self):
        Manufacturer.objects.create(name="Sega", slug="sega")
        resolver = ManufacturerResolver()
        assert resolver.resolve_normalized("Sega Enterprises, Ltd.") == "sega"

    def test_resolve_normalized_ambiguous_returns_none(self):
        Manufacturer.objects.create(name="Acme", slug="acme")
        Manufacturer.objects.create(name="Acme Games", slug="acme-games")
        resolver = ManufacturerResolver()
        # Both normalize to "acme", so the lookup is ambiguous.
        assert resolver.resolve_normalized("Acme Industries") is None

    def test_resolve_normalized_no_match(self):
        resolver = ManufacturerResolver()
        assert resolver.resolve_normalized("Nonexistent Manufacturing") is None

    # --- resolve_object ---

    def test_resolve_object_returns_instance(self):
        mfr = Manufacturer.objects.create(name="Stern", slug="stern")
        resolver = ManufacturerResolver()
        result = resolver.resolve_object("Stern")
        assert result is not None
        assert result.pk == mfr.pk

    def test_resolve_object_unknown_returns_none(self):
        resolver = ManufacturerResolver()
        assert resolver.resolve_object("Nonexistent") is None

    # --- resolve_normalized_object ---

    def test_resolve_normalized_object_returns_instance(self):
        mfr = Manufacturer.objects.create(name="WMS", slug="wms")
        resolver = ManufacturerResolver()
        result = resolver.resolve_normalized_object("WMS Industries")
        assert result is not None
        assert result.pk == mfr.pk

    def test_resolve_normalized_object_ambiguous_returns_none(self):
        Manufacturer.objects.create(name="Acme", slug="acme")
        Manufacturer.objects.create(name="Acme Games", slug="acme-games")
        resolver = ManufacturerResolver()
        assert resolver.resolve_normalized_object("Acme Industries") is None

    # --- resolve_or_create populates slug_to_mfr cache ---

    def test_resolve_or_create_populates_object_cache(self):
        resolver = ManufacturerResolver()
        slug = resolver.resolve_or_create("New Mfr")
        result = resolver.resolve_object("New Mfr")
        assert result is not None
        assert result.slug == slug


class TestNormalizeManufacturerName:
    def test_simple_suffix(self):
        assert normalize_manufacturer_name("Bally Manufacturing") == "bally"

    def test_multiple_suffixes(self):
        assert normalize_manufacturer_name("WMS Industries") == "wms"

    def test_compound_suffix(self):
        assert normalize_manufacturer_name("Sega Enterprises, Ltd.") == "sega"

    def test_no_suffix(self):
        assert normalize_manufacturer_name("Stern") == "stern"

    def test_inc_suffix(self):
        assert normalize_manufacturer_name("Gottlieb Inc.") == "gottlieb"

    def test_gmbh_suffix(self):
        assert normalize_manufacturer_name("Löwen GmbH") == "löwen"

    def test_incorporated_suffix(self):
        assert normalize_manufacturer_name("Stern Pinball, Incorporated") == "stern"

    def test_limited_suffix(self):
        assert normalize_manufacturer_name("Data East Limited") == "data east"

    def test_preserves_core_name(self):
        assert normalize_manufacturer_name("Jersey Jack Pinball") == "jersey jack"
