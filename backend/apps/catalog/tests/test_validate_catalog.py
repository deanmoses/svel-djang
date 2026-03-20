"""Tests for the validate_catalog management command."""

import json

import pytest
from django.core.management import call_command

from apps.catalog.models import (
    CreditRole,
    Franchise,
    MachineModel,
    Manufacturer,
    Person,
    Theme,
    Title,
)
from apps.provenance.models import Claim, Source


@pytest.fixture(autouse=True)
def _no_golden_records(monkeypatch, tmp_path):
    """Point golden records at an empty fixture so unrelated tests skip them."""
    import apps.catalog.management.commands.validate_catalog as mod

    empty = tmp_path / "golden_records.json"
    empty.write_text(json.dumps({"models": [], "titles": [], "manufacturers": []}))
    monkeypatch.setattr(mod, "GOLDEN_RECORDS_PATH", empty)


@pytest.fixture
def ipdb(db):
    return Source.objects.create(name="IPDB", source_type="database", priority=10)


@pytest.fixture
def pinbase_source(db):
    return Source.objects.create(
        name="Pinbase", slug="pinbase", source_type="editorial", priority=300
    )


@pytest.fixture
def manufacturer(db):
    return Manufacturer.objects.create(name="Williams", slug="williams")


@pytest.fixture
def title(db):
    return Title.objects.create(
        name="Medieval Madness", slug="medieval-madness", opdb_id="G1234"
    )


class TestValidateCatalogClean:
    """A clean catalog should produce no errors or warnings."""

    def test_empty_catalog_no_errors(self, db, capsys):
        """Empty catalog is valid — no errors or warnings."""
        call_command("validate_catalog")
        captured = capsys.readouterr()
        assert "error(s)" in captured.out
        assert "0 error(s)" in captured.out
        assert "0 warning(s)" in captured.out

    def test_clean_model_no_errors(self, db, title, capsys):
        MachineModel.objects.create(
            name="Medieval Madness",
            slug="medieval-madness-williams-1997",
            title=title,
            year=1997,
        )
        call_command("validate_catalog")
        captured = capsys.readouterr()
        assert "0 error(s)" in captured.out


class TestNamelessEntities:
    def test_nameless_model_is_error(self, db, capsys):
        MachineModel.objects.create(name="", slug="empty-name")
        with pytest.raises(SystemExit, match="1"):
            call_command("validate_catalog")
        captured = capsys.readouterr()
        assert "have no name" in captured.out

    def test_nameless_title_is_error(self, db, capsys):
        Title.objects.create(name="", slug="empty-title", opdb_id="G0000")
        with pytest.raises(SystemExit, match="1"):
            call_command("validate_catalog")
        captured = capsys.readouterr()
        assert "title(s) have no name" in captured.out

    def test_nameless_person_is_error(self, db, capsys):
        Person.objects.create(name="", slug="empty-person")
        with pytest.raises(SystemExit, match="1"):
            call_command("validate_catalog")
        captured = capsys.readouterr()
        assert "person(s) have no name" in captured.out


class TestConversionVariantConflict:
    def test_conversion_with_variant_of_is_error(self, db, capsys):
        parent = MachineModel.objects.create(name="Parent", slug="parent")
        MachineModel.objects.create(
            name="Child",
            slug="child",
            is_conversion=True,
            variant_of=parent,
        )
        with pytest.raises(SystemExit, match="1"):
            call_command("validate_catalog")
        captured = capsys.readouterr()
        assert "is_conversion=True and variant_of" in captured.out


