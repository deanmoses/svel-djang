"""Tests for CitationSource and CitationSourceLink model behavior."""

import pytest
from django.db.models import ProtectedError

from apps.citation.models import CitationSource, CitationSourceLink


class TestCitationSourceStr:
    def test_name_only(self, db):
        cs = CitationSource.objects.create(name="IPDB", source_type="web")
        assert str(cs) == "IPDB"

    def test_name_and_year(self, db):
        cs = CitationSource.objects.create(
            name="The Encyclopedia of Pinball", source_type="book", year=1996
        )
        assert str(cs) == "The Encyclopedia of Pinball (1996)"

    def test_name_author_year(self, db):
        cs = CitationSource.objects.create(
            name="The Encyclopedia of Pinball",
            source_type="book",
            author="Richard Bueschel",
            year=1996,
        )
        assert str(cs) == "The Encyclopedia of Pinball (Richard Bueschel, 1996)"


class TestCitationSourceTimestamps:
    def test_timestamps_set_on_create(self, citation_source):
        assert citation_source.created_at is not None
        assert citation_source.updated_at is not None

    def test_updated_at_changes_on_save(self, citation_source):
        original = citation_source.updated_at
        citation_source.author = "Updated Author"
        citation_source.save()
        citation_source.refresh_from_db()
        assert citation_source.updated_at > original


class TestCitationSourceRelationships:
    def test_children_relationship(self, citation_source):
        child = CitationSource.objects.create(
            name="Child", source_type="book", parent=citation_source
        )
        assert child in citation_source.children.all()

    def test_links_relationship(self, citation_source, citation_source_link):
        assert citation_source_link in citation_source.links.all()

    def test_cascade_deletes_links(self, citation_source, citation_source_link):
        link_pk = citation_source_link.pk
        citation_source.delete()
        assert not CitationSourceLink.objects.filter(pk=link_pk).exists()

    def test_protect_prevents_parent_delete(self, citation_source_with_parent):
        parent = citation_source_with_parent.parent
        with pytest.raises(ProtectedError):
            parent.delete()


class TestCitationSourceLinkStr:
    def test_with_label(self, citation_source_link):
        assert str(citation_source_link) == (
            "archive.org scan (https://archive.org/details/encyclopedia-of-pinball)"
        )

    def test_without_label(self, citation_source):
        link = CitationSourceLink.objects.create(
            citation_source=citation_source,
            link_type="homepage",
            url="https://example.com",
        )
        assert str(link) == "https://example.com"
