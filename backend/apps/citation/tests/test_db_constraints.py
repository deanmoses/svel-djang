"""Tests for database-level CHECK constraints on citation models.

Verifies that constraints enforce ranges, cross-field invariants, non-blank
rules, nullable IDs, and self-referential anti-cycles at the DB level —
independent of Python validators.
"""

import pytest
from django.db import IntegrityError, connection

from apps.citation.models import CitationSource, CitationSourceLink


def _raw_update(model, pk, **fields):
    """Bypass ORM validation with a raw SQL UPDATE."""
    table = model._meta.db_table
    sets = ", ".join(f"{col} = %s" for col in fields)
    with connection.cursor() as cur:
        cur.execute(f"UPDATE {table} SET {sets} WHERE id = %s", [*fields.values(), pk])


# ---------------------------------------------------------------------------
# CitationSource: non-blank constraints
# ---------------------------------------------------------------------------


class TestCitationSourceNonBlank:
    def test_empty_name_rejected(self, db):
        with pytest.raises(IntegrityError):
            CitationSource.objects.create(name="", source_type="book")

    def test_empty_source_type_rejected(self, db):
        with pytest.raises(IntegrityError):
            CitationSource.objects.create(name="Test", source_type="")


# ---------------------------------------------------------------------------
# CitationSource: source_type enum
# ---------------------------------------------------------------------------


class TestCitationSourceType:
    def test_invalid_source_type_rejected(self, db):
        with pytest.raises(IntegrityError):
            CitationSource.objects.create(name="Test", source_type="invalid")

    @pytest.mark.parametrize("source_type", ["book", "magazine", "web"])
    def test_valid_source_type_accepted(self, db, source_type):
        cs = CitationSource.objects.create(name="Test", source_type=source_type)
        assert cs.pk is not None


# ---------------------------------------------------------------------------
# CitationSource: identifier_key enum
# ---------------------------------------------------------------------------


class TestCitationSourceIdentifierKey:
    def test_invalid_identifier_key_rejected(self, db):
        with pytest.raises(IntegrityError):
            CitationSource.objects.create(
                name="Test", source_type="web", identifier_key="bogus"
            )

    def test_empty_identifier_key_accepted(self, db):
        cs = CitationSource.objects.create(name="Test", source_type="web")
        assert cs.identifier_key == ""

    @pytest.mark.parametrize("key", ["ipdb", "opdb"])
    def test_valid_identifier_key_accepted(self, db, key):
        cs = CitationSource.objects.create(
            name="Test", source_type="web", identifier_key=key
        )
        assert cs.identifier_key == key


# ---------------------------------------------------------------------------
# CitationSource: self-reference
# ---------------------------------------------------------------------------


class TestCitationSourceParent:
    def test_parent_self_reference_rejected(self, citation_source):
        with pytest.raises(IntegrityError):
            _raw_update(
                CitationSource, citation_source.pk, parent_id=citation_source.pk
            )

    def test_valid_parent_accepted(self, citation_source):
        child = CitationSource.objects.create(
            name="Child", source_type="book", parent=citation_source
        )
        assert child.parent_id == citation_source.pk

    def test_null_parent_accepted(self, db):
        cs = CitationSource.objects.create(name="Root", source_type="book")
        assert cs.parent_id is None


# ---------------------------------------------------------------------------
# CitationSource: year/month/day ranges
# ---------------------------------------------------------------------------


class TestCitationSourceDateRanges:
    @pytest.fixture
    def source(self, db):
        return CitationSource.objects.create(
            name="Test", source_type="book", year=1992, month=6, day=15
        )

    def test_year_above_max_rejected(self, source):
        with pytest.raises(IntegrityError):
            _raw_update(CitationSource, source.pk, year=2101)

    def test_year_below_min_rejected(self, source):
        with pytest.raises(IntegrityError):
            _raw_update(CitationSource, source.pk, year=1799)

    def test_year_at_min_accepted(self, source):
        _raw_update(CitationSource, source.pk, year=1800)
        source.refresh_from_db()
        assert source.year == 1800

    def test_year_at_max_accepted(self, source):
        _raw_update(CitationSource, source.pk, year=2100)
        source.refresh_from_db()
        assert source.year == 2100

    def test_month_zero_rejected(self, source):
        with pytest.raises(IntegrityError):
            _raw_update(CitationSource, source.pk, month=0)

    def test_month_thirteen_rejected(self, source):
        with pytest.raises(IntegrityError):
            _raw_update(CitationSource, source.pk, month=13)

    def test_day_zero_rejected(self, source):
        with pytest.raises(IntegrityError):
            _raw_update(CitationSource, source.pk, day=0)

    def test_day_thirty_two_rejected(self, source):
        with pytest.raises(IntegrityError):
            _raw_update(CitationSource, source.pk, day=32)


