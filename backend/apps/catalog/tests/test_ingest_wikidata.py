"""Tests for the ingest_wikidata command and wikidata_sparql module."""

import pytest
from django.core.management import call_command

from apps.catalog.ingestion.wikidata_sparql import parse_wikidata_date
from apps.catalog.models import Credit, CreditRole, MachineModel, Person
from apps.catalog.tests.conftest import make_machine_model
from apps.provenance.models import Claim, Source

FIXTURES = "apps/catalog/tests/fixtures"
SAMPLE = f"{FIXTURES}/wikidata_sample.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _seed_db(db, credit_roles):
    """Pre-seed the DB with persons and machine credits for matching."""
    # Steve Ritchie exists and has credits on machines whose titles overlap
    # with the Wikidata fixture ("Black Knight", "Terminator 2: Judgment Day").
    steve = Person.objects.create(name="Steve Ritchie", slug="steve-ritchie")
    bk = make_machine_model(name="Black Knight", slug="black-knight", year=1980)
    t2 = make_machine_model(
        name="Terminator 2: Judgment Day", slug="terminator-2-judgment-day", year=1991
    )
    role = CreditRole.objects.get(slug="design")
    Credit.objects.create(model=bk, person=steve, role=role)
    Credit.objects.create(model=t2, person=steve, role=role)

    # Pat Designer exists but has NO credits in the DB.
    Person.objects.create(name="Pat Designer", slug="pat-designer")

    # "Unknown Person" does NOT exist in the DB.


@pytest.fixture
def _run_wikidata(_seed_db):
    """Run ingest_wikidata using the sample fixture."""
    call_command("ingest_wikidata", from_dump=SAMPLE)


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.usefixtures("_run_wikidata")
class TestIngestWikidata:
    def test_creates_source(self):
        source = Source.objects.get(slug="wikidata")
        assert source.name == "Wikidata"
        assert source.priority == 75
        assert source.source_type == "database"

    def test_matched_person_gets_wikidata_id(self):
        person = Person.objects.get(name="Steve Ritchie")
        assert person.wikidata_id == "Q312897"

    def test_matched_person_no_credits_gets_wikidata_id(self):
        person = Person.objects.get(name="Pat Designer")
        assert person.wikidata_id == "Q99999"

    def test_unmatched_person_not_created(self):
        assert not Person.objects.filter(name="Unknown Person").exists()

    def test_bio_claim_asserted(self):
        person = Person.objects.get(name="Steve Ritchie")
        source = Source.objects.get(slug="wikidata")
        claim = person.claims.get(
            source=source, field_name="wikidata.description", is_active=True
        )
        assert claim.value == "American pinball machine designer"
        assert claim.citation == "https://www.wikidata.org/wiki/Q312897"

    def test_birth_date_claims(self):
        person = Person.objects.get(name="Steve Ritchie")
        source = Source.objects.get(slug="wikidata")
        assert (
            person.claims.get(
                source=source, field_name="birth_year", is_active=True
            ).value
            == 1951
        )
        assert (
            person.claims.get(
                source=source, field_name="birth_month", is_active=True
            ).value
            == 10
        )
        assert (
            person.claims.get(
                source=source, field_name="birth_day", is_active=True
            ).value
            == 15
        )

    def test_year_precision_only_asserts_year(self):
        """Pat Designer has birthDatePrecision=9 (year only) in the fixture."""
        person = Person.objects.get(name="Pat Designer")
        source = Source.objects.get(slug="wikidata")
        assert person.claims.filter(
            source=source, field_name="birth_year", is_active=True
        ).exists()
        assert not person.claims.filter(
            source=source, field_name="birth_month", is_active=True
        ).exists()
        assert not person.claims.filter(
            source=source, field_name="birth_day", is_active=True
        ).exists()

    def test_birth_place_claim(self):
        person = Person.objects.get(name="Steve Ritchie")
        source = Source.objects.get(slug="wikidata")
        claim = person.claims.get(
            source=source, field_name="birth_place", is_active=True
        )
        assert claim.value == "Chicago"

    def test_nationality_claim(self):
        person = Person.objects.get(name="Steve Ritchie")
        source = Source.objects.get(slug="wikidata")
        claim = person.claims.get(
            source=source, field_name="nationality", is_active=True
        )
        assert claim.value == "United States of America"

    def test_photo_url_uses_https(self):
        person = Person.objects.get(name="Steve Ritchie")
        source = Source.objects.get(slug="wikidata")
        claim = person.claims.get(source=source, field_name="photo_url", is_active=True)
        assert claim.value.startswith("https://")
        assert "Steve_Ritchie" in claim.value

    def test_resolve_applied_after_ingest(self):
        """resolve_person() should have applied claims to model fields."""
        person = Person.objects.get(name="Steve Ritchie")
        person.refresh_from_db()
        assert (
            person.extra_data.get("wikidata.description")
            == "American pinball machine designer"
        )
        assert person.birth_year == 1951
        assert person.birth_month == 10
        assert person.birth_day == 15
        assert person.birth_place == "Chicago"
        assert person.nationality == "United States of America"

    def test_idempotent(self):
        """Running twice must not duplicate claims or change wikidata_id."""
        call_command("ingest_wikidata", from_dump=SAMPLE)
        assert Person.objects.filter(wikidata_id="Q312897").count() == 1
        source = Source.objects.get(slug="wikidata")
        steve = Person.objects.get(name="Steve Ritchie")
        bio_claims = steve.claims.filter(
            source=source, field_name="wikidata.description", is_active=True
        )
        assert bio_claims.count() == 1

    def test_design_credit_created(self):
        steve = Person.objects.get(name="Steve Ritchie")
        bk = MachineModel.objects.get(name="Black Knight")
        assert Credit.objects.filter(
            person=steve, model=bk, role__slug="design"
        ).exists()

    def test_both_credits_created(self):
        steve = Person.objects.get(name="Steve Ritchie")
        t2 = MachineModel.objects.get(name="Terminator 2: Judgment Day")
        assert Credit.objects.filter(
            person=steve, model=t2, role__slug="design"
        ).exists()

    def test_credit_idempotent(self):
        call_command("ingest_wikidata", from_dump=SAMPLE)
        steve = Person.objects.get(name="Steve Ritchie")
        bk = MachineModel.objects.get(name="Black Knight")
        assert (
            Credit.objects.filter(person=steve, model=bk, role__slug="design").count()
            == 1
        )

    def test_unmatched_machine_skipped(self):
        """Pat Designer's credit points to 'Mystery Machine', not in DB — no crash."""
        assert Credit.objects.filter(person__name="Pat Designer").count() == 0


