"""Tests for citation API endpoints."""

from __future__ import annotations

import json

import pytest

from apps.citation.models import CitationSource, CitationSourceLink

pytestmark = pytest.mark.django_db


def _post(client, path, body):
    return client.post(path, data=json.dumps(body), content_type="application/json")


def _patch(client, path, body):
    return client.patch(path, data=json.dumps(body), content_type="application/json")


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSearchCitationSources:
    def test_anonymous_gets_401(self, client):
        resp = client.get("/api/citation-sources/search/?q=test")
        assert resp.status_code in (401, 403)

    def test_empty_q_returns_empty_list(self, client, user):
        client.force_login(user)
        resp = client.get("/api/citation-sources/search/?q=")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_whitespace_q_returns_empty_list(self, client, user):
        client.force_login(user)
        resp = client.get("/api/citation-sources/search/?q=   ")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_search_by_name(self, client, user, citation_source):
        client.force_login(user)
        resp = client.get("/api/citation-sources/search/?q=Encyclopedia")
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 1
        assert results[0]["name"] == citation_source.name

    def test_search_by_author(self, client, user, citation_source_full):
        client.force_login(user)
        resp = client.get("/api/citation-sources/search/?q=Bueschel")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_search_by_publisher(self, client, user, citation_source_full):
        client.force_login(user)
        resp = client.get("/api/citation-sources/search/?q=Silverball")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_search_by_isbn(self, client, user, citation_source_full):
        client.force_login(user)
        resp = client.get("/api/citation-sources/search/?q=0964359219")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_search_by_linked_url(
        self, client, user, citation_source, citation_source_link
    ):
        client.force_login(user)
        resp = client.get("/api/citation-sources/search/?q=archive.org")
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 1
        assert results[0]["id"] == citation_source.pk

    def test_search_case_insensitive(self, client, user, citation_source):
        client.force_login(user)
        resp = client.get("/api/citation-sources/search/?q=encyclopedia")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_search_max_20_results(self, client, user, db):
        for i in range(25):
            CitationSource.objects.create(name=f"Test Source {i}", source_type="book")
        client.force_login(user)
        resp = client.get("/api/citation-sources/search/?q=Test Source")
        assert resp.status_code == 200
        assert len(resp.json()) <= 20

    def test_search_response_shape(self, client, user, citation_source_full):
        client.force_login(user)
        resp = client.get("/api/citation-sources/search/?q=Encyclopedia")
        data = resp.json()[0]
        assert set(data.keys()) == {
            "id",
            "name",
            "source_type",
            "author",
            "publisher",
            "year",
            "isbn",
            "parent_id",
            "has_children",
            "is_abstract",
            "skip_locator",
            "child_input_mode",
            "identifier_key",
        }

    def test_search_returns_identifier_key(self, client, user, db):
        """Search results include identifier_key when set on the source."""
        CitationSource.objects.create(
            name="Internet Pinball Database",
            source_type="web",
            identifier_key="ipdb",
        )
        client.force_login(user)
        resp = client.get("/api/citation-sources/search/?q=Internet Pinball")
        assert resp.status_code == 200
        data = resp.json()[0]
        assert data["identifier_key"] == "ipdb"

    def test_search_returns_empty_identifier_key(self, client, user, citation_source):
        """Search results return empty string for sources without identifier_key."""
        client.force_login(user)
        resp = client.get("/api/citation-sources/search/?q=Encyclopedia")
        assert resp.status_code == 200
        data = resp.json()[0]
        assert data["identifier_key"] == ""


