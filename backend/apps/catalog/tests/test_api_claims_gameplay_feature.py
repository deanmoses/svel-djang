"""Tests for PATCH /api/gameplay-features/{slug}/claims/."""

import json

import pytest
from django.contrib.auth import get_user_model

from apps.catalog.models import GameplayFeature
from apps.provenance.models import ChangeSet

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create(username="editor")


@pytest.fixture
def feature(db):
    return GameplayFeature.objects.create(name="Multiball", slug="multiball")


def _patch(client, slug, body):
    return client.patch(
        f"/api/gameplay-features/{slug}/claims/",
        data=json.dumps(body),
        content_type="application/json",
    )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPatchGameplayFeatureAuth:
    def test_anonymous_gets_401(self, client, feature):
        resp = _patch(client, feature.slug, {"fields": {"description": "Updated"}})
        assert resp.status_code in (401, 403)

    def test_authenticated_user_can_patch(self, client, user, feature):
        client.force_login(user)
        resp = _patch(client, feature.slug, {"fields": {"description": "Updated"}})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPatchGameplayFeatureValidation:
    def test_empty_fields_returns_422(self, client, user, feature):
        client.force_login(user)
        resp = _patch(client, feature.slug, {"fields": {}})
        assert resp.status_code == 422

    def test_no_fields_key_returns_422(self, client, user, feature):
        client.force_login(user)
        resp = _patch(client, feature.slug, {})
        assert resp.status_code == 422

    def test_unknown_field_returns_422(self, client, user, feature):
        client.force_login(user)
        resp = _patch(client, feature.slug, {"fields": {"slug": "bad"}})
        assert resp.status_code == 422

    def test_nonexistent_slug_returns_404(self, client, user):
        client.force_login(user)
        resp = _patch(client, "does-not-exist", {"fields": {"name": "X"}})
        assert resp.status_code == 404

    def test_duplicate_name_returns_422(self, client, user, feature):
        GameplayFeature.objects.create(name="Drop Targets", slug="drop-targets")
        client.force_login(user)
        resp = _patch(client, feature.slug, {"fields": {"name": "Drop Targets"}})
        assert resp.status_code == 422
        assert "unique" in resp.json()["detail"].lower()

    def test_invalid_markdown_link_returns_422(self, client, user, feature):
        client.force_login(user)
        resp = _patch(
            client,
            feature.slug,
            {"fields": {"description": "Links to [[system:nope]]."}},
        )
        assert resp.status_code == 422
        assert "nope" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPatchGameplayFeaturePersistence:
    def test_claim_created_for_user(self, client, user, feature):
        client.force_login(user)
        _patch(client, feature.slug, {"fields": {"description": "Updated"}})
        claim = feature.claims.get(user=user, field_name="description", is_active=True)
        assert claim.value == "Updated"

    def test_model_resolved_and_returned(self, client, user, feature):
        client.force_login(user)
        resp = _patch(client, feature.slug, {"fields": {"description": "Updated"}})
        data = resp.json()
        assert data["description"]["text"] == "Updated"
        feature.refresh_from_db()
        assert feature.description == "Updated"

    def test_repeated_edit_supersedes_previous(self, client, user, feature):
        client.force_login(user)
        _patch(client, feature.slug, {"fields": {"description": "First"}})
        _patch(client, feature.slug, {"fields": {"description": "Second"}})
        active = feature.claims.filter(
            user=user, field_name="description", is_active=True
        )
        inactive = feature.claims.filter(
            user=user, field_name="description", is_active=False
        )
        assert active.count() == 1
        assert inactive.count() == 1
        assert active.first().value == "Second"

    def test_response_includes_activity(self, client, user, feature):
        client.force_login(user)
        resp = _patch(client, feature.slug, {"fields": {"description": "Updated"}})
        data = resp.json()
        assert "activity" in data
        assert any(
            c["field_name"] == "description" and c["is_winner"]
            for c in data["activity"]
        )


# ---------------------------------------------------------------------------
# ChangeSet
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPatchGameplayFeatureChangeSet:
    def test_changeset_created_with_claims(self, client, user, feature):
        client.force_login(user)
        _patch(
            client,
            feature.slug,
            {"fields": {"name": "Multiball Mania", "description": "Updated"}},
        )
        assert ChangeSet.objects.count() == 1
        cs = ChangeSet.objects.first()
        assert cs.user == user
        assert cs.claims.count() == 2
        assert set(cs.claims.values_list("field_name", flat=True)) == {
            "name",
            "description",
        }

    def test_changeset_stores_note(self, client, user, feature):
        client.force_login(user)
        _patch(
            client,
            feature.slug,
            {
                "fields": {"description": "Updated"},
                "note": "Corrected from IPDB listing",
            },
        )
        cs = ChangeSet.objects.first()
        assert cs.note == "Corrected from IPDB listing"

    def test_changeset_note_in_activity_response(self, client, user, feature):
        client.force_login(user)
        resp = _patch(
            client,
            feature.slug,
            {
                "fields": {"description": "Updated"},
                "note": "My edit note",
            },
        )
        data = resp.json()
        desc_claim = next(
            c for c in data["activity"] if c["field_name"] == "description"
        )
        assert desc_claim["changeset_note"] == "My edit note"

    def test_changeset_note_defaults_to_empty(self, client, user, feature):
        client.force_login(user)
        _patch(client, feature.slug, {"fields": {"description": "Updated"}})
        cs = ChangeSet.objects.first()
        assert cs.note == ""
