import pytest

from apps.citation.models import CitationSource, CitationSourceLink


@pytest.fixture
def citation_source(db):
    """Minimal CitationSource — name + source_type only."""
    return CitationSource.objects.create(
        name="The Encyclopedia of Pinball",
        source_type="book",
    )


@pytest.fixture
def citation_source_full(db):
    """CitationSource with all optional fields populated."""
    return CitationSource.objects.create(
        name="The Encyclopedia of Pinball - Edition 1",
        source_type="book",
        author="Richard Bueschel",
        publisher="Silverball Amusements",
        year=1996,
        month=6,
        day=15,
        date_note="",
        isbn="0964359219",
        description="First edition hardcover.",
    )


@pytest.fixture
def citation_source_with_parent(db, citation_source):
    """A child CitationSource with parent set."""
    return CitationSource.objects.create(
        name="The Encyclopedia of Pinball - Edition 1",
        source_type="book",
        parent=citation_source,
    )


@pytest.fixture
def citation_source_link(db, citation_source):
    """CitationSourceLink on citation_source."""
    return CitationSourceLink.objects.create(
        citation_source=citation_source,
        url="https://archive.org/details/encyclopedia-of-pinball",
        label="archive.org scan",
    )
