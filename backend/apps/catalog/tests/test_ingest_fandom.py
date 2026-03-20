"""Tests for the ingest_fandom command and fandom_wiki module."""

import pytest
from django.core.management import call_command

from apps.catalog.ingestion.fandom_wiki import (
    FandomCredit,
    FandomPerson,
    _extract_prose,
    _parse_company_template,
    _parse_infobox_credits,
    parse_game_pages,
    parse_manufacturer_pages,
    parse_person_pages,
)
from apps.catalog.models import Credit, CreditRole, MachineModel, Manufacturer, Person
from apps.provenance.models import Claim, Source

FIXTURES = "apps/catalog/tests/fixtures"
SAMPLE = f"{FIXTURES}/fandom_sample.json"
PERSONS_SAMPLE = f"{FIXTURES}/fandom_persons_sample.json"
MANUFACTURERS_SAMPLE = f"{FIXTURES}/fandom_manufacturers_sample.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _seed_db(db, credit_roles):
    """Pre-seed the DB with machines and persons for matching."""
    addams = MachineModel.objects.create(name="The Addams Family", year=1992)
    medieval = MachineModel.objects.create(name="Medieval Madness", year=1997)

    pat = Person.objects.create(name="Pat Lawlor")
    john_y = Person.objects.create(name="John Youssi")
    brian = Person.objects.create(name="Brian Eddy")

    # Greg Freres is in the fixture for Medieval Madness but NOT in the DB.

    # Pre-existing credit (should not be duplicated on re-run).
    role = CreditRole.objects.get(slug="design")
    Credit.objects.create(model=addams, person=pat, role=role)

    return {
        "addams": addams,
        "medieval": medieval,
        "pat": pat,
        "john_y": john_y,
        "brian": brian,
    }


@pytest.fixture
def _run_fandom(_seed_db):
    """Run ingest_fandom using the sample fixtures (no network calls)."""
    call_command(
        "ingest_fandom",
        from_dump=SAMPLE,
        from_dump_persons=PERSONS_SAMPLE,
        from_dump_manufacturers=MANUFACTURERS_SAMPLE,
    )


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.usefixtures("_run_fandom")
class TestIngestFandom:
    def test_creates_source(self):
        source = Source.objects.get(slug="fandom")
        assert source.name == "Pinball Wiki (Fandom)"
        assert source.priority == 20
        assert source.source_type == "wiki"

    def test_art_credit_created(self):
        """John Youssi's art credit for The Addams Family should be created."""
        addams = MachineModel.objects.get(name="The Addams Family")
        john_y = Person.objects.get(name="John Youssi")
        assert Credit.objects.filter(
            model=addams, person=john_y, role__slug="art"
        ).exists()

    def test_animation_credit_created(self):
        """Scott Slomiany is not in the DB — credit should be skipped."""
        # Scott Slomiany is not seeded in the DB.
        assert not Person.objects.filter(name="Scott Slomiany").exists()

    def test_existing_design_credit_not_duplicated(self):
        """Pat Lawlor's existing design credit must not be duplicated."""
        addams = MachineModel.objects.get(name="The Addams Family")
        pat = Person.objects.get(name="Pat Lawlor")
        assert (
            Credit.objects.filter(model=addams, person=pat, role__slug="design").count()
            == 1
        )

    def test_medieval_madness_design_credit(self):
        medieval = MachineModel.objects.get(name="Medieval Madness")
        brian = Person.objects.get(name="Brian Eddy")
        assert Credit.objects.filter(
            model=medieval, person=brian, role__slug="design"
        ).exists()

    def test_unmatched_game_skipped(self):
        """'Unknown Game That Is Not In DB' must not crash and not create credits."""
        assert not MachineModel.objects.filter(
            name="Unknown Game That Is Not In DB"
        ).exists()

    def test_no_infobox_game_skipped(self):
        """Pages without an infobox should produce no credits and not crash."""
        assert not MachineModel.objects.filter(name="No Infobox Game").exists()

    def test_idempotent(self):
        """Running twice must not duplicate credits."""
        call_command(
            "ingest_fandom",
            from_dump=SAMPLE,
            from_dump_persons=PERSONS_SAMPLE,
            from_dump_manufacturers=MANUFACTURERS_SAMPLE,
        )
        addams = MachineModel.objects.get(name="The Addams Family")
        john_y = Person.objects.get(name="John Youssi")
        assert (
            Credit.objects.filter(model=addams, person=john_y, role__slug="art").count()
            == 1
        )