class TestVariantChains:
    def test_variant_chain_is_warning(self, db, capsys):
        root = MachineModel.objects.create(name="Root", slug="root")
        mid = MachineModel.objects.create(name="Mid", slug="mid", variant_of=root)
        MachineModel.objects.create(name="Leaf", slug="leaf", variant_of=mid)
        call_command("validate_catalog")
        captured = capsys.readouterr()
        assert "variant_of chains" in captured.out
        assert "0 error(s)" in captured.out

    def test_variant_chain_fails_with_fail_on_warn(self, db, capsys):
        root = MachineModel.objects.create(name="Root", slug="root")
        mid = MachineModel.objects.create(name="Mid", slug="mid", variant_of=root)
        MachineModel.objects.create(name="Leaf", slug="leaf", variant_of=mid)
        with pytest.raises(SystemExit, match="1"):
            call_command("validate_catalog", "--fail-on-warn")


class TestDuplicatePersons:
    def test_duplicate_person_names_are_warning(self, db, capsys):
        Person.objects.create(name="Pat Lawlor", slug="pat-lawlor")
        Person.objects.create(name="pat lawlor", slug="pat-lawlor-2")
        call_command("validate_catalog")
        captured = capsys.readouterr()
        assert "person name(s) appear more than once" in captured.out


class TestUnresolvedFKClaims:
    def test_unresolved_system_claim_is_warning(self, db, ipdb, capsys):
        pm = MachineModel.objects.create(name="Test", slug="test-model")
        Claim.objects.assert_claim(pm, "system", "nonexistent-sys", source=ipdb)
        call_command("validate_catalog")
        captured = capsys.readouterr()
        assert "unresolved system claim" in captured.out


class TestUnresolvedCreditClaims:
    def test_missing_person_in_credit_claim(self, db, ipdb, capsys):
        CreditRole.objects.create(name="Design", slug="design")
        pm = MachineModel.objects.create(name="Test", slug="test-model")
        from apps.catalog.claims import build_relationship_claim

        claim_key, value = build_relationship_claim(
            "credit", {"person_slug": "ghost-person", "role": "design"}
        )
        Claim.objects.assert_claim(
            pm, "credit", value, source=ipdb, claim_key=claim_key
        )
        call_command("validate_catalog")
        captured = capsys.readouterr()
        assert "missing person slugs" in captured.out

    def test_missing_role_in_credit_claim(self, db, ipdb, capsys):
        Person.objects.create(name="Pat Lawlor", slug="pat-lawlor")
        pm = MachineModel.objects.create(name="Test", slug="test-model")
        from apps.catalog.claims import build_relationship_claim

        claim_key, value = build_relationship_claim(
            "credit", {"person_slug": "pat-lawlor", "role": "ghost-role"}
        )
        Claim.objects.assert_claim(
            pm, "credit", value, source=ipdb, claim_key=claim_key
        )
        call_command("validate_catalog")
        captured = capsys.readouterr()
        assert "missing role slugs" in captured.out


class TestUncuratedThemes:
    def test_auto_created_themes_noted(self, db, ipdb, pinbase_source, capsys):
        # Curated theme — has a pinbase name claim.
        curated = Theme.objects.create(name="Sports", slug="sports")
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(Theme)
        Claim.objects.create(
            content_type=ct,
            object_id=curated.pk,
            source=pinbase_source,
            field_name="name",
            claim_key="name",
            value="Sports",
        )

        # Uncurated theme — no pinbase claim.
        Theme.objects.create(name="Basebal", slug="basebal")

        call_command("validate_catalog")
        captured = capsys.readouterr()
        assert "auto-created" in captured.out
        assert "basebal" in captured.out