class TestSearchComputedFields:
    """Tests for is_abstract, skip_locator, and child_input_mode on search results."""

    def test_root_book_no_children(self, client, user, db):
        """A standalone book: not abstract, needs locator, no child mode."""
        CitationSource.objects.create(name="Solo Book", source_type="book")
        client.force_login(user)
        resp = client.get("/api/citation-sources/search/?q=Solo Book")
        data = resp.json()[0]
        assert data["is_abstract"] is False
        assert data["skip_locator"] is False
        assert data["child_input_mode"] is None

    def test_root_book_with_children(self, client, user, db):
        """A book with editions: abstract, search_children mode."""
        parent = CitationSource.objects.create(name="Big Book", source_type="book")
        CitationSource.objects.create(
            name="Big Book Ed. 1", source_type="book", parent=parent
        )
        client.force_login(user)
        resp = client.get("/api/citation-sources/search/?q=Big Book")
        # Find the parent in results
        results = {r["id"]: r for r in resp.json()}
        data = results[parent.pk]
        assert data["is_abstract"] is True
        assert data["skip_locator"] is False
        assert data["child_input_mode"] == "search_children"

    def test_root_web_source(self, client, user, db):
        """A root web source (e.g. IPDB): abstract, enter_identifier mode."""
        CitationSource.objects.create(
            name="Internet Pinball Database", source_type="web"
        )
        client.force_login(user)
        resp = client.get("/api/citation-sources/search/?q=Internet Pinball")
        data = resp.json()[0]
        assert data["is_abstract"] is True
        assert data["skip_locator"] is False
        assert data["child_input_mode"] == "enter_identifier"

    def test_child_web_source(self, client, user, db):
        """A child web source (e.g. IPDB machine page): skip locator."""
        parent = CitationSource.objects.create(
            name="Internet Pinball Database", source_type="web"
        )
        child = CitationSource.objects.create(
            name="IPDB Machine 4836", source_type="web", parent=parent
        )
        client.force_login(user)
        resp = client.get("/api/citation-sources/search/?q=IPDB Machine")
        results = {r["id"]: r for r in resp.json()}
        data = results[child.pk]
        assert data["is_abstract"] is False
        assert data["skip_locator"] is True
        assert data["child_input_mode"] is None

    def test_root_magazine(self, client, user, db):
        """A root magazine: abstract, search_children mode."""
        CitationSource.objects.create(name="Pinball Magazine", source_type="magazine")
        client.force_login(user)
        resp = client.get("/api/citation-sources/search/?q=Pinball Magazine")
        data = resp.json()[0]
        assert data["is_abstract"] is True
        assert data["skip_locator"] is False
        assert data["child_input_mode"] == "search_children"


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreateCitationSource:
    def test_anonymous_gets_401(self, client):
        resp = _post(
            client, "/api/citation-sources/", {"name": "X", "source_type": "book"}
        )
        assert resp.status_code in (401, 403)

    def test_minimal_create(self, client, user):
        client.force_login(user)
        resp = _post(
            client,
            "/api/citation-sources/",
            {
                "name": "Test Book",
                "source_type": "book",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Book"
        assert data["source_type"] == "book"
        assert data["author"] == ""
        assert data["links"] == []
        assert data["children"] == []

    def test_full_create(self, client, user):
        client.force_login(user)
        resp = _post(
            client,
            "/api/citation-sources/",
            {
                "name": "The Encyclopedia of Pinball Vol 1",
                "source_type": "book",
                "author": "Richard Bueschel",
                "publisher": "Silverball Amusements",
                "year": 1996,
                "month": 6,
                "day": 15,
                "date_note": "",
                "isbn": "1234567890",
                "description": "A great book.",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["year"] == 1996
        assert data["month"] == 6
        assert data["isbn"] == "1234567890"

    def test_create_with_parent(self, client, user, citation_source):
        client.force_login(user)
        resp = _post(
            client,
            "/api/citation-sources/",
            {
                "name": "Edition 2",
                "source_type": "book",
                "parent_id": citation_source.pk,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["parent"]["id"] == citation_source.pk
        assert data["parent"]["name"] == citation_source.name

    def test_create_sets_created_by_and_updated_by(self, client, user):
        client.force_login(user)
        _post(
            client,
            "/api/citation-sources/",
            {
                "name": "Test",
                "source_type": "book",
            },
        )
        source = CitationSource.objects.get(name="Test")
        assert source.created_by == user
        assert source.updated_by == user

    def test_invalid_source_type_returns_422(self, client, user):
        client.force_login(user)
        resp = _post(
            client,
            "/api/citation-sources/",
            {
                "name": "Test",
                "source_type": "podcast",
            },
        )
        assert resp.status_code == 422

    def test_empty_name_returns_422(self, client, user):
        client.force_login(user)
        resp = _post(
            client,
            "/api/citation-sources/",
            {
                "name": "",
                "source_type": "book",
            },
        )
        assert resp.status_code == 422

    def test_duplicate_isbn_returns_422(self, client, user, citation_source_full):
        client.force_login(user)
        resp = _post(
            client,
            "/api/citation-sources/",
            {
                "name": "Another Book",
                "source_type": "book",
                "isbn": citation_source_full.isbn,
            },
        )
        assert resp.status_code == 422

    def test_month_without_year_returns_422(self, client, user):
        client.force_login(user)
        resp = _post(
            client,
            "/api/citation-sources/",
            {
                "name": "Test",
                "source_type": "book",
                "month": 6,
            },
        )
        assert resp.status_code == 422

    def test_day_without_month_returns_422(self, client, user):
        client.force_login(user)
        resp = _post(
            client,
            "/api/citation-sources/",
            {
                "name": "Test",
                "source_type": "book",
                "year": 1996,
                "day": 15,
            },
        )
        assert resp.status_code == 422

    def test_nonexistent_parent_returns_404(self, client, user):
        client.force_login(user)
        resp = _post(
            client,
            "/api/citation-sources/",
            {
                "name": "Test",
                "source_type": "book",
                "parent_id": 99999,
            },
        )
        assert resp.status_code == 404

    def test_mojibake_name_returns_422(self, client, user):
        client.force_login(user)
        resp = _post(
            client,
            "/api/citation-sources/",
            {
                "name": "Ã©ncyclopedia",
                "source_type": "book",
            },
        )
        assert resp.status_code == 422


class TestCreateCitationSourceWithLink:
    """Atomic source + link creation via the optional url field."""

    def test_create_with_url_creates_source_and_link(self, client, user):
        client.force_login(user)
        resp = _post(
            client,
            "/api/citation-sources/",
            {
                "name": "Pinball Wiki Page",
                "source_type": "web",
                "url": "https://example.com/pinball",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Pinball Wiki Page"
        assert len(data["links"]) == 1
        assert data["links"][0]["url"] == "https://example.com/pinball"

    def test_create_with_url_and_link_label(self, client, user):
        client.force_login(user)
        resp = _post(
            client,
            "/api/citation-sources/",
            {
                "name": "Archive Page",
                "source_type": "web",
                "url": "https://archive.org/details/pinball",
                "link_label": "archive.org",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["links"][0]["label"] == "archive.org"

    def test_create_without_url_creates_no_link(self, client, user):
        client.force_login(user)
        resp = _post(
            client,
            "/api/citation-sources/",
            {
                "name": "A Book",
                "source_type": "book",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["links"] == []

    def test_invalid_url_returns_422_and_creates_no_source(self, client, user):
        client.force_login(user)
        resp = _post(
            client,
            "/api/citation-sources/",
            {
                "name": "Bad Link Source",
                "source_type": "web",
                "url": "not-a-url",
            },
        )
        assert resp.status_code == 422
        assert not CitationSource.objects.filter(name="Bad Link Source").exists()

    def test_link_sets_created_by(self, client, user):
        client.force_login(user)
        resp = _post(
            client,
            "/api/citation-sources/",
            {
                "name": "Test Web",
                "source_type": "web",
                "url": "https://example.com",
            },
        )
        assert resp.status_code == 201
        link = CitationSourceLink.objects.get(citation_source_id=resp.json()["id"])
        assert link.created_by == user


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------


class TestGetCitationSourceDetail:
    def test_anonymous_gets_401(self, client, citation_source):
        resp = client.get(f"/api/citation-sources/{citation_source.pk}/")
        assert resp.status_code in (401, 403)

    def test_get_existing_source(self, client, user, citation_source):
        client.force_login(user)
        resp = client.get(f"/api/citation-sources/{citation_source.pk}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == citation_source.name
        assert data["id"] == citation_source.pk

    def test_get_source_with_links_and_children(
        self,
        client,
        user,
        citation_source,
        citation_source_link,
        citation_source_with_parent,
    ):
        client.force_login(user)
        resp = client.get(f"/api/citation-sources/{citation_source.pk}/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["links"]) == 1
        assert data["links"][0]["url"] == citation_source_link.url
        assert len(data["children"]) == 1
        assert data["children"][0]["id"] == citation_source_with_parent.pk

    def test_nonexistent_returns_404(self, client, user):
        client.force_login(user)
        resp = client.get("/api/citation-sources/99999/")
        assert resp.status_code == 404

    def test_detail_includes_skip_locator(self, client, user, db):
        """Detail response includes skip_locator field."""
        parent = CitationSource.objects.create(
            name="Internet Pinball Database", source_type="web"
        )
        child = CitationSource.objects.create(
            name="IPDB Machine 1000", source_type="web", parent=parent
        )
        client.force_login(user)
        resp = client.get(f"/api/citation-sources/{child.pk}/")
        assert resp.status_code == 200
        assert resp.json()["skip_locator"] is True

    def test_detail_skip_locator_false_for_book(self, client, user, citation_source):
        """Detail response: skip_locator is false for non-web sources."""
        client.force_login(user)
        resp = client.get(f"/api/citation-sources/{citation_source.pk}/")
        assert resp.status_code == 200
        assert resp.json()["skip_locator"] is False

    def test_detail_children_include_skip_locator(self, client, user, db):
        """Children in detail response include skip_locator."""
        parent = CitationSource.objects.create(
            name="Internet Pinball Database", source_type="web"
        )
        CitationSource.objects.create(
            name="IPDB Machine 2000", source_type="web", parent=parent
        )
        client.force_login(user)
        resp = client.get(f"/api/citation-sources/{parent.pk}/")
        data = resp.json()
        assert len(data["children"]) == 1
        assert data["children"][0]["skip_locator"] is True

    def test_detail_children_include_urls(self, client, user, db):
        """Children in detail response include their link URLs."""
        parent = CitationSource.objects.create(
            name="Internet Pinball Database", source_type="web"
        )
        child = CitationSource.objects.create(
            name="IPDB Machine 3000", source_type="web", parent=parent
        )
        CitationSourceLink.objects.create(
            citation_source=child,
            link_type="homepage",
            url="https://www.ipdb.org/machine.cgi?id=3000",
        )
        client.force_login(user)
        resp = client.get(f"/api/citation-sources/{parent.pk}/")
        data = resp.json()
        assert len(data["children"]) == 1
        assert data["children"][0]["urls"] == [
            "https://www.ipdb.org/machine.cgi?id=3000"
        ]

    def test_detail_children_urls_empty_when_no_links(self, client, user, db):
        """Children with no links have an empty urls list."""
        parent = CitationSource.objects.create(name="Big Book", source_type="book")
        CitationSource.objects.create(
            name="Edition 1", source_type="book", parent=parent
        )
        client.force_login(user)
        resp = client.get(f"/api/citation-sources/{parent.pk}/")
        data = resp.json()
        assert len(data["children"]) == 1
        assert data["children"][0]["urls"] == []


# ---------------------------------------------------------------------------
# Children (filtered)
# ---------------------------------------------------------------------------


class TestListChildren:
    """Tests for GET /api/citation-sources/{id}/children/?q=..."""

    def test_anonymous_gets_401(self, client, citation_source):
        resp = client.get(f"/api/citation-sources/{citation_source.pk}/children/")
        assert resp.status_code in (401, 403)

    def test_empty_q_returns_empty_list(self, client, user, db):
        parent = CitationSource.objects.create(
            name="Internet Pinball Database", source_type="web"
        )
        CitationSource.objects.create(
            name="IPDB Machine 1000", source_type="web", parent=parent
        )
        client.force_login(user)
        resp = client.get(f"/api/citation-sources/{parent.pk}/children/?q=")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_filter_by_child_name(self, client, user, db):
        parent = CitationSource.objects.create(
            name="Internet Pinball Database", source_type="web"
        )
        match = CitationSource.objects.create(
            name="IPDB Machine 4836", source_type="web", parent=parent
        )
        CitationSource.objects.create(
            name="IPDB Machine 9999", source_type="web", parent=parent
        )
        client.force_login(user)
        resp = client.get(f"/api/citation-sources/{parent.pk}/children/?q=4836")
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 1
        assert results[0]["id"] == match.pk

    def test_filter_by_child_url(self, client, user, db):
        parent = CitationSource.objects.create(
            name="Internet Pinball Database", source_type="web"
        )
        child = CitationSource.objects.create(
            name="IPDB Machine 4836", source_type="web", parent=parent
        )
        CitationSourceLink.objects.create(
            citation_source=child,
            link_type="homepage",
            url="https://www.ipdb.org/machine.cgi?id=4836",
        )
        CitationSource.objects.create(
            name="IPDB Machine 9999", source_type="web", parent=parent
        )
        client.force_login(user)
        resp = client.get(
            f"/api/citation-sources/{parent.pk}/children/?q=ipdb.org/machine.cgi?id=4836"
        )
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 1
        assert results[0]["id"] == child.pk
        assert results[0]["urls"] == ["https://www.ipdb.org/machine.cgi?id=4836"]

    def test_response_shape_matches_child_schema(self, client, user, db):
        parent = CitationSource.objects.create(
            name="Internet Pinball Database", source_type="web"
        )
        child = CitationSource.objects.create(
            name="IPDB Machine 5000", source_type="web", parent=parent, year=2020
        )
        CitationSourceLink.objects.create(
            citation_source=child,
            link_type="homepage",
            url="https://www.ipdb.org/machine.cgi?id=5000",
        )
        client.force_login(user)
        resp = client.get(f"/api/citation-sources/{parent.pk}/children/?q=5000")
        data = resp.json()[0]
        assert set(data.keys()) == {
            "id",
            "name",
            "source_type",
            "year",
            "isbn",
            "skip_locator",
            "urls",
        }

    def test_max_20_results(self, client, user, db):
        parent = CitationSource.objects.create(
            name="Internet Pinball Database", source_type="web"
        )
        for i in range(25):
            CitationSource.objects.create(
                name=f"IPDB Machine {i}", source_type="web", parent=parent
            )
        client.force_login(user)
        resp = client.get(f"/api/citation-sources/{parent.pk}/children/?q=IPDB")
        assert resp.status_code == 200
        assert len(resp.json()) <= 20

    def test_nonexistent_parent_returns_404(self, client, user):
        client.force_login(user)
        resp = client.get("/api/citation-sources/99999/children/?q=test")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class TestUpdateCitationSource:
    def test_anonymous_gets_401(self, client, citation_source):
        resp = _patch(
            client,
            f"/api/citation-sources/{citation_source.pk}/",
            {
                "name": "New Name",
            },
        )
        assert resp.status_code in (401, 403)

    def test_partial_update_name_only(self, client, user, citation_source):
        client.force_login(user)
        resp = _patch(
            client,
            f"/api/citation-sources/{citation_source.pk}/",
            {
                "name": "Updated Name",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    def test_partial_update_preserves_unchanged_fields(
        self, client, user, citation_source_full
    ):
        client.force_login(user)
        resp = _patch(
            client,
            f"/api/citation-sources/{citation_source_full.pk}/",
            {
                "name": "Updated",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated"
        assert data["author"] == citation_source_full.author
        assert data["year"] == citation_source_full.year

    def test_update_sets_updated_by(self, client, user, citation_source):
        client.force_login(user)
        _patch(
            client,
            f"/api/citation-sources/{citation_source.pk}/",
            {
                "name": "Updated",
            },
        )
        citation_source.refresh_from_db()
        assert citation_source.updated_by == user

    def test_clear_nullable_field(self, client, user, citation_source_full):
        client.force_login(user)
        resp = _patch(
            client,
            f"/api/citation-sources/{citation_source_full.pk}/",
            {
                "year": None,
                "month": None,
                "day": None,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["year"] is None
        assert data["month"] is None

    def test_clear_isbn_via_empty_string(self, client, user, citation_source_full):
        client.force_login(user)
        resp = _patch(
            client,
            f"/api/citation-sources/{citation_source_full.pk}/",
            {
                "isbn": "",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["isbn"] is None

    def test_null_coercion_for_string_field(self, client, user, citation_source_full):
        """Sending null for a non-nullable string field coerces to empty string."""
        client.force_login(user)
        resp = _patch(
            client,
            f"/api/citation-sources/{citation_source_full.pk}/",
            {
                "author": None,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["author"] == ""

    def test_duplicate_isbn_returns_422(self, client, user, citation_source_full):
        other = CitationSource.objects.create(
            name="Other", source_type="book", isbn="9999999999"
        )
        client.force_login(user)
        resp = _patch(
            client,
            f"/api/citation-sources/{citation_source_full.pk}/",
            {
                "isbn": other.isbn,
            },
        )
        assert resp.status_code == 422

    def test_no_changes_returns_422(self, client, user, citation_source):
        client.force_login(user)
        resp = _patch(client, f"/api/citation-sources/{citation_source.pk}/", {})
        assert resp.status_code == 422

    def test_nonexistent_returns_404(self, client, user):
        client.force_login(user)
        resp = _patch(client, "/api/citation-sources/99999/", {"name": "X"})
        assert resp.status_code == 404

    def test_day_without_month_after_merge_returns_422(self, client, user):
        """PATCH day on a source with year but no month should fail."""
        source = CitationSource.objects.create(
            name="Test", source_type="book", year=1996
        )
        client.force_login(user)
        resp = _patch(
            client,
            f"/api/citation-sources/{source.pk}/",
            {
                "day": 15,
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Create Link
# ---------------------------------------------------------------------------


class TestCreateCitationSourceLink:
    def test_anonymous_gets_401(self, client, citation_source):
        resp = _post(
            client,
            f"/api/citation-sources/{citation_source.pk}/links/",
            {"link_type": "homepage", "url": "https://example.com"},
        )
        assert resp.status_code in (401, 403)

    def test_create_link(self, client, user, citation_source):
        client.force_login(user)
        resp = _post(
            client,
            f"/api/citation-sources/{citation_source.pk}/links/",
            {"link_type": "catalog", "url": "https://example.com", "label": "Example"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["link_type"] == "catalog"
        assert data["url"] == "https://example.com"
        assert data["label"] == "Example"

    def test_create_link_sets_created_by(self, client, user, citation_source):
        client.force_login(user)
        _post(
            client,
            f"/api/citation-sources/{citation_source.pk}/links/",
            {"link_type": "homepage", "url": "https://example.com"},
        )
        link = CitationSourceLink.objects.get(citation_source=citation_source)
        assert link.created_by == user
        assert link.updated_by == user

    def test_duplicate_url_returns_422(
        self, client, user, citation_source, citation_source_link
    ):
        client.force_login(user)
        resp = _post(
            client,
            f"/api/citation-sources/{citation_source.pk}/links/",
            {"link_type": "homepage", "url": citation_source_link.url},
        )
        assert resp.status_code == 422

    def test_nonexistent_source_returns_404(self, client, user):
        client.force_login(user)
        resp = _post(
            client,
            "/api/citation-sources/99999/links/",
            {"link_type": "homepage", "url": "https://example.com"},
        )
        assert resp.status_code == 404

    def test_invalid_url_returns_422(self, client, user, citation_source):
        client.force_login(user)
        resp = _post(
            client,
            f"/api/citation-sources/{citation_source.pk}/links/",
            {"link_type": "homepage", "url": "not-a-url"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Update Link
# ---------------------------------------------------------------------------


class TestUpdateCitationSourceLink:
    def test_anonymous_gets_401(self, client, citation_source, citation_source_link):
        resp = _patch(
            client,
            f"/api/citation-sources/{citation_source.pk}/links/{citation_source_link.pk}/",
            {"label": "new"},
        )
        assert resp.status_code in (401, 403)

    def test_update_url(self, client, user, citation_source, citation_source_link):
        client.force_login(user)
        resp = _patch(
            client,
            f"/api/citation-sources/{citation_source.pk}/links/{citation_source_link.pk}/",
            {"url": "https://new-url.com"},
        )
        assert resp.status_code == 200
        assert resp.json()["url"] == "https://new-url.com"

    def test_update_label(self, client, user, citation_source, citation_source_link):
        client.force_login(user)
        resp = _patch(
            client,
            f"/api/citation-sources/{citation_source.pk}/links/{citation_source_link.pk}/",
            {"label": "updated label"},
        )
        assert resp.status_code == 200
        assert resp.json()["label"] == "updated label"

    def test_update_sets_updated_by(
        self, client, user, citation_source, citation_source_link
    ):
        client.force_login(user)
        _patch(
            client,
            f"/api/citation-sources/{citation_source.pk}/links/{citation_source_link.pk}/",
            {"label": "updated"},
        )
        citation_source_link.refresh_from_db()
        assert citation_source_link.updated_by == user

    def test_link_on_wrong_source_returns_404(self, client, user, citation_source_link):
        other_source = CitationSource.objects.create(name="Other", source_type="web")
        client.force_login(user)
        resp = _patch(
            client,
            f"/api/citation-sources/{other_source.pk}/links/{citation_source_link.pk}/",
            {"label": "hack"},
        )
        assert resp.status_code == 404

    def test_no_changes_returns_422(
        self, client, user, citation_source, citation_source_link
    ):
        client.force_login(user)
        resp = _patch(
            client,
            f"/api/citation-sources/{citation_source.pk}/links/{citation_source_link.pk}/",
            {},
        )
        assert resp.status_code == 422

    def test_duplicate_url_returns_422(
        self, client, user, citation_source, citation_source_link
    ):
        CitationSourceLink.objects.create(
            citation_source=citation_source,
            link_type="homepage",
            url="https://other.com",
            label="other",
        )
        client.force_login(user)
        resp = _patch(
            client,
            f"/api/citation-sources/{citation_source.pk}/links/{citation_source_link.pk}/",
            {"url": "https://other.com"},
        )
        assert resp.status_code == 422