@pytest.mark.django_db
class TestFromDumpEmpty:
    """Empty dump should not crash and should still create the source."""

    def test_empty_games(self, db):
        import json
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"games": []}, f)
            games_path = f.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"persons": []}, f)
            persons_path = f.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"manufacturers": []}, f)
            mfrs_path = f.name

        call_command(
            "ingest_fandom",
            from_dump=games_path,
            from_dump_persons=persons_path,
            from_dump_manufacturers=mfrs_path,
        )
        assert Source.objects.filter(slug="fandom").exists()
        assert Credit.objects.count() == 0


# ---------------------------------------------------------------------------
# Unit tests for parse functions (no DB)
# ---------------------------------------------------------------------------


class TestParseInfboxCredits:
    ADDAMS_WIKITEXT = (
        "{{Infobox Title | title = The Addams Family\n"
        "|designer = '''Designers''': [[Pat Lawlor]]<br>"
        "'''Artwork''': [[John Youssi]]<br>"
        "'''Dots/Animation''': [[Scott Slomiany]]<br>"
        "'''Mechanics''': [[John Krutsch]]<br>"
        "'''Sounds/Music''': [[Chris Granner]]<br>"
        "'''Software''': [[Larry DeMar]], [[Mike Boon]]\n"
        "}}"
    )

    def test_design_credit(self):
        credits = _parse_infobox_credits(self.ADDAMS_WIKITEXT)
        assert FandomCredit(person_name="Pat Lawlor", role="design") in credits

    def test_art_credit(self):
        credits = _parse_infobox_credits(self.ADDAMS_WIKITEXT)
        assert FandomCredit(person_name="John Youssi", role="art") in credits

    def test_animation_credit(self):
        credits = _parse_infobox_credits(self.ADDAMS_WIKITEXT)
        assert FandomCredit(person_name="Scott Slomiany", role="animation") in credits

    def test_mechanics_credit(self):
        credits = _parse_infobox_credits(self.ADDAMS_WIKITEXT)
        assert FandomCredit(person_name="John Krutsch", role="mechanics") in credits

    def test_music_credit(self):
        credits = _parse_infobox_credits(self.ADDAMS_WIKITEXT)
        assert FandomCredit(person_name="Chris Granner", role="music") in credits

    def test_software_credits_multiple(self):
        credits = _parse_infobox_credits(self.ADDAMS_WIKITEXT)
        assert FandomCredit(person_name="Larry DeMar", role="software") in credits
        assert FandomCredit(person_name="Mike Boon", role="software") in credits

    def test_no_infobox_returns_empty(self):
        assert _parse_infobox_credits("No infobox here.") == []

    def test_infobox_without_designer_returns_empty(self):
        wikitext = "{{Infobox Title | title = Foo\n|manufacturer = [[Bally]]\n}}"
        assert _parse_infobox_credits(wikitext) == []

    def test_plain_name_without_wikilink(self):
        """Names not wrapped in [[]] should still be parsed."""
        wikitext = (
            "{{Infobox Title\n|designer = '''Software''': Larry DeMar, Mike Boon\n}}"
        )
        credits = _parse_infobox_credits(wikitext)
        assert FandomCredit(person_name="Larry DeMar", role="software") in credits
        assert FandomCredit(person_name="Mike Boon", role="software") in credits

    def test_br_self_closing_variant(self):
        """<br/> and <br /> variants should also split segments."""
        wikitext = (
            "{{Infobox Title\n"
            "|designer = '''Designers''': [[Alice]]<br/>'''Artwork''': [[Bob]]\n"
            "}}"
        )
        credits = _parse_infobox_credits(wikitext)
        assert FandomCredit(person_name="Alice", role="design") in credits
        assert FandomCredit(person_name="Bob", role="art") in credits

    def test_wikilink_with_display_text(self):
        """[[Display|Target]] should use the display text (first part)."""
        wikitext = (
            "{{Infobox Title\n|designer = '''Designers''': [[Pat Lawlor|Pat]]\n}}"
        )
        credits = _parse_infobox_credits(wikitext)
        assert FandomCredit(person_name="Pat Lawlor", role="design") in credits

    def test_unknown_label_skipped(self):
        """Labels not in the role map should be silently ignored."""
        wikitext = (
            "{{Infobox Title\n"
            "|designer = '''Gibberish Label''': [[Alice]]<br>'''Designers''': [[Bob]]\n"
            "}}"
        )
        credits = _parse_infobox_credits(wikitext)
        names = [c.person_name for c in credits]
        assert "Alice" not in names
        assert "Bob" in names


