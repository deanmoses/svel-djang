"""Tests for the generate_ipdb_titles management command."""

import pytest
from django.core.management import call_command

from apps.catalog.models import MachineModel, Manufacturer, Title
from apps.provenance.models import Claim, Source


@pytest.fixture
def ipdb_source(db):
    return Source.objects.create(
        name="IPDB", slug="ipdb", source_type="database", priority=100
    )


@pytest.fixture
def manufacturer(db):
    return Manufacturer.objects.create(name="Williams", slug="williams")


@pytest.fixture
def ipdb_only_model(db, manufacturer):
    """An IPDB-only model with no opdb_id."""
    return MachineModel.objects.create(
        name="Alien Poker",
        ipdb_id=20,
        manufacturer=manufacturer,
    )


@pytest.fixture
def opdb_title(db):
    """An existing OPDB-backed title (simulating a name collision)."""
    return Title.objects.create(
        opdb_id="G1234",
        name="High Speed",
        slug="high-speed",
    )


@pytest.fixture
def ipdb_model_matching_opdb(db, manufacturer, opdb_title):
    """An IPDB-only model whose name matches an existing OPDB title."""
    return MachineModel.objects.create(
        name="High Speed",
        ipdb_id=1100,
        manufacturer=manufacturer,
    )


@pytest.fixture
def ipdb_model_base_name_match(db, manufacturer, opdb_title):
    """An IPDB-only model whose base name (w/o parenthetical) matches an OPDB title."""
    return MachineModel.objects.create(
        name="High Speed (Junior)",
        ipdb_id=1101,
        manufacturer=manufacturer,
    )


@pytest.fixture
def opdb_model(db, manufacturer):
    """A model with an OPDB ID (should be skipped)."""
    return MachineModel.objects.create(
        name="Medieval Madness",
        opdb_id="G5pe4-M1",
        ipdb_id=4032,
        manufacturer=manufacturer,
    )


@pytest.mark.django_db
class TestGenerateIpdbTitles:
    def test_creates_title_for_ipdb_only_model(self, ipdb_only_model, ipdb_source):
        call_command("generate_ipdb_titles")

        title = Title.objects.get(opdb_id="ipdb:20")
        assert title.name == "Alien Poker"
        assert title.slug == "alien-poker"
        assert title.needs_review is False
        assert title.needs_review_notes == ""

    def test_creates_group_claim(self, ipdb_only_model, ipdb_source):
        call_command("generate_ipdb_titles")

        source = Source.objects.get(slug="ipdb")
        claim = ipdb_only_model.claims.get(
            source=source, field_name="group", is_active=True
        )
        assert claim.value == "ipdb:20"
        assert claim.needs_review is False

    def test_skips_opdb_models(self, opdb_model, ipdb_source):
        call_command("generate_ipdb_titles")

        assert not Title.objects.filter(opdb_id__startswith="ipdb:").exists()

    def test_skips_model_with_existing_group_claim(self, ipdb_only_model, ipdb_source):
        """Models that already have an active group claim should be skipped."""
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(MachineModel)
        Claim.objects.create(
            content_type=ct,
            object_id=ipdb_only_model.pk,
            source=ipdb_source,
            field_name="group",
            claim_key="group",
            value="G9999",
        )

        call_command("generate_ipdb_titles")

        assert not Title.objects.filter(opdb_id="ipdb:20").exists()

    def test_idempotent(self, ipdb_only_model, ipdb_source):
        call_command("generate_ipdb_titles")
        first_count = Title.objects.filter(opdb_id__startswith="ipdb:").count()

        call_command("generate_ipdb_titles")
        second_count = Title.objects.filter(opdb_id__startswith="ipdb:").count()

        assert first_count == second_count == 1

    def test_flags_exact_name_match(
        self, ipdb_model_matching_opdb, opdb_title, ipdb_source
    ):
        call_command("generate_ipdb_titles")

        title = Title.objects.get(opdb_id="ipdb:1100")
        assert title.needs_review is True
        assert "High Speed" in title.needs_review_notes
        assert "G1234" in title.needs_review_notes

        source = Source.objects.get(slug="ipdb")
        claim = ipdb_model_matching_opdb.claims.get(
            source=source, field_name="group", is_active=True
        )
        assert claim.needs_review is True
        assert "G1234" in claim.needs_review_notes

    def test_flags_base_name_match(
        self, ipdb_model_base_name_match, opdb_title, ipdb_source
    ):
        call_command("generate_ipdb_titles")

        title = Title.objects.get(opdb_id="ipdb:1101")
        assert title.needs_review is True
        assert "High Speed" in title.needs_review_notes
        assert "High Speed (Junior)" in title.needs_review_notes
        assert "G1234" in title.needs_review_notes

    def test_flags_ambiguous_multi_match(self, db, manufacturer, ipdb_source):
        """When name matches multiple OPDB titles, flag as ambiguous."""
        Title.objects.create(opdb_id="G4kw7", name="Aloha", slug="aloha")
        Title.objects.create(opdb_id="GxYz1", name="Aloha", slug="aloha-2")
        MachineModel.objects.create(name="Aloha", ipdb_id=50, manufacturer=manufacturer)

        call_command("generate_ipdb_titles")

        title = Title.objects.get(opdb_id="ipdb:50")
        assert title.needs_review is True
        assert "multiple existing titles" in title.needs_review_notes
        assert "G4kw7" in title.needs_review_notes
        assert "GxYz1" in title.needs_review_notes

    def test_no_review_for_unmatched(self, ipdb_only_model, ipdb_source):
        """Models with no name match should not be flagged."""
        call_command("generate_ipdb_titles")

        title = Title.objects.get(opdb_id="ipdb:20")
        assert title.needs_review is False
        assert title.needs_review_notes == ""

    def test_resolve_claims_links_title(self, ipdb_only_model, ipdb_source):
        """After generate + resolve, the model's title FK should be set."""
        call_command("generate_ipdb_titles")
        call_command("resolve_claims")

        ipdb_only_model.refresh_from_db()
        assert ipdb_only_model.title is not None
        assert ipdb_only_model.title.opdb_id == "ipdb:20"
