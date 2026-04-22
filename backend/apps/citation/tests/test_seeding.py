"""Tests for citation source seeding."""

from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command

from apps.citation.models import CitationSource, CitationSourceLink

# -- Small test-only seed lists ------------------------------------------------

_ONE_FLAT = [
    {
        "name": "Test Book",
        "source_type": "book",
        "author": "Test Author",
        "publisher": "Test Publisher",
        "year": 2000,
        "isbn": "9780000000001",
        "description": "A test book.",
    },
]

_WITH_HIERARCHY = [
    {
        "name": "Test Series",
        "source_type": "book",
        "author": "Series Author",
        "publisher": "Series Publisher",
        "description": "A multi-volume series.",
        "children": [
            {
                "name": "Test Series, Vol. 1",
                "source_type": "book",
                "author": "Series Author",
                "publisher": "Series Publisher",
                "year": 1990,
                "isbn": "9780000000010",
                "description": "A multi-volume series. Vol. 1.",
            },
            {
                "name": "Test Series, Vol. 2",
                "source_type": "book",
                "author": "Series Author",
                "publisher": "Series Publisher",
                "year": 1992,
                "isbn": "9780000000020",
                "description": "A multi-volume series. Vol. 2.",
            },
        ],
    },
]

_WITH_LINKS = [
    {
        "name": "Test Website",
        "source_type": "web",
        "description": "A test website.",
        "links": [
            {
                "url": "https://example.com/",
                "label": "Homepage",
                "link_type": "homepage",
            },
        ],
    },
]


# -- TDD tests: write before implementation ------------------------------------


class TestSeedCreatesSources:
    def test_creates_flat_source(self, db):
        from apps.citation.seeding import ensure_citation_sources

        counts = ensure_citation_sources(sources=_ONE_FLAT)

        assert counts["created"] == 1
        assert counts["updated"] == 0
        assert counts["unchanged"] == 0
        obj = CitationSource.objects.get(name="Test Book")
        assert obj.author == "Test Author"
        assert obj.publisher == "Test Publisher"
        assert obj.year == 2000
        assert obj.isbn == "9780000000001"
        assert obj.description == "A test book."

    def test_creates_hierarchy(self, db):
        from apps.citation.seeding import ensure_citation_sources

        counts = ensure_citation_sources(sources=_WITH_HIERARCHY)

        assert counts["created"] == 3  # root + 2 children
        root = CitationSource.objects.get(name="Test Series")
        assert root.parent is None
        children = CitationSource.objects.filter(parent=root).order_by("year")
        assert children.count() == 2
        vol1, vol2 = children
        assert vol1.name == "Test Series, Vol. 1"
        assert vol1.author == "Series Author"
        assert vol1.year == 1990
        assert vol2.name == "Test Series, Vol. 2"
        assert vol2.year == 1992


class TestSeedIdempotent:
    def test_second_run_creates_nothing(self, db):
        from apps.citation.seeding import ensure_citation_sources

        ensure_citation_sources(sources=_WITH_HIERARCHY)
        count_after_first = CitationSource.objects.count()

        counts = ensure_citation_sources(sources=_WITH_HIERARCHY)

        assert counts["created"] == 0
        assert counts["unchanged"] == 3
        assert CitationSource.objects.count() == count_after_first


class TestSeedDetectsUpdates:
    def test_corrects_mutated_author(self, db):
        from apps.citation.seeding import ensure_citation_sources

        ensure_citation_sources(sources=_ONE_FLAT)
        CitationSource.objects.filter(name="Test Book").update(author="Wrong Author")

        counts = ensure_citation_sources(sources=_ONE_FLAT)

        assert counts["updated"] == 1
        assert counts["created"] == 0
        obj = CitationSource.objects.get(name="Test Book")
        assert obj.author == "Test Author"

    def test_update_bumps_updated_at(self, db):
        """Regression: save(update_fields=...) must include updated_at
        or auto_now won't fire."""
        from apps.citation.seeding import ensure_citation_sources

        ensure_citation_sources(sources=_ONE_FLAT)
        obj = CitationSource.objects.get(name="Test Book")
        original_updated_at = obj.updated_at

        CitationSource.objects.filter(name="Test Book").update(author="Wrong Author")

        ensure_citation_sources(sources=_ONE_FLAT)
        obj.refresh_from_db()
        assert obj.updated_at > original_updated_at


class TestSeedCreatesLinks:
    def test_creates_links_for_source(self, db):
        from apps.citation.seeding import ensure_citation_sources

        ensure_citation_sources(sources=_WITH_LINKS)

        src = CitationSource.objects.get(name="Test Website")
        links = CitationSourceLink.objects.filter(citation_source=src)
        assert links.count() == 1
        link = links.first()
        assert link is not None
        assert link.url == "https://example.com/"
        assert link.label == "Homepage"
        assert link.link_type == "homepage"