class TestParseGamePages:
    def test_sorted_by_title(self):
        data = {
            "games": [
                {"page_id": 2, "title": "Zork", "wikitext": ""},
                {"page_id": 1, "title": "Addams", "wikitext": ""},
            ]
        }
        games = parse_game_pages(data)
        assert games[0].title == "Addams"
        assert games[1].title == "Zork"

    def test_citation_url_uses_underscores(self):
        data = {
            "games": [
                {"page_id": 1, "title": "The Addams Family", "wikitext": ""},
            ]
        }
        games = parse_game_pages(data)
        assert (
            games[0].citation_url == "https://pinball.fandom.com/wiki/The_Addams_Family"
        )

    def test_empty_games_returns_empty_list(self):
        assert parse_game_pages({"games": []}) == []


# ---------------------------------------------------------------------------
# Integration tests — persons
# ---------------------------------------------------------------------------


@pytest.fixture
def _seed_persons_db(db, credit_roles):
    """Seed DB for person ingestion tests."""
    addams = MachineModel.objects.create(name="The Addams Family", year=1992)
    pat = Person.objects.create(name="Pat Lawlor")
    role = CreditRole.objects.get(slug="design")
    Credit.objects.create(model=addams, person=pat, role=role)
    return {"addams": addams, "pat": pat}


@pytest.mark.django_db
class TestIngestFandomPersons:
    def test_existing_person_not_duplicated(self, _seed_persons_db):
        """Pat Lawlor is already in the DB — must not be duplicated."""
        call_command(
            "ingest_fandom",
            from_dump=SAMPLE,
            from_dump_persons=PERSONS_SAMPLE,
            from_dump_manufacturers=MANUFACTURERS_SAMPLE,
        )
        assert Person.objects.filter(name="Pat Lawlor").count() == 1

    def test_new_person_created(self, _seed_persons_db):
        """'New Artist' is in the persons dump but not the DB — should be created."""
        call_command(
            "ingest_fandom",
            from_dump=SAMPLE,
            from_dump_persons=PERSONS_SAMPLE,
            from_dump_manufacturers=MANUFACTURERS_SAMPLE,
        )
        assert Person.objects.filter(name="New Artist").exists()

    def test_redirect_page_skipped(self, _seed_persons_db):
        """Redirect pages must not create person records."""
        call_command(
            "ingest_fandom",
            from_dump=SAMPLE,
            from_dump_persons=PERSONS_SAMPLE,
            from_dump_manufacturers=MANUFACTURERS_SAMPLE,
        )
        assert not Person.objects.filter(name="Bally").exists()

    def test_bio_claim_asserted_for_existing_person(self, _seed_persons_db):
        """A bio claim should be asserted for Pat Lawlor from his Fandom page."""
        call_command(
            "ingest_fandom",
            from_dump=SAMPLE,
            from_dump_persons=PERSONS_SAMPLE,
            from_dump_manufacturers=MANUFACTURERS_SAMPLE,
        )
        pat = Person.objects.get(name="Pat Lawlor")
        assert Claim.objects.filter(object_id=pat.pk, field_name="fandom.bio").exists()

    def test_bio_resolved_into_extra_data(self, _seed_persons_db):
        """resolve_person() should populate Person.extra_data from the Fandom claim."""
        call_command(
            "ingest_fandom",
            from_dump=SAMPLE,
            from_dump_persons=PERSONS_SAMPLE,
            from_dump_manufacturers=MANUFACTURERS_SAMPLE,
        )
        pat = Person.objects.get(name="Pat Lawlor")
        assert pat.extra_data.get("fandom.bio", "") != ""

    def test_idempotent_persons(self, _seed_persons_db):
        """Running twice must not duplicate persons or claims."""
        call_command(
            "ingest_fandom",
            from_dump=SAMPLE,
            from_dump_persons=PERSONS_SAMPLE,
            from_dump_manufacturers=MANUFACTURERS_SAMPLE,
        )
        call_command(
            "ingest_fandom",
            from_dump=SAMPLE,
            from_dump_persons=PERSONS_SAMPLE,
            from_dump_manufacturers=MANUFACTURERS_SAMPLE,
        )
        assert Person.objects.filter(name="Pat Lawlor").count() == 1
        assert Person.objects.filter(name="New Artist").count() == 1


