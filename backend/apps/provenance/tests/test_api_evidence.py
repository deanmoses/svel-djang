"""Tests for cited edit evidence endpoint."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from apps.catalog.models import Title
from apps.citation.models import CitationSource, CitationSourceLink
from apps.provenance.models import ChangeSet, CitationInstance, Claim, Source

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="editor")


@pytest.fixture
def bootstrap_source(db):
    return Source.objects.create(
        name="Bootstrap", slug="bootstrap", source_type="editorial", priority=100
    )


@pytest.fixture
def title(db, bootstrap_source):
    title = Title.objects.create(name="Medieval Madness", slug="medieval-madness")
    Claim.objects.assert_claim(
        title, "name", "Medieval Madness", source=bootstrap_source
    )
    return title


@pytest.fixture
def citation_source(db):
    source = CitationSource.objects.create(name="Williams Flyer", source_type="web")
    CitationSourceLink.objects.create(
        citation_source=source,
        link_type="homepage",
        url="https://example.com/flyer",
        label="Scan",
    )
    return source


def _attach_citation(claim, citation_source, locator="p. 2"):
    return CitationInstance.objects.create(
        citation_source=citation_source,
        claim=claim,
        locator=locator,
    )


@pytest.mark.django_db
class TestCitedEditEvidence:
    def test_returns_cited_changesets_with_fields_and_citation_details(
        self, client, user, title, citation_source
    ):
        changeset = ChangeSet.objects.create(user=user, note="Documented the flyer")
        year_claim = Claim.objects.assert_claim(
            title, "name", "Medieval Madness (1997)", user=user, changeset=changeset
        )
        desc_claim = Claim.objects.assert_claim(
            title, "description", "Updated copy", user=user, changeset=changeset
        )
        _attach_citation(year_claim, citation_source)
        _attach_citation(desc_claim, citation_source)

        resp = client.get("/api/pages/evidence/title/medieval-madness/")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["note"] == "Documented the flyer"
        assert set(data[0]["fields"]) == {"description", "name"}
        assert len(data[0]["citations"]) == 1
        assert data[0]["citations"][0]["source_name"] == "Williams Flyer"
        assert data[0]["citations"][0]["locator"] == "p. 2"
        assert data[0]["citations"][0]["links"] == [
            {"url": "https://example.com/flyer", "label": "Scan"}
        ]

    def test_coalesces_repeated_copied_claim_citations(
        self, client, user, title, citation_source
    ):
        changeset = ChangeSet.objects.create(user=user, note="Grouped edit")
        first_claim = Claim.objects.assert_claim(
            title, "name", "Medieval Madness (1997)", user=user, changeset=changeset
        )
        second_claim = Claim.objects.assert_claim(
            title, "description", "Updated copy", user=user, changeset=changeset
        )
        _attach_citation(first_claim, citation_source, locator="p. 3")
        _attach_citation(second_claim, citation_source, locator="p. 3")

        resp = client.get("/api/pages/evidence/title/medieval-madness/")

        assert resp.status_code == 200
        assert len(resp.json()[0]["citations"]) == 1

    def test_omits_uncited_changesets(self, client, user, title, citation_source):
        uncited = ChangeSet.objects.create(user=user, note="Uncited cleanup")
        cited = ChangeSet.objects.create(user=user, note="Cited update")
        Claim.objects.assert_claim(
            title, "description", "Cleanup", user=user, changeset=uncited
        )
        cited_claim = Claim.objects.assert_claim(
            title, "name", "Medieval Madness (1997)", user=user, changeset=cited
        )
        _attach_citation(cited_claim, citation_source)

        resp = client.get("/api/pages/evidence/title/medieval-madness/")

        assert resp.status_code == 200
        assert [item["note"] for item in resp.json()] == ["Cited update"]
