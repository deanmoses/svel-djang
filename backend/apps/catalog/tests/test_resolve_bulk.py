"""Tests for _resolve_bulk and resolve_title."""

import pytest
from django.contrib.contenttypes.models import ContentType

from apps.catalog.models import Franchise, Manufacturer, System, Tag, Title
from apps.catalog.resolve import (
    MANUFACTURER_DIRECT_FIELDS,
    TAXONOMY_DIRECT_FIELDS,
    TITLE_DIRECT_FIELDS,
    _resolve_bulk,
    resolve_title,
)
from apps.core.models import RecordReference
from apps.provenance.models import Claim, Source


@pytest.fixture
def opdb():
    return Source.objects.create(
        name="OPDB", slug="opdb", source_type="database", priority=200
    )


@pytest.fixture
def editorial():
    return Source.objects.create(
        name="Editorial", slug="editorial", source_type="editorial", priority=300
    )


@pytest.mark.django_db
class TestResolveBulkTitle:
    def test_resolves_multiple_titles(self, opdb):
        t1 = Title.objects.create(opdb_id="G1", name="", slug="t1")
        t2 = Title.objects.create(opdb_id="G2", name="", slug="t2")

        Claim.objects.assert_claim(t1, "name", "Godzilla", source=opdb)
        Claim.objects.assert_claim(t2, "name", "Blackout", source=opdb)

        _resolve_bulk(Title, TITLE_DIRECT_FIELDS)

        t1.refresh_from_db()
        t2.refresh_from_db()
        assert t1.name == "Godzilla"
        assert t2.name == "Blackout"

    def test_winner_by_priority(self, opdb, editorial):
        t = Title.objects.create(opdb_id="G1", name="", slug="t1")

        Claim.objects.assert_claim(t, "name", "Low Priority", source=opdb)
        Claim.objects.assert_claim(t, "name", "High Priority", source=editorial)

        _resolve_bulk(Title, TITLE_DIRECT_FIELDS)

        t.refresh_from_db()
        assert t.name == "High Priority"

    def test_no_claims_resets_to_default(self, opdb):
        t = Title.objects.create(opdb_id="G1", name="Stale Name", slug="t1")

        # No claims — resolution should blank the name.
        _resolve_bulk(Title, TITLE_DIRECT_FIELDS)

        t.refresh_from_db()
        assert t.name == ""

    def test_fk_handler_resolves_franchise(self, opdb):
        franchise = Franchise.objects.create(name="Godzilla", slug="godzilla")
        t = Title.objects.create(opdb_id="G1", name="", slug="t1")

        Claim.objects.assert_claim(t, "franchise", "godzilla", source=opdb)

        franchise_lookup = {f.slug: f for f in Franchise.objects.all()}
        _resolve_bulk(
            Title,
            TITLE_DIRECT_FIELDS,
            fk_handlers={"franchise": ("franchise", franchise_lookup)},
        )

        t.refresh_from_db()
        assert t.franchise == franchise

    def test_fk_handler_resets_when_no_claim(self, opdb):
        franchise = Franchise.objects.create(name="Godzilla", slug="godzilla")
        t = Title.objects.create(opdb_id="G1", name="", slug="t1", franchise=franchise)

        # No franchise claim — should reset to None.
        franchise_lookup = {f.slug: f for f in Franchise.objects.all()}
        _resolve_bulk(
            Title,
            TITLE_DIRECT_FIELDS,
            fk_handlers={"franchise": ("franchise", franchise_lookup)},
        )

        t.refresh_from_db()
        assert t.franchise is None

    def test_object_ids_scoping(self, opdb):
        t1 = Title.objects.create(opdb_id="G1", name="Untouched", slug="t1")
        t2 = Title.objects.create(opdb_id="G2", name="", slug="t2")

        Claim.objects.assert_claim(t2, "name", "Resolved", source=opdb)

        # Only resolve t2.
        _resolve_bulk(Title, TITLE_DIRECT_FIELDS, object_ids={t2.pk})

        t1.refresh_from_db()
        t2.refresh_from_db()
        assert t1.name == "Untouched"  # Not touched.
        assert t2.name == "Resolved"

    def test_updated_at_is_set(self, opdb):
        t = Title.objects.create(opdb_id="G1", name="", slug="t1")
        old_updated_at = t.updated_at

        Claim.objects.assert_claim(t, "name", "New Name", source=opdb)
        _resolve_bulk(Title, TITLE_DIRECT_FIELDS)

        t.refresh_from_db()
        assert t.updated_at > old_updated_at