# ---------------------------------------------------------------------------
# Integration tests — manufacturers
# ---------------------------------------------------------------------------


@pytest.fixture
def _seed_manufacturers_db(db):
    """Seed DB for manufacturer ingestion tests."""
    williams = Manufacturer.objects.create(name="Williams Electronics")
    return {"williams": williams}


@pytest.mark.django_db
class TestIngestFandomManufacturers:
    def test_year_start_claim_asserted(self, _seed_manufacturers_db):
        """year_start claim should be created for Williams Electronics."""
        call_command(
            "ingest_fandom",
            from_dump=SAMPLE,
            from_dump_persons=PERSONS_SAMPLE,
            from_dump_manufacturers=MANUFACTURERS_SAMPLE,
        )
        williams = Manufacturer.objects.get(name="Williams Electronics")
        # year_start, year_end, headquarters are now on CorporateEntity.
        # Fandom ingest no longer creates claims for these fields on Manufacturer.
        assert Claim.objects.filter(
            object_id=williams.pk, field_name="fandom.description"
        ).exists()

    def test_unmatched_manufacturer_not_created(self, _seed_manufacturers_db):
        """'Unknown Co' is in the dump but not the DB — must NOT be created."""
        call_command(
            "ingest_fandom",
            from_dump=SAMPLE,
            from_dump_persons=PERSONS_SAMPLE,
            from_dump_manufacturers=MANUFACTURERS_SAMPLE,
        )
        assert not Manufacturer.objects.filter(name="Unknown Co").exists()

    def test_redirect_manufacturer_skipped(self, _seed_manufacturers_db):
        """Redirect pages must not create manufacturer records."""
        call_command(
            "ingest_fandom",
            from_dump=SAMPLE,
            from_dump_persons=PERSONS_SAMPLE,
            from_dump_manufacturers=MANUFACTURERS_SAMPLE,
        )
        assert not Manufacturer.objects.filter(name="Bally").exists()

    def test_idempotent_manufacturers(self, _seed_manufacturers_db):
        """Running twice must not duplicate claims."""
        call_command(
            "ingest_fandom",
            from_dump=SAMPLE,
            from_dump_persons=PERSONS_SAMPLE,
            from_dump_manufacturers=MANUFACTURERS_SAMPLE,
        )
        call_command(
            "ingest_fandom",
            from_dump=SAMPLE,
            from_dump_persons=PERSONS_SAMPLE,
            from_dump_manufacturers=MANUFACTURERS_SAMPLE,
        )
        williams = Manufacturer.objects.get(name="Williams Electronics")
        assert (
            Claim.objects.filter(
                object_id=williams.pk, field_name="fandom.description"
            ).count()
            == 1
        )


# ---------------------------------------------------------------------------
# Unit tests — prose extraction and Company template parsing
# ---------------------------------------------------------------------------


class TestExtractProse:
    def test_strips_stub_template(self):
        wikitext = "{{stub}}\n\n'''Pat Lawlor''' is a designer.\n"
        assert _extract_prose(wikitext) == "Pat Lawlor is a designer."

    def test_strips_wikilinks(self):
        wikitext = (
            "'''Alice''' works for [[Bally]] and [[Williams Electronics|Williams]].\n"
        )
        result = _extract_prose(wikitext)
        assert "Bally" in result
        assert "Williams" in result
        assert "[[" not in result

    def test_strips_bold_apostrophes(self):
        wikitext = "'''Bob Smith''' is a pinball artist.\n"
        assert _extract_prose(wikitext) == "Bob Smith is a pinball artist."

    def test_skips_headings(self):
        wikitext = "{{stub}}\n== Credits ==\n'''Alice''' is an artist.\n"
        assert _extract_prose(wikitext) == "Alice is an artist."

    def test_skips_category_links(self):
        wikitext = "[[Category:People|Smith, Bob]]\n'''Bob Smith''' is a designer.\n"
        result = _extract_prose(wikitext)
        assert result == "Bob Smith is a designer."

    def test_empty_wikitext_returns_empty(self):
        assert _extract_prose("") == ""

    def test_redirect_page_returns_empty(self):
        assert _extract_prose("#REDIRECT [[Midway Manufacturing Company]]") == ""


