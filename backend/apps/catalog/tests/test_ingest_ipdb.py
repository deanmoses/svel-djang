"""Integration tests for the ingest_ipdb command."""

import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.catalog.models import DesignCredit, MachineModel, Person
from apps.provenance.models import Source

FIXTURES = "apps/catalog/tests/fixtures"


@pytest.fixture
def _run_ipdb(db):
    """Run ingest_ipdb with the sample fixture."""
    call_command("ingest_ipdb", ipdb=f"{FIXTURES}/ipdb_sample.json")


@pytest.mark.django_db
@pytest.mark.usefixtures("_run_ipdb")
class TestIngestIpdb:
    def test_creates_source(self):
        source = Source.objects.get(slug="ipdb")
        assert source.name == "IPDB"
        assert source.priority == 100

    def test_creates_models(self):
        assert MachineModel.objects.count() == 4
        assert MachineModel.objects.filter(ipdb_id=4000).exists()
        assert MachineModel.objects.filter(ipdb_id=20).exists()
        assert MachineModel.objects.filter(ipdb_id=61).exists()
        assert MachineModel.objects.filter(ipdb_id=100).exists()

    def test_claims_created(self):
        pm = MachineModel.objects.get(ipdb_id=4000)
        source = Source.objects.get(slug="ipdb")
        active_claims = pm.claims.filter(source=source, is_active=True)

        claim_fields = set(active_claims.values_list("field_name", flat=True))
        assert "name" in claim_fields
        assert "year" in claim_fields
        assert "manufacturer" in claim_fields
        assert "technology_generation" in claim_fields
        assert "ipdb_rating" in claim_fields

    def test_date_parsing(self):
        pm = MachineModel.objects.get(ipdb_id=4000)
        source = Source.objects.get(slug="ipdb")
        year_claim = pm.claims.get(source=source, field_name="year", is_active=True)
        assert year_claim.value == 1997
        month_claim = pm.claims.get(source=source, field_name="month", is_active=True)
        assert month_claim.value == 6

    def test_year_only_date(self):
        pm = MachineModel.objects.get(ipdb_id=20)
        source = Source.objects.get(slug="ipdb")
        year_claim = pm.claims.get(source=source, field_name="year", is_active=True)
        assert year_claim.value == 1941
        assert not pm.claims.filter(
            source=source, field_name="month", is_active=True
        ).exists()

    def test_credits_created(self):
        pm = MachineModel.objects.get(ipdb_id=4000)
        credits = DesignCredit.objects.filter(model=pm)
        assert credits.count() == 4
        assert credits.filter(role="design", person__name="Brian Eddy").exists()
        assert credits.filter(role="art", person__name="John Youssi").exists()
        assert credits.filter(role="software", person__name="Lyman Sheats").exists()

    def test_multi_credit_string(self):
        pm = MachineModel.objects.get(ipdb_id=61)
        design_credits = DesignCredit.objects.filter(model=pm, role="design")
        assert design_credits.count() == 2
        names = set(design_credits.values_list("person__name", flat=True))
        assert names == {"Pat Lawlor", "Larry DeMar"}

    def test_persons_created(self):
        assert Person.objects.count() == 6

    def test_pure_mechanical_type(self):
        pm = MachineModel.objects.get(ipdb_id=100)
        source = Source.objects.get(slug="ipdb")
        type_claim = pm.claims.get(
            source=source, field_name="technology_generation", is_active=True
        )
        assert type_claim.value == "pure-mechanical"

    def test_idempotent(self):
        call_command("ingest_ipdb", ipdb=f"{FIXTURES}/ipdb_sample.json")
        assert MachineModel.objects.count() == 4
        assert Person.objects.count() == 6

    def test_system_claim_created(self):
        """Medieval Madness has MPU 'Williams WPC-95' → system claim value 'wpc-95'."""
        pm = MachineModel.objects.get(ipdb_id=4000)
        source = Source.objects.get(slug="ipdb")
        claim = pm.claims.filter(
            source=source, field_name="system", is_active=True
        ).first()
        assert claim is not None
        assert claim.value == "wpc-95"

    def test_no_mpu_no_system_claim(self):
        """Records without MPU do not produce a system claim."""
        pm = MachineModel.objects.get(ipdb_id=20)
        source = Source.objects.get(slug="ipdb")
        assert not pm.claims.filter(
            source=source, field_name="system", is_active=True
        ).exists()


@pytest.mark.django_db
class TestIngestIpdbUnknownMpu:
    def test_unknown_mpu_raises_command_error(self, tmp_path):
        fixture = tmp_path / "bad_ipdb.json"
        fixture.write_text(
            json.dumps(
                {
                    "Data": [
                        {
                            "IpdbId": 9999,
                            "Title": "Mystery Machine",
                            "ManufacturerId": 999,
                            "Type": "Solid State (SS)",
                            "TypeShortName": "SS",
                            "MPU": "Unknown Board X-99",
                        }
                    ]
                }
            )
        )
        with pytest.raises(CommandError, match="Unknown MPU strings"):
            call_command("ingest_ipdb", ipdb=str(fixture))