@pytest.mark.django_db
class TestResolveBulkManufacturer:
    def test_resolves_with_int_fields(self, opdb):
        m = Manufacturer.objects.create(name="", slug="stern")

        Claim.objects.assert_claim(m, "name", "Stern Pinball", source=opdb)
        Claim.objects.assert_claim(m, "founded_year", "1999", source=opdb)
        Claim.objects.assert_claim(m, "country", "US", source=opdb)

        _resolve_bulk(
            Manufacturer,
            MANUFACTURER_DIRECT_FIELDS,
        )

        m.refresh_from_db()
        assert m.name == "Stern Pinball"
        assert m.founded_year == 1999
        assert m.country == "US"


@pytest.mark.django_db
class TestResolveBulkMarkdownReferences:
    def test_bulk_resolve_syncs_record_references(self, opdb):
        """_resolve_bulk populates RecordReference for markdown link fields."""
        mfr = Manufacturer.objects.create(name="", slug="williams")
        system = System.objects.create(name="WPC-95", slug="wpc-95", manufacturer=mfr)

        Claim.objects.assert_claim(mfr, "name", "Williams", source=opdb)
        Claim.objects.assert_claim(
            mfr,
            "description",
            f"Uses [[system:id:{system.pk}]].",
            source=opdb,
        )

        _resolve_bulk(Manufacturer, MANUFACTURER_DIRECT_FIELDS)

        mfr_ct = ContentType.objects.get_for_model(Manufacturer)
        refs = RecordReference.objects.filter(source_type=mfr_ct, source_id=mfr.pk)
        assert refs.count() == 1
        system_ct = ContentType.objects.get_for_model(System)
        assert refs.first().target_type == system_ct
        assert refs.first().target_id == system.pk

    def test_bulk_resolve_cleans_stale_references(self, opdb):
        """_resolve_bulk removes RecordReference when markdown links are removed."""
        mfr = Manufacturer.objects.create(name="", slug="williams")
        system = System.objects.create(name="WPC-95", slug="wpc-95", manufacturer=mfr)

        # First resolve with a link
        Claim.objects.assert_claim(
            mfr,
            "description",
            f"Uses [[system:id:{system.pk}]].",
            source=opdb,
        )
        _resolve_bulk(Manufacturer, MANUFACTURER_DIRECT_FIELDS)

        mfr_ct = ContentType.objects.get_for_model(Manufacturer)
        assert (
            RecordReference.objects.filter(source_type=mfr_ct, source_id=mfr.pk).count()
            == 1
        )

        # Deactivate the claim so description resolves to blank
        Claim.objects.filter(
            content_type=mfr_ct, object_id=mfr.pk, field_name="description"
        ).update(is_active=False)
        _resolve_bulk(Manufacturer, MANUFACTURER_DIRECT_FIELDS)

        assert (
            RecordReference.objects.filter(source_type=mfr_ct, source_id=mfr.pk).count()
            == 0
        )


@pytest.mark.django_db
class TestResolveBulkTaxonomy:
    def test_malformed_int_claim_uses_default(self, opdb):
        """Non-parseable integer on a non-null field should fall back to 0, not None."""
        tag = Tag.objects.create(name="", slug="test-tag")

        Claim.objects.assert_claim(tag, "name", "Test Tag", source=opdb)
        Claim.objects.assert_claim(tag, "display_order", "abc", source=opdb)

        _resolve_bulk(Tag, TAXONOMY_DIRECT_FIELDS, object_ids={tag.pk})

        tag.refresh_from_db()
        assert tag.name == "Test Tag"
        assert tag.display_order == 0  # default, not None


@pytest.mark.django_db
class TestResolveTitle:
    def test_single_object_wrapper(self, opdb):
        franchise = Franchise.objects.create(name="Godzilla", slug="godzilla")
        t = Title.objects.create(opdb_id="G1", name="", slug="t1")

        Claim.objects.assert_claim(t, "name", "Godzilla", source=opdb)
        Claim.objects.assert_claim(t, "description", "A monster game.", source=opdb)
        Claim.objects.assert_claim(t, "franchise", "godzilla", source=opdb)

        result = resolve_title(t)

        assert result.name == "Godzilla"
        assert result.description == "A monster game."
        assert result.franchise == franchise

    def test_resets_franchise_when_no_claim(self, opdb):
        franchise = Franchise.objects.create(name="Godzilla", slug="godzilla")
        t = Title.objects.create(opdb_id="G1", name="", slug="t1", franchise=franchise)

        # Only a name claim, no franchise.
        Claim.objects.assert_claim(t, "name", "Godzilla", source=opdb)
        result = resolve_title(t)

        assert result.franchise is None
