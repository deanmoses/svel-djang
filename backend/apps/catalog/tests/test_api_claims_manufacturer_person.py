"""Tests for PATCH /api/manufacturers/{slug}/claims/ and /api/people/{slug}/claims/."""

import pytest
from django.contrib.auth import get_user_model

from apps.catalog.models import Manufacturer, Person
from apps.provenance.models import Claim, Source

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="editor", password="testpass")  # pragma: allowlist secret  # fmt: skip


@pytest.fixture
def mfr(db):
    return Manufacturer.objects.create(name="Williams")


@pytest.fixture
def person(db):
    return Person.objects.create(name="Pat Lawlor")


# ---------------------------------------------------------------------------
# Manufacturer claims
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPatchManufacturerClaimsAuth:
    def test_anonymous_gets_401(self, client, mfr):
        resp = client.patch(
            f"/api/manufacturers/{mfr.slug}/claims/",
            data='{"fields": {"trade_name": "WMS"}}',
            content_type="application/json",
        )
        assert resp.status_code in (401, 403)

    def test_authenticated_user_can_patch(self, client, user, mfr):
        client.force_login(user)
        resp = client.patch(
            f"/api/manufacturers/{mfr.slug}/claims/",
            data='{"fields": {"trade_name": "WMS"}}',
            content_type="application/json",
        )
        assert resp.status_code == 200


@pytest.mark.django_db
class TestPatchManufacturerClaimsValidation:
    def test_unknown_field_returns_422(self, client, user, mfr):
        client.force_login(user)
        resp = client.patch(
            f"/api/manufacturers/{mfr.slug}/claims/",
            data='{"fields": {"slug": "bad"}}',
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_nonexistent_slug_returns_404(self, client, user):
        client.force_login(user)
        resp = client.patch(
            "/api/manufacturers/does-not-exist/claims/",
            data='{"fields": {"name": "X"}}',
            content_type="application/json",
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestPatchManufacturerClaimsPersistence:
    def test_claim_created_for_user(self, client, user, mfr):
        client.force_login(user)
        client.patch(
            f"/api/manufacturers/{mfr.slug}/claims/",
            data='{"fields": {"trade_name": "WMS"}}',
            content_type="application/json",
        )
        claim = mfr.claims.get(user=user, field_name="trade_name", is_active=True)
        assert claim.value == "WMS"

    def test_model_resolved_and_returned(self, client, user, mfr):
        client.force_login(user)
        resp = client.patch(
            f"/api/manufacturers/{mfr.slug}/claims/",
            data='{"fields": {"trade_name": "WMS"}}',
            content_type="application/json",
        )
        data = resp.json()
        assert data["trade_name"] == "WMS"
        mfr.refresh_from_db()
        assert mfr.trade_name == "WMS"

    def test_repeated_edit_supersedes_previous(self, client, user, mfr):
        client.force_login(user)
        client.patch(
            f"/api/manufacturers/{mfr.slug}/claims/",
            data='{"fields": {"trade_name": "First"}}',
            content_type="application/json",
        )
        client.patch(
            f"/api/manufacturers/{mfr.slug}/claims/",
            data='{"fields": {"trade_name": "Second"}}',
            content_type="application/json",
        )
        active = mfr.claims.filter(user=user, field_name="trade_name", is_active=True)
        inactive = mfr.claims.filter(
            user=user, field_name="trade_name", is_active=False
        )
        assert active.count() == 1
        assert inactive.count() == 1
        assert active.first().value == "Second"

    def test_user_claim_beats_lower_priority_source(self, client, user, mfr):
        source = Source.objects.create(
            name="LowPri", source_type="database", priority=10
        )
        Claim.objects.assert_claim(mfr, "trade_name", "Source Name", source=source)
        from apps.catalog.resolve import resolve_manufacturer

        resolve_manufacturer(mfr)
        mfr.refresh_from_db()
        assert mfr.trade_name == "Source Name"

        client.force_login(user)
        resp = client.patch(
            f"/api/manufacturers/{mfr.slug}/claims/",
            data='{"fields": {"trade_name": "User Name"}}',
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.json()["trade_name"] == "User Name"

    def test_response_includes_activity(self, client, user, mfr):
        client.force_login(user)
        resp = client.patch(
            f"/api/manufacturers/{mfr.slug}/claims/",
            data='{"fields": {"trade_name": "WMS"}}',
            content_type="application/json",
        )
        data = resp.json()
        assert "activity" in data
        assert any(
            c["field_name"] == "trade_name" and c["is_winner"] for c in data["activity"]
        )


# ---------------------------------------------------------------------------
# Person claims
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPatchPersonClaimsAuth:
    def test_anonymous_gets_401(self, client, person):
        resp = client.patch(
            f"/api/people/{person.slug}/claims/",
            data='{"fields": {"bio": "A great designer."}}',
            content_type="application/json",
        )
        assert resp.status_code in (401, 403)

    def test_authenticated_user_can_patch(self, client, user, person):
        client.force_login(user)
        resp = client.patch(
            f"/api/people/{person.slug}/claims/",
            data='{"fields": {"bio": "A great designer."}}',
            content_type="application/json",
        )
        assert resp.status_code == 200


@pytest.mark.django_db
class TestPatchPersonClaimsValidation:
    def test_unknown_field_returns_422(self, client, user, person):
        client.force_login(user)
        resp = client.patch(
            f"/api/people/{person.slug}/claims/",
            data='{"fields": {"credits": []}}',
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_nonexistent_slug_returns_404(self, client, user):
        client.force_login(user)
        resp = client.patch(
            "/api/people/does-not-exist/claims/",
            data='{"fields": {"bio": "x"}}',
            content_type="application/json",
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestPatchPersonClaimsPersistence:
    def test_claim_created_for_user(self, client, user, person):
        client.force_login(user)
        client.patch(
            f"/api/people/{person.slug}/claims/",
            data='{"fields": {"bio": "A great designer."}}',
            content_type="application/json",
        )
        claim = person.claims.get(user=user, field_name="bio", is_active=True)
        assert claim.value == "A great designer."

    def test_model_resolved_and_returned(self, client, user, person):
        client.force_login(user)
        resp = client.patch(
            f"/api/people/{person.slug}/claims/",
            data='{"fields": {"bio": "A great designer.", "name": "Pat Lawlor"}}',
            content_type="application/json",
        )
        data = resp.json()
        assert data["bio"] == "A great designer."
        assert data["name"] == "Pat Lawlor"
        person.refresh_from_db()
        assert person.bio == "A great designer."

    def test_response_includes_activity(self, client, user, person):
        client.force_login(user)
        resp = client.patch(
            f"/api/people/{person.slug}/claims/",
            data='{"fields": {"bio": "Short bio."}}',
            content_type="application/json",
        )
        data = resp.json()
        assert "activity" in data
        assert any(
            c["field_name"] == "bio" and c["is_winner"] for c in data["activity"]
        )
