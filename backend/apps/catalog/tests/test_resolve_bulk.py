"""Tests for _resolve_single, _resolve_bulk, and resolve_entity."""

import pytest
from django.contrib.contenttypes.models import ContentType

from apps.catalog.models import Franchise, Manufacturer, System, Tag, Title
from apps.catalog.resolve import (
    _resolve_bulk,
    _resolve_single,
    resolve_entity,
)
from apps.core.models import RecordReference, get_claim_fields
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

        _resolve_bulk(Title, get_claim_fields(Title))

        t1.refresh_from_db()
        t2.refresh_from_db()
        assert t1.name == "Godzilla"
        assert t2.name == "Blackout"

    def test_winner_by_priority(self, opdb, editorial):
        t = Title.objects.create(opdb_id="G1", name="", slug="t1")

        Claim.objects.assert_claim(t, "name", "Low Priority", source=opdb)
        Claim.objects.assert_claim(t, "name", "High Priority", source=editorial)

        _resolve_bulk(Title, get_claim_fields(Title))

        t.refresh_from_db()
        assert t.name == "High Priority"

    def test_no_claims_resets_to_default(self, opdb):
        t = Title.objects.create(opdb_id="G1", name="Stale Name", slug="t1")

        # No claims — resolution should blank the name.
        _resolve_bulk(Title, get_claim_fields(Title))

        t.refresh_from_db()
        assert t.name == ""

    def test_fk_resolves_franchise(self, opdb):
        from apps.catalog.resolve import resolve_all_entities

        franchise = Franchise.objects.create(name="Godzilla", slug="godzilla")
        t = Title.objects.create(opdb_id="G1", name="", slug="t1")

        Claim.objects.assert_claim(t, "franchise", "godzilla", source=opdb)

        resolve_all_entities(Title)

        t.refresh_from_db()
        assert t.franchise == franchise

    def test_fk_resets_when_no_claim(self, opdb):
        from apps.catalog.resolve import resolve_all_entities

        franchise = Franchise.objects.create(name="Godzilla", slug="godzilla")
        t = Title.objects.create(opdb_id="G1", name="", slug="t1", franchise=franchise)

        # No franchise claim — should reset to None.
        resolve_all_entities(Title)

        t.refresh_from_db()
        assert t.franchise is None

    def test_object_ids_scoping(self, opdb):
        t1 = Title.objects.create(opdb_id="G1", name="Untouched", slug="t1")
        t2 = Title.objects.create(opdb_id="G2", name="", slug="t2")

        Claim.objects.assert_claim(t2, "name", "Resolved", source=opdb)

        # Only resolve t2.
        _resolve_bulk(Title, get_claim_fields(Title), object_ids={t2.pk})

        t1.refresh_from_db()
        t2.refresh_from_db()
        assert t1.name == "Untouched"  # Not touched.
        assert t2.name == "Resolved"

    def test_updated_at_is_set(self, opdb):
        t = Title.objects.create(opdb_id="G1", name="", slug="t1")
        old_updated_at = t.updated_at

        Claim.objects.assert_claim(t, "name", "New Name", source=opdb)
        _resolve_bulk(Title, get_claim_fields(Title))

        t.refresh_from_db()
        assert t.updated_at > old_updated_at