# ---------------------------------------------------------------------------
# CitationSource: date component chains
# ---------------------------------------------------------------------------


class TestCitationSourceDateChains:
    def test_month_without_year_rejected(self, db):
        with pytest.raises(IntegrityError):
            CitationSource.objects.create(
                name="Test", source_type="book", month=6, year=None
            )

    def test_day_without_month_rejected(self, db):
        with pytest.raises(IntegrityError):
            CitationSource.objects.create(
                name="Test", source_type="book", year=1992, day=15, month=None
            )

    def test_year_only_accepted(self, db):
        cs = CitationSource.objects.create(name="Test", source_type="book", year=1992)
        assert cs.month is None
        assert cs.day is None

    def test_year_month_accepted(self, db):
        cs = CitationSource.objects.create(
            name="Test", source_type="book", year=1992, month=6
        )
        assert cs.day is None

    def test_year_month_day_accepted(self, db):
        cs = CitationSource.objects.create(
            name="Test", source_type="book", year=1992, month=6, day=15
        )
        assert cs.pk is not None


# ---------------------------------------------------------------------------
# CitationSource: ISBN (nullable unique)
# ---------------------------------------------------------------------------


class TestCitationSourceISBN:
    def test_empty_isbn_rejected(self, db):
        cs = CitationSource.objects.create(
            name="Test", source_type="book", isbn="1234567890"
        )
        with pytest.raises(IntegrityError):
            _raw_update(CitationSource, cs.pk, isbn="")

    def test_null_isbn_accepted(self, db):
        cs = CitationSource.objects.create(name="Test", source_type="book")
        assert cs.isbn is None

    def test_duplicate_isbn_rejected(self, db):
        CitationSource.objects.create(
            name="Book A", source_type="book", isbn="1234567890"
        )
        with pytest.raises(IntegrityError):
            CitationSource.objects.create(
                name="Book B", source_type="book", isbn="1234567890"
            )


# ---------------------------------------------------------------------------
# CitationSourceLink constraints
# ---------------------------------------------------------------------------


class TestCitationSourceLinkConstraints:
    def test_valid_link(self, citation_source):
        link = CitationSourceLink.objects.create(
            citation_source=citation_source,
            link_type="homepage",
            url="https://example.com",
        )
        assert link.pk is not None

    def test_valid_link_with_label(self, citation_source):
        link = CitationSourceLink.objects.create(
            citation_source=citation_source,
            link_type="homepage",
            url="https://example.com",
            label="Example",
        )
        assert link.label == "Example"

    def test_empty_url_rejected(self, citation_source):
        with pytest.raises(IntegrityError):
            CitationSourceLink.objects.create(
                citation_source=citation_source,
                link_type="homepage",
                url="",
            )

    def test_duplicate_url_same_source_rejected(self, citation_source):
        CitationSourceLink.objects.create(
            citation_source=citation_source,
            link_type="homepage",
            url="https://example.com",
        )
        with pytest.raises(IntegrityError):
            CitationSourceLink.objects.create(
                citation_source=citation_source,
                link_type="homepage",
                url="https://example.com",
            )

    def test_duplicate_url_different_source_accepted(self, citation_source):
        CitationSourceLink.objects.create(
            citation_source=citation_source,
            link_type="homepage",
            url="https://example.com",
        )
        other = CitationSource.objects.create(name="Other", source_type="web")
        link = CitationSourceLink.objects.create(
            citation_source=other,
            link_type="homepage",
            url="https://example.com",
        )
        assert link.pk is not None

    @pytest.mark.parametrize(
        "link_type", ["homepage", "catalog", "publisher", "reference", "archive"]
    )
    def test_valid_link_types_accepted(self, citation_source, link_type):
        link = CitationSourceLink.objects.create(
            citation_source=citation_source,
            link_type=link_type,
            url=f"https://example.com/{link_type}",
        )
        assert link.pk is not None

    def test_invalid_link_type_rejected(self, citation_source):
        with pytest.raises(IntegrityError):
            CitationSourceLink.objects.create(
                citation_source=citation_source,
                link_type="bogus",
                url="https://example.com",
            )

    def test_empty_link_type_rejected(self, citation_source):
        with pytest.raises(IntegrityError):
            CitationSourceLink.objects.create(
                citation_source=citation_source,
                link_type="",
                url="https://example.com",
            )
