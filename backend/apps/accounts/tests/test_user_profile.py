"""Tests for GET /api/users/{username}/ endpoint."""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from apps.catalog.models import MachineModel, Manufacturer
from apps.provenance.models import Claim, Source

User = get_user_model()


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="historian")


@pytest.fixture
def bootstrap_source(db):
    return Source.objects.create(
        name="Bootstrap", slug="bootstrap", source_type="editorial", priority=1
    )


@pytest.fixture
def manufacturer(db, bootstrap_source):
    mfr = Manufacturer.objects.create(name="Williams", slug="williams")
    Claim.objects.assert_claim(mfr, "name", "Williams", source=bootstrap_source)
    return mfr


@pytest.fixture
def model_a(db, bootstrap_source):
    pm = MachineModel.objects.create(
        name="Medieval Madness", slug="medieval-madness", year=1997
    )
    Claim.objects.assert_claim(pm, "name", "Medieval Madness", source=bootstrap_source)
    return pm


@pytest.fixture
def model_b(db, bootstrap_source):
    pm = MachineModel.objects.create(
        name="Attack from Mars", slug="attack-from-mars", year=1995
    )
    Claim.objects.assert_claim(pm, "name", "Attack from Mars", source=bootstrap_source)
    return pm


@pytest.mark.django_db
class TestUserProfileNotFound:
    def test_nonexistent_user_returns_404(self, client):
        resp = client.get("/api/users/nonexistent/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestUserProfileEmpty:
    def test_user_with_no_edits(self, client, user):
        resp = client.get(f"/api/users/{user.username}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "historian"
        assert data["edit_count"] == 0
        assert data["entities_edited"] == []
        assert data["recent_edits"] == []
        assert "member_since" in data


@pytest.mark.django_db
class TestUserProfileWithEdits:
    def test_single_entity_edit(self, client, user, model_a):
        """Editing one entity shows up in both entities_edited and recent_edits."""
        client.force_login(user)
        client.patch(
            f"/api/models/{model_a.slug}/claims/",
            data='{"fields": {"year": 1998}}',
            content_type="application/json",
        )

        resp = client.get(f"/api/users/{user.username}/")
        assert resp.status_code == 200
        data = resp.json()

        assert data["edit_count"] == 1
        assert len(data["entities_edited"]) == 1

        entity = data["entities_edited"][0]
        assert entity["entity_href"] == "/models/medieval-madness"
        assert entity["entity_name"] == "Medieval Madness"
        assert entity["entity_type_label"] == "Model"
        assert entity["edit_count"] == 1

        assert len(data["recent_edits"]) == 1
        edit = data["recent_edits"][0]
        assert edit["entity_href"] == "/models/medieval-madness"
        assert edit["entity_name"] == "Medieval Madness"

    def test_multiple_entity_edits_ordered_by_recency(
        self, client, user, model_a, model_b
    ):
        """Entities are ordered by most recently edited."""
        client.force_login(user)
        # Edit model_a first
        client.patch(
            f"/api/models/{model_a.slug}/claims/",
            data='{"fields": {"year": 1998}}',
            content_type="application/json",
        )
        # Edit model_b second (more recent)
        client.patch(
            f"/api/models/{model_b.slug}/claims/",
            data='{"fields": {"year": 1996}}',
            content_type="application/json",
        )

        resp = client.get(f"/api/users/{user.username}/")
        data = resp.json()

        assert data["edit_count"] == 2
        assert len(data["entities_edited"]) == 2
        # Most recently edited first
        assert data["entities_edited"][0]["entity_name"] == "Attack from Mars"
        assert data["entities_edited"][1]["entity_name"] == "Medieval Madness"

        # Recent edits also newest first
        assert len(data["recent_edits"]) == 2
        assert data["recent_edits"][0]["entity_name"] == "Attack from Mars"
        assert data["recent_edits"][1]["entity_name"] == "Medieval Madness"

    def test_multiple_edits_same_entity(self, client, user, model_a):
        """Multiple edits to one entity count correctly."""
        client.force_login(user)
        client.patch(
            f"/api/models/{model_a.slug}/claims/",
            data='{"fields": {"year": 1998}}',
            content_type="application/json",
        )
        client.patch(
            f"/api/models/{model_a.slug}/claims/",
            data='{"fields": {"year": 1999}}',
            content_type="application/json",
        )

        resp = client.get(f"/api/users/{user.username}/")
        data = resp.json()

        assert data["edit_count"] == 2
        assert len(data["entities_edited"]) == 1
        assert data["entities_edited"][0]["edit_count"] == 2
        assert len(data["recent_edits"]) == 2

    def test_cross_entity_type_edits(self, client, user, model_a, manufacturer):
        """Edits to different entity types are all included."""
        client.force_login(user)
        client.patch(
            f"/api/models/{model_a.slug}/claims/",
            data='{"fields": {"year": 1998}}',
            content_type="application/json",
        )
        client.patch(
            f"/api/manufacturers/{manufacturer.slug}/claims/",
            data='{"fields": {"description": "A pinball manufacturer."}}',
            content_type="application/json",
        )

        resp = client.get(f"/api/users/{user.username}/")
        data = resp.json()

        assert data["edit_count"] == 2
        assert len(data["entities_edited"]) == 2
        entity_types = {e["entity_type_label"] for e in data["entities_edited"]}
        assert "Model" in entity_types
        assert "Manufacturer" in entity_types

    def test_other_users_edits_not_included(self, client, user, model_a, db):
        """Only the requested user's edits appear."""
        other = User.objects.create_user(username="other")
        client.force_login(other)
        client.patch(
            f"/api/models/{model_a.slug}/claims/",
            data='{"fields": {"year": 1998}}',
            content_type="application/json",
        )

        resp = client.get(f"/api/users/{user.username}/")
        data = resp.json()
        assert data["edit_count"] == 0
        assert data["entities_edited"] == []
        assert data["recent_edits"] == []


@pytest.mark.django_db
class TestEditHistoryUserDisplayNull:
    """Verify that build_edit_history returns null for non-user changesets."""

    def test_ingest_changeset_has_null_user_display(self, client, db):
        from apps.provenance.models import ChangeSet, IngestRun

        source = Source.objects.create(
            name="IPDB", slug="ipdb", source_type="database", priority=10
        )
        pm = MachineModel.objects.create(name="Gorgar", slug="gorgar", year=1979)

        # Create an ingest changeset with a claim — this is the non-user path
        ingest_run = IngestRun.objects.create(source=source, input_fingerprint="abc123")
        ingest_cs = ChangeSet.objects.create(ingest_run=ingest_run)
        Claim.objects.assert_claim(pm, "year", 1979, source=source, changeset=ingest_cs)

        # Create a user changeset with a claim — this is the user path
        user = User.objects.create_user(username="tester")
        user_cs = ChangeSet.objects.create(user=user)
        Claim.objects.assert_claim(
            pm,
            "description",
            "First talking pinball machine",
            user=user,
            changeset=user_cs,
        )

        resp = client.get(f"/api/edit-history/machinemodel/{pm.slug}/")
        data = resp.json()
        # Find entries by user_display to avoid ordering assumptions
        user_entries = [e for e in data if e["user_display"] == "tester"]
        ingest_entries = [e for e in data if e["user_display"] is None]
        assert len(user_entries) == 1
        assert len(ingest_entries) == 1
