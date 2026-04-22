"""Tests for the ingest_wikidata_manufacturers command."""

import json
import tempfile

import pytest
from django.core.management import call_command

from apps.catalog.models import Manufacturer
from apps.provenance.models import Claim, Source

FIXTURES = "apps/catalog/tests/fixtures"
SAMPLE = f"{FIXTURES}/wikidata_manufacturers_sample.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _seed_db(db):
    """Pre-seed the DB with a manufacturer that matches the Wikidata fixture.

    Mirrors what ingest_manufacturers does: create the record then assert
    name claims from the originating source so that resolve()
    can restore them (claims are the sole source of truth for these fields).
    """
    mfr = Manufacturer.objects.create(name="Williams", slug="williams")
    ipdb = Source.objects.create(name="IPDB", source_type="database", priority=10)
    Claim.objects.assert_claim(mfr, "name", "Williams", source=ipdb)
    # "Obscure Pinball Co" has no DB record — exercises the no-match path.


@pytest.fixture
def _run_ingest(_seed_db):
    """Run ingest_wikidata_manufacturers using the sample fixture."""
    call_command("ingest_wikidata_manufacturers", from_dump=SAMPLE)


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.usefixtures("_run_ingest")
class TestIngestWikidataManufacturers:
    def test_creates_source(self):
        source = Source.objects.get(slug="wikidata")
        assert source.name == "Wikidata"
        assert source.priority == 75
        assert source.source_type == "database"

    def test_manufacturer_matched_gets_wikidata_id(self):
        mfr = Manufacturer.objects.get(name="Williams")
        assert mfr.wikidata_id == "Q180268"

    def test_unmatched_manufacturer_not_created(self):
        assert not Manufacturer.objects.filter(name="Obscure Pinball Co").exists()

    def test_claims_created(self):
        mfr = Manufacturer.objects.get(name="Williams")
        source = Source.objects.get(slug="wikidata")
        active = mfr.claims.filter(source=source, is_active=True)
        field_names = set(active.values_list("field_name", flat=True))
        assert field_names >= {
            "wikidata.description",
            "logo_url",
            "website",
        }

    def test_resolved_description_in_extra_data(self):
        mfr = Manufacturer.objects.get(name="Williams")
        mfr.refresh_from_db()
        assert (
            mfr.extra_data.get("wikidata.description")
            == "American manufacturer of pinball machines and arcade games"
        )

    def test_resolved_logo_url_uses_https(self):
        mfr = Manufacturer.objects.get(name="Williams")
        mfr.refresh_from_db()
        assert mfr.logo_url is not None
        assert mfr.logo_url.startswith("https://")

    def test_resolved_website(self):
        mfr = Manufacturer.objects.get(name="Williams")
        mfr.refresh_from_db()
        assert mfr.website == "https://www.williams.com"

    def test_idempotent(self):
        """Running twice must not duplicate claims or change wikidata_id."""
        call_command("ingest_wikidata_manufacturers", from_dump=SAMPLE)
        assert Manufacturer.objects.filter(wikidata_id="Q180268").count() == 1
        source = Source.objects.get(slug="wikidata")
        mfr = Manufacturer.objects.get(name="Williams")
        desc_claims = mfr.claims.filter(
            source=source, field_name="wikidata.description", is_active=True
        )
        assert desc_claims.count() == 1


@pytest.mark.django_db
class TestFromDumpEmpty:
    """Empty dump should not crash and should still create the source."""

    def test_empty_bindings(self, db):
        empty: dict[str, object] = {"results": {"bindings": []}}
        data = {"manufacturers": empty, "bio": empty}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name

        call_command("ingest_wikidata_manufacturers", from_dump=path)
        assert Source.objects.filter(slug="wikidata").exists()
        assert (
            Claim.objects.filter(source=Source.objects.get(slug="wikidata")).count()
            == 0
        )