class TestGoldenRecords:
    """Test the golden records spot-check system."""

    @pytest.fixture
    def golden_file(self, tmp_path, monkeypatch):
        """Create a temporary golden_records.json and patch the path."""
        import apps.catalog.management.commands.validate_catalog as mod

        path = tmp_path / "golden_records.json"

        def _write(data):
            path.write_text(json.dumps(data))
            monkeypatch.setattr(mod, "GOLDEN_RECORDS_PATH", path)
            return path

        return _write

    def test_golden_model_passes(self, db, golden_file, capsys):
        t = Title.objects.create(
            name="Godzilla", slug="godzilla-stern", opdb_id="GweeP"
        )
        MachineModel.objects.create(
            name="Godzilla (Premium)",
            slug="godzilla-premium",
            title=t,
            ipdb_id=6842,
            opdb_id="GweeP-Ml9pZ-ARZoY",
        )
        golden_file(
            {
                "models": [
                    {
                        "slug": "godzilla-premium",
                        "expect": {
                            "name": "Godzilla (Premium)",
                            "title_slug": "godzilla-stern",
                            "ipdb_id": 6842,
                            "opdb_id": "GweeP-Ml9pZ-ARZoY",
                        },
                    }
                ],
                "titles": [],
                "manufacturers": [],
            }
        )
        call_command("validate_catalog")
        captured = capsys.readouterr()
        assert "golden record(s) passed" in captured.out
        assert "0 error(s)" in captured.out

    def test_golden_model_wrong_field_is_error(self, db, golden_file, capsys):
        MachineModel.objects.create(
            name="Godzilla (Premium)",
            slug="godzilla-premium",
            ipdb_id=6842,
        )
        golden_file(
            {
                "models": [
                    {
                        "slug": "godzilla-premium",
                        "expect": {"ipdb_id": 9999},
                    }
                ],
                "titles": [],
                "manufacturers": [],
            }
        )
        with pytest.raises(SystemExit, match="1"):
            call_command("validate_catalog")
        captured = capsys.readouterr()
        assert "ipdb_id=6842" in captured.out
        assert "expected 9999" in captured.out

    def test_golden_model_missing_is_error(self, db, golden_file, capsys):
        golden_file(
            {
                "models": [
                    {
                        "slug": "nonexistent-machine",
                        "expect": {"name": "Nope"},
                    }
                ],
                "titles": [],
                "manufacturers": [],
            }
        )
        with pytest.raises(SystemExit, match="1"):
            call_command("validate_catalog")
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_golden_title_passes(self, db, golden_file, capsys):
        f = Franchise.objects.create(name="Godzilla", slug="godzilla")
        Title.objects.create(
            name="Godzilla",
            slug="godzilla-stern",
            opdb_id="GweeP",
            franchise=f,
        )
        golden_file(
            {
                "models": [],
                "titles": [
                    {
                        "slug": "godzilla-stern",
                        "expect": {
                            "name": "Godzilla",
                            "opdb_id": "GweeP",
                            "franchise_slug": "godzilla",
                        },
                    }
                ],
                "manufacturers": [],
            }
        )
        call_command("validate_catalog")
        captured = capsys.readouterr()
        assert "golden record(s) passed" in captured.out

    def test_golden_variant_of_checked(self, db, golden_file, capsys):
        parent = MachineModel.objects.create(
            name="Godzilla (Premium)",
            slug="godzilla-premium",
        )
        MachineModel.objects.create(
            name="Godzilla (LE)",
            slug="godzilla-le",
            variant_of=parent,
        )
        golden_file(
            {
                "models": [
                    {
                        "slug": "godzilla-le",
                        "expect": {"variant_of_slug": "godzilla-premium"},
                    }
                ],
                "titles": [],
                "manufacturers": [],
            }
        )
        call_command("validate_catalog")
        captured = capsys.readouterr()
        assert "0 error(s)" in captured.out

    def test_golden_conversion_checked(self, db, golden_file, capsys):
        parent = MachineModel.objects.create(name="Eight Ball", slug="eight-ball")
        MachineModel.objects.create(
            name="Challenger",
            slug="challenger",
            is_conversion=True,
            converted_from=parent,
        )
        golden_file(
            {
                "models": [
                    {
                        "slug": "challenger",
                        "expect": {
                            "is_conversion": True,
                            "converted_from_slug": "eight-ball",
                            "variant_of_slug": None,
                        },
                    }
                ],
                "titles": [],
                "manufacturers": [],
            }
        )
        call_command("validate_catalog")
        captured = capsys.readouterr()
        assert "0 error(s)" in captured.out