@pytest.mark.django_db
class TestFromDumpEmpty:
    """Empty dump should not crash and should still create the source."""

    def test_empty_bindings(self, db):
        import json
        import tempfile

        empty: dict[str, object] = {"results": {"bindings": []}}
        data = {"persons": empty, "bio": empty, "credits": empty}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name

        call_command("ingest_wikidata", from_dump=path)
        assert Source.objects.filter(slug="wikidata").exists()
        # No claims or persons created beyond what was already there.
        assert (
            Claim.objects.filter(source=Source.objects.get(slug="wikidata")).count()
            == 0
        )


# ---------------------------------------------------------------------------
# Unit tests for parse_wikidata_date (no DB)
# ---------------------------------------------------------------------------


class TestParseWikidataDate:
    def test_full_day_precision(self):
        assert parse_wikidata_date("+1951-10-15T00:00:00Z", 11) == (1951, 10, 15)

    def test_month_precision(self):
        assert parse_wikidata_date("+1951-10-15T00:00:00Z", 10) == (1951, 10, None)

    def test_year_precision(self):
        assert parse_wikidata_date("+1951-10-15T00:00:00Z", 9) == (1951, None, None)

    def test_decade_precision_returns_none(self):
        assert parse_wikidata_date("+1950-01-01T00:00:00Z", 8) == (None, None, None)

    def test_none_date_returns_none(self):
        assert parse_wikidata_date(None, None) == (None, None, None)

    def test_none_precision_returns_all_components(self):
        assert parse_wikidata_date("+1951-10-15T00:00:00Z", None) == (1951, 10, 15)

    def test_bce_date(self):
        assert parse_wikidata_date("-0044-01-01T00:00:00Z", 9) == (-44, None, None)

    def test_positive_sign_stripped(self):
        year, _, _ = parse_wikidata_date("+2000-06-01T00:00:00Z", 11)
        assert year == 2000