@pytest.mark.django_db
class TestResolveBulkManufacturer:
    def test_resolves_with_int_fields(self, opdb):
        from apps.catalog.models import CorporateEntity

        m = Manufacturer.objects.create(name="Stern Pinball", slug="stern")
        ce = CorporateEntity.objects.create(
            manufacturer=m, name="Stern Pinball, Inc.", slug="stern-pinball-inc"
        )

        Claim.objects.assert_claim(ce, "name", "Stern Pinball, Inc.", source=opdb)
        Claim.objects.assert_claim(ce, "year_start", "1999", source=opdb)

        _resolve_bulk(
            CorporateEntity,
            get_claim_fields(CorporateEntity),
        )

        ce.refresh_from_db()
        assert ce.name == "Stern Pinball, Inc."
        assert ce.year_start == 1999


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

        _resolve_bulk(Manufacturer, get_claim_fields(Manufacturer))

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
        _resolve_bulk(Manufacturer, get_claim_fields(Manufacturer))

        mfr_ct = ContentType.objects.get_for_model(Manufacturer)
        assert (
            RecordReference.objects.filter(source_type=mfr_ct, source_id=mfr.pk).count()
            == 1
        )

        # Deactivate the claim so description resolves to blank
        Claim.objects.filter(
            content_type=mfr_ct, object_id=mfr.pk, field_name="description"
        ).update(is_active=False)
        _resolve_bulk(Manufacturer, get_claim_fields(Manufacturer))

        assert (
            RecordReference.objects.filter(source_type=mfr_ct, source_id=mfr.pk).count()
            == 0
        )


@pytest.mark.django_db
class TestResolveBulkUniqueFieldSafety:
    """UNIQUE fields must not be reset when no claim exists, or bulk_update
    will crash with an IntegrityError when multiple objects share the default."""

    def test_unique_name_preserved_when_no_claim(self, opdb):
        """Objects without a name claim keep their existing name."""
        from apps.catalog.models import Theme

        t1 = Theme.objects.create(name="Horror", slug="horror")
        t2 = Theme.objects.create(name="Sports", slug="sports")

        # Only t1 gets a name claim; t2 has none.
        Claim.objects.assert_claim(t1, "name", "Horror Movies", source=opdb)

        _resolve_bulk(Theme, get_claim_fields(Theme))

        t1.refresh_from_db()
        t2.refresh_from_db()
        assert t1.name == "Horror Movies"  # Updated by claim.
        assert t2.name == "Sports"  # Preserved — not reset to "".

    def test_non_unique_field_still_resets(self, opdb):
        """Non-unique fields are still reset to default when no claim exists."""
        from apps.catalog.models import Theme

        t = Theme.objects.create(name="Horror", slug="horror", description="Old desc")

        # Name claim but no description claim.
        Claim.objects.assert_claim(t, "name", "Horror", source=opdb)

        _resolve_bulk(Theme, get_claim_fields(Theme))

        t.refresh_from_db()
        assert t.description == ""  # Reset to default.

    def test_single_preserves_unique_name_without_claim(self, opdb):
        """_resolve_single also preserves UNIQUE fields without claims (parity)."""
        from apps.catalog.models import Theme

        t = Theme.objects.create(name="Horror", slug="horror", description="Old desc")

        # Description claim but no name claim.
        Claim.objects.assert_claim(t, "description", "Scary stuff", source=opdb)

        _resolve_single(t, get_claim_fields(Theme))

        assert t.name == "Horror"  # Preserved — not reset to "".
        assert t.description == "Scary stuff"  # Applied from claim.

    def test_single_and_bulk_produce_same_result(self, opdb):
        """Single and bulk resolution must agree on partial-claim entities."""
        from apps.catalog.models import Theme

        # Two identical themes, one resolved single, one bulk.
        t_single = Theme.objects.create(
            name="Horror", slug="horror", description="Old desc"
        )
        t_bulk = Theme.objects.create(
            name="Horror Copy", slug="horror-copy", description="Old desc"
        )

        # Both get only a description claim, no name claim.
        Claim.objects.assert_claim(t_single, "description", "Scary stuff", source=opdb)
        Claim.objects.assert_claim(t_bulk, "description", "Scary stuff", source=opdb)

        _resolve_single(t_single, get_claim_fields(Theme))
        t_single.save()

        _resolve_bulk(Theme, get_claim_fields(Theme), object_ids={t_bulk.pk})
        t_bulk.refresh_from_db()

        assert t_single.name == "Horror"  # Preserved.
        assert t_bulk.name == "Horror Copy"  # Preserved.
        assert t_single.description == t_bulk.description == "Scary stuff"


