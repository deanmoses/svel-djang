"""Tests for GET /api/pages/edit-history/{entity_type}/{public_id}/ endpoint."""

import pytest
from django.contrib.auth import get_user_model

from apps.catalog.tests.conftest import make_machine_model
from apps.provenance.models import Claim, Source

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="editor")


@pytest.fixture
def _bootstrap_source(db):
    """Low-priority source for seeding name claims."""
    return Source.objects.create(
        name="Bootstrap", slug="bootstrap", source_type="editorial", priority=1
    )


@pytest.fixture
def source(db):
    return Source.objects.create(name="IPDB", source_type="database", priority=10)


@pytest.fixture
def pm(db, _bootstrap_source):
    pm = make_machine_model(name="Medieval Madness", slug="medieval-madness", year=1997)
    Claim.objects.assert_claim(pm, "name", "Medieval Madness", source=_bootstrap_source)
    return pm


@pytest.mark.django_db
class TestEditHistoryEmpty:
    def test_no_changesets_returns_empty_list(self, client, pm):
        resp = client.get(f"/api/pages/edit-history/model/{pm.slug}/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_nonexistent_slug_returns_404(self, client):
        resp = client.get("/api/pages/edit-history/model/does-not-exist/")
        assert resp.status_code == 404

    def test_source_claims_not_included(self, client, pm, source):
        """Source-attributed claims (no changeset) should not appear."""
        Claim.objects.assert_claim(pm, "year", 1998, source=source)
        resp = client.get(f"/api/pages/edit-history/model/{pm.slug}/")
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.django_db
class TestEditHistoryBasic:
    def test_single_changeset_returned(self, client, user, pm):
        """A single edit session shows up with field changes."""
        client.force_login(user)
        client.patch(
            f"/api/models/{pm.slug}/claims/",
            data='{"fields": {"year": 1998}}',
            content_type="application/json",
        )

        resp = client.get(f"/api/pages/edit-history/model/{pm.slug}/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

        cs = data[0]
        assert cs["user_display"] == "editor"
        assert cs["note"] == ""
        assert len(cs["changes"]) == 1
        assert cs["changes"][0]["field_name"] == "year"
        assert cs["changes"][0]["new_value"] == 1998
        # First edit — no old value
        assert cs["changes"][0]["old_value"] is None

    def test_old_value_shown_on_second_edit(self, client, user, pm):
        """When a field is edited twice, the second changeset shows old→new."""
        client.force_login(user)
        client.patch(
            f"/api/models/{pm.slug}/claims/",
            data='{"fields": {"year": 1998}}',
            content_type="application/json",
        )
        client.patch(
            f"/api/models/{pm.slug}/claims/",
            data='{"fields": {"year": 1999}}',
            content_type="application/json",
        )

        resp = client.get(f"/api/pages/edit-history/model/{pm.slug}/")
        data = resp.json()
        assert len(data) == 2

        # Most recent first
        newest = data[0]
        assert newest["changes"][0]["field_name"] == "year"
        assert newest["changes"][0]["old_value"] == 1998
        assert newest["changes"][0]["new_value"] == 1999

        oldest = data[1]
        assert oldest["changes"][0]["old_value"] is None
        assert oldest["changes"][0]["new_value"] == 1998


@pytest.mark.django_db
class TestEditHistoryMultipleFields:
    def test_multi_field_changeset(self, client, user, pm):
        """A single edit that changes multiple fields shows all changes."""
        client.force_login(user)
        client.patch(
            f"/api/models/{pm.slug}/claims/",
            data='{"fields": {"year": 1998, "player_count": 4}}',
            content_type="application/json",
        )

        resp = client.get(f"/api/pages/edit-history/model/{pm.slug}/")
        data = resp.json()
        assert len(data) == 1

        field_names = {c["field_name"] for c in data[0]["changes"]}
        assert field_names == {"year", "player_count"}


@pytest.mark.django_db
class TestEditHistoryMultiUser:
    def test_old_value_scoped_to_same_user(self, client, user, pm, db):
        """User B editing after User A should not show User A's value as old."""
        user_b = User.objects.create_user(username="other")

        client.force_login(user)
        client.patch(
            f"/api/models/{pm.slug}/claims/",
            data='{"fields": {"year": 1998}}',
            content_type="application/json",
        )
        client.force_login(user_b)
        client.patch(
            f"/api/models/{pm.slug}/claims/",
            data='{"fields": {"year": 1999}}',
            content_type="application/json",
        )

        resp = client.get(f"/api/pages/edit-history/model/{pm.slug}/")
        data = resp.json()
        assert len(data) == 2

        # User B's edit is newest — no old value because B never edited year before
        assert data[0]["user_display"] == "other"
        assert data[0]["changes"][0]["old_value"] is None
        assert data[0]["changes"][0]["new_value"] == 1999

        # User A's edit — also no old value (first edit)
        assert data[1]["user_display"] == "editor"
        assert data[1]["changes"][0]["old_value"] is None
        assert data[1]["changes"][0]["new_value"] == 1998


@pytest.mark.django_db
class TestEditHistoryOrdering:
    def test_newest_first(self, client, user, pm):
        """Changesets are returned newest first."""
        client.force_login(user)
        client.patch(
            f"/api/models/{pm.slug}/claims/",
            data='{"fields": {"year": 1998}}',
            content_type="application/json",
        )
        client.patch(
            f"/api/models/{pm.slug}/claims/",
            data='{"fields": {"player_count": 4}}',
            content_type="application/json",
        )

        resp = client.get(f"/api/pages/edit-history/model/{pm.slug}/")
        data = resp.json()
        assert len(data) == 2
        # Newest changeset (player_count) first
        assert data[0]["changes"][0]["field_name"] == "player_count"
        assert data[1]["changes"][0]["field_name"] == "year"


@pytest.mark.django_db
class TestEditHistorySoftDeleted:
    def test_soft_deleted_entity_still_returns_history(self, client, user, pm):
        """Soft-delete is soft: audit trail remains inspectable by public_id.

        Policy: provenance surfaces intentionally use the default manager
        (not ``.active()``) so deleted entities keep their history visible
        to direct API callers. See ``edit_history_page`` docstring.
        """
        client.force_login(user)
        client.patch(
            f"/api/models/{pm.slug}/claims/",
            data='{"fields": {"year": 1998}}',
            content_type="application/json",
        )
        pm.status = "deleted"
        pm.save(update_fields=["status"])

        resp = client.get(f"/api/pages/edit-history/model/{pm.slug}/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["changes"][0]["new_value"] == 1998


@pytest.mark.django_db
class TestEditHistoryEntityTypeGuard:
    def test_unknown_entity_type_returns_404(self, client):
        resp = client.get("/api/pages/edit-history/nonexistent/some-slug/")
        assert resp.status_code == 404

    def test_non_linkable_entity_type_returns_404(self, client):
        """Models that aren't LinkableModel subclasses (e.g. Location) should be rejected."""
        resp = client.get("/api/pages/edit-history/location/some-slug/")
        assert resp.status_code == 404