class TestParseCompanyTemplate:
    WILLIAMS_WIKITEXT = (
        "{{Company\n"
        "  | title1=Williams Electronics\n"
        "  | founded=1943\n"
        "  | defunct=1999\n"
        "  | headquarters=Chicago, Illinois\n"
        "  | website=[http://www.williams.com/ www.williams.com]\n"
        "}}\n"
        "'''Williams Electronics''' was a major pinball manufacturer.\n"
    )

    def test_year_start(self):
        result = _parse_company_template(self.WILLIAMS_WIKITEXT)
        assert result["year_start"] == 1943

    def test_year_end(self):
        result = _parse_company_template(self.WILLIAMS_WIKITEXT)
        assert result["year_end"] == 1999

    def test_headquarters(self):
        result = _parse_company_template(self.WILLIAMS_WIKITEXT)
        assert result["headquarters"] == "Chicago, Illinois"

    def test_website_strips_external_link_markup(self):
        result = _parse_company_template(self.WILLIAMS_WIKITEXT)
        assert result["website"] == "http://www.williams.com/"

    def test_no_company_template_returns_none(self):
        assert _parse_company_template("No template here.") is None

    def test_missing_fields_return_none_or_empty(self):
        wikitext = "{{Company\n  | title1=Minimal Co\n}}\n"
        result = _parse_company_template(wikitext)
        assert result is not None
        assert result["year_start"] is None
        assert result["year_end"] is None
        assert result["headquarters"] == ""


class TestParsePersonPages:
    def test_redirect_skipped(self):
        data = {
            "persons": [
                {"page_id": 1, "title": "Bally", "wikitext": "#REDIRECT [[Midway]]"}
            ]
        }
        assert parse_person_pages(data) == []

    def test_bio_extracted(self):
        data = {
            "persons": [
                {
                    "page_id": 1,
                    "title": "Pat Lawlor",
                    "wikitext": "{{stub}}\n\n'''Pat Lawlor''' is a designer.\n",
                }
            ]
        }
        persons = parse_person_pages(data)
        assert len(persons) == 1
        assert persons[0].bio == "Pat Lawlor is a designer."

    def test_sorted_by_title(self):
        data = {
            "persons": [
                {"page_id": 2, "title": "Steve Ritchie", "wikitext": ""},
                {"page_id": 1, "title": "Pat Lawlor", "wikitext": ""},
            ]
        }
        persons = parse_person_pages(data)
        assert persons[0].title == "Pat Lawlor"
        assert persons[1].title == "Steve Ritchie"

    def test_citation_url(self):
        data = {"persons": [{"page_id": 1, "title": "Pat Lawlor", "wikitext": ""}]}
        persons = parse_person_pages(data)
        assert persons[0].citation_url == "https://pinball.fandom.com/wiki/Pat_Lawlor"

    def test_returns_fandom_person_type(self):
        data = {
            "persons": [{"page_id": 1, "title": "Pat Lawlor", "wikitext": "stub text"}]
        }
        persons = parse_person_pages(data)
        assert isinstance(persons[0], FandomPerson)


class TestParseManufacturerPages:
    def test_redirect_skipped(self):
        data = {
            "manufacturers": [
                {"page_id": 1, "title": "Bally", "wikitext": "#REDIRECT [[Midway]]"}
            ]
        }
        assert parse_manufacturer_pages(data) == []

    def test_year_start_parsed(self):
        data = {
            "manufacturers": [
                {
                    "page_id": 1,
                    "title": "Williams Electronics",
                    "wikitext": "{{Company\n  | founded=1943\n}}\nSome text.\n",
                }
            ]
        }
        mfrs = parse_manufacturer_pages(data)
        assert mfrs[0].year_start == 1943

    def test_no_company_template_still_included(self):
        """Pages without {{Company}} are included (description only)."""
        data = {
            "manufacturers": [
                {
                    "page_id": 1,
                    "title": "Stub Co",
                    "wikitext": "'''Stub Co''' is a company.\n",
                }
            ]
        }
        mfrs = parse_manufacturer_pages(data)
        assert len(mfrs) == 1
        assert mfrs[0].year_start is None

    def test_sorted_by_title(self):
        data = {
            "manufacturers": [
                {"page_id": 2, "title": "Williams", "wikitext": ""},
                {"page_id": 1, "title": "Bally Manufacturing", "wikitext": ""},
            ]
        }
        mfrs = parse_manufacturer_pages(data)
        assert mfrs[0].title == "Bally Manufacturing"