class TestSeedUpdatesLinkFields:
    def test_corrects_mutated_label(self, db):
        from apps.citation.seeding import ensure_citation_sources

        ensure_citation_sources(sources=_WITH_LINKS)
        CitationSourceLink.objects.filter(url="https://example.com/").update(
            label="Old label"
        )

        ensure_citation_sources(sources=_WITH_LINKS)

        link = CitationSourceLink.objects.get(url="https://example.com/")
        assert link.label == "Homepage"

    def test_corrects_mutated_link_type(self, db):
        from apps.citation.seeding import ensure_citation_sources

        ensure_citation_sources(sources=_WITH_LINKS)
        CitationSourceLink.objects.filter(url="https://example.com/").update(
            link_type="archive"
        )

        ensure_citation_sources(sources=_WITH_LINKS)

        link = CitationSourceLink.objects.get(url="https://example.com/")
        assert link.link_type == "homepage"


class TestSeedHierarchy:
    def test_children_have_correct_parent_and_inherited_fields(self, db):
        from apps.citation.seeding import ensure_citation_sources

        ensure_citation_sources(sources=_WITH_HIERARCHY)

        root = CitationSource.objects.get(name="Test Series")
        vol1 = CitationSource.objects.get(isbn="9780000000010")
        vol2 = CitationSource.objects.get(isbn="9780000000020")

        assert vol1.parent_id == root.pk
        assert vol2.parent_id == root.pk
        # Children carry their own author/publisher (inherited in seed data)
        assert vol1.author == "Series Author"
        assert vol1.publisher == "Series Publisher"


class TestSeedRollsBackOnValidationError:
    def test_invalid_data_rolls_back_all(self, db):
        from apps.citation.seeding import ensure_citation_sources

        bad_seed = [
            {
                "name": "Good Book",
                "source_type": "book",
                "year": 2000,
            },
            {
                "name": "Bad Book",
                "source_type": "book",
                "year": 9999,  # exceeds YEAR_MAX (2100)
            },
        ]

        with pytest.raises(ValidationError):
            ensure_citation_sources(sources=bad_seed)

        # Nothing should have been created — transaction rolled back
        assert CitationSource.objects.count() == 0


class TestSeedAmbiguousLookupFails:
    def test_duplicate_name_type_raises(self, db):
        from apps.citation.seeding import ensure_citation_sources

        # Manually create two sources with the same name+type
        CitationSource.objects.create(name="Ambiguous", source_type="web")
        CitationSource.objects.create(name="Ambiguous", source_type="web")

        seed = [{"name": "Ambiguous", "source_type": "web"}]

        with pytest.raises(Exception, match=r"[Mm]ultiple"):
            ensure_citation_sources(sources=seed)


# -- Post-implementation tests (need real seed data) ---------------------------


class TestSeedRealData:
    def test_real_data_creates_expected_sources(self, db):
        from apps.citation.seeding import ensure_citation_sources

        counts = ensure_citation_sources()  # uses _SEED_SOURCES

        assert counts["created"] > 0
        assert counts["updated"] == 0
        assert counts["unchanged"] == 0

        # Spot-check: a multi-edition root
        assert CitationSource.objects.filter(
            name="The Encyclopedia of Pinball", source_type="book"
        ).exists()

        # Spot-check: an ISBN-bearing edition
        assert CitationSource.objects.filter(isbn="9781889933009").exists()

        # Spot-check: a web source with link
        ipdb = CitationSource.objects.get(name="Internet Pinball Database (IPDB)")
        assert ipdb.source_type == "web"
        assert CitationSourceLink.objects.filter(
            citation_source=ipdb, url="https://www.ipdb.org/"
        ).exists()

        # Spot-check: a flat single-edition book
        wizardry = CitationSource.objects.get(name="Pinball Wizardry")
        assert wizardry.isbn == "9780136762218"
        assert wizardry.year == 1979
        assert wizardry.parent is None

        # Spot-check: a magazine source
        play_meter = CitationSource.objects.get(name="Play Meter")
        assert play_meter.source_type == "magazine"
        assert play_meter.year == 1974

        # Spot-check: identifier_key set on IPDB and OPDB
        assert ipdb.identifier_key == "ipdb"
        opdb = CitationSource.objects.get(name="Online Pinball Database (OPDB)")
        assert opdb.identifier_key == "opdb"


class TestManagementCommand:
    def test_command_output(self, db):
        out = StringIO()
        call_command("seed_citation_sources", stdout=out)
        output = out.getvalue()
        assert "created" in output
        assert "updated" in output
        assert "unchanged" in output