@pytest.mark.django_db
class TestPreserveNotNullFK:
    """Non-nullable FK fields must not be reset when no claim exists."""

    @pytest.fixture
    def subgen_fields(self):
        """Claim fields including technology_generation (NOT NULL FK).

        Uses explicit field dict rather than get_claim_fields() so these
        tests verify resolver behavior independent of claims_exempt state.
        """
        from apps.catalog.models.taxonomy import TechnologySubgeneration

        fields = get_claim_fields(TechnologySubgeneration)
        fields["technology_generation"] = "technology_generation"
        return fields

    def test_bulk_preserves_notnull_fk_without_claim(self, opdb, subgen_fields):
        from apps.catalog.models.taxonomy import (
            TechnologyGeneration,
            TechnologySubgeneration,
        )

        gen = TechnologyGeneration.objects.create(
            name="Solid State", slug="solid-state"
        )
        subgen = TechnologySubgeneration.objects.create(
            name="Discrete Logic", slug="discrete-logic", technology_generation=gen
        )

        # Name claim but no technology_generation claim.
        Claim.objects.assert_claim(subgen, "name", "Discrete Logic", source=opdb)

        _resolve_bulk(
            TechnologySubgeneration,
            subgen_fields,
            object_ids={subgen.pk},
        )

        subgen.refresh_from_db()
        assert subgen.name == "Discrete Logic"
        assert subgen.technology_generation == gen  # Preserved, not crashed.

    def test_single_preserves_notnull_fk_without_claim(self, opdb, subgen_fields):
        from apps.catalog.models.taxonomy import (
            TechnologyGeneration,
            TechnologySubgeneration,
        )

        gen = TechnologyGeneration.objects.create(
            name="Solid State", slug="solid-state"
        )
        subgen = TechnologySubgeneration.objects.create(
            name="Discrete Logic", slug="discrete-logic", technology_generation=gen
        )

        Claim.objects.assert_claim(subgen, "name", "Discrete Logic", source=opdb)

        _resolve_single(subgen, subgen_fields)
        subgen.save()

        subgen.refresh_from_db()
        assert subgen.technology_generation == gen  # Preserved.

    def test_notnull_fk_overwritten_when_claim_exists(self, opdb, subgen_fields):
        from apps.catalog.models.taxonomy import (
            TechnologyGeneration,
            TechnologySubgeneration,
        )

        gen1 = TechnologyGeneration.objects.create(
            name="Solid State", slug="solid-state"
        )
        gen2 = TechnologyGeneration.objects.create(name="Electromechanical", slug="em")
        subgen = TechnologySubgeneration.objects.create(
            name="Discrete Logic", slug="discrete-logic", technology_generation=gen1
        )

        Claim.objects.assert_claim(subgen, "name", "Discrete Logic", source=opdb)
        Claim.objects.assert_claim(subgen, "technology_generation", "em", source=opdb)

        _resolve_bulk(
            TechnologySubgeneration,
            subgen_fields,
            object_ids={subgen.pk},
        )

        subgen.refresh_from_db()
        assert subgen.technology_generation == gen2  # Overwritten by claim.


@pytest.mark.django_db
class TestResolveBulkTaxonomy:
    def test_malformed_int_claim_uses_default(self, opdb):
        """Non-parseable integer on a non-null field should fall back to 0, not None."""
        tag = Tag.objects.create(name="", slug="test-tag")

        Claim.objects.assert_claim(tag, "name", "Test Tag", source=opdb)
        Claim.objects.assert_claim(tag, "display_order", "abc", source=opdb)

        _resolve_bulk(Tag, get_claim_fields(Tag), object_ids={tag.pk})

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

        result = resolve_entity(t)

        assert result.name == "Godzilla"
        assert result.description == "A monster game."
        assert result.franchise == franchise

    def test_resets_franchise_when_no_claim(self, opdb):
        franchise = Franchise.objects.create(name="Godzilla", slug="godzilla")
        t = Title.objects.create(opdb_id="G1", name="", slug="t1", franchise=franchise)

        # Only a name claim, no franchise.
        Claim.objects.assert_claim(t, "name", "Godzilla", source=opdb)
        result = resolve_entity(t)

        assert result.franchise is None
