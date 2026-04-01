"""Tests for media detach (removal) endpoint."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import Client

from apps.catalog.claims import build_media_attachment_claim
from apps.catalog.models import MachineModel
from apps.catalog.resolve import resolve_media_attachments
from apps.media.models import EntityMedia, MediaAsset
from apps.provenance.models import Claim

User = get_user_model()

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user(db):
    return User.objects.create_user("editor")


@pytest.fixture
def machine_model(db):
    return MachineModel.objects.create(name="Test Machine", slug="test-machine")


@pytest.fixture
def asset(db, user):
    return MediaAsset.objects.create(
        kind=MediaAsset.Kind.IMAGE,
        status=MediaAsset.Status.READY,
        original_filename="backglass.jpg",
        mime_type="image/jpeg",
        byte_size=1024,
        width=800,
        height=600,
        uploaded_by=user,
    )


def _attach_via_claims(entity, asset, user, category="backglass", is_primary=True):
    """Create a media attachment through the claims system."""
    claim_key, claim_value = build_media_attachment_claim(
        entity, asset.pk, category=category, is_primary=is_primary
    )
    Claim.objects.assert_claim(
        entity,
        "media_attachment",
        claim_value,
        user=user,
        claim_key=claim_key,
    )
    ct = ContentType.objects.get_for_model(type(entity))
    resolve_media_attachments(content_type_id=ct.id, entity_ids={entity.pk})


@pytest.fixture
def attached(machine_model, asset, user):
    """Attach asset to machine_model via claims and resolve."""
    _attach_via_claims(machine_model, asset, user)


@pytest.fixture
def auth_client(user):
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def anon_client():
    return Client()


# ---------------------------------------------------------------------------
# Detach endpoint
# ---------------------------------------------------------------------------


class TestDetachEndpoint:
    def test_successful_detach(self, auth_client, machine_model, asset, attached):
        """Detaching removes the EntityMedia row."""
        assert EntityMedia.objects.filter(asset=asset).exists()

        resp = auth_client.post(
            "/api/media/detach/",
            data={
                "entity_type": "machine-model",
                "slug": machine_model.slug,
                "asset_uuid": str(asset.uuid),
            },
            content_type="application/json",
        )

        assert resp.status_code == 200
        assert not EntityMedia.objects.filter(asset=asset).exists()

    def test_detach_idempotent(self, auth_client, machine_model, asset, attached):
        """Second detach of same asset returns 404 (already detached)."""
        auth_client.post(
            "/api/media/detach/",
            data={
                "entity_type": "machine-model",
                "slug": machine_model.slug,
                "asset_uuid": str(asset.uuid),
            },
            content_type="application/json",
        )

        resp = auth_client.post(
            "/api/media/detach/",
            data={
                "entity_type": "machine-model",
                "slug": machine_model.slug,
                "asset_uuid": str(asset.uuid),
            },
            content_type="application/json",
        )

        assert resp.status_code == 404

    def test_asset_not_attached_to_entity(self, auth_client, machine_model, asset):
        """Detaching an asset that exists but isn't attached to this entity fails."""
        resp = auth_client.post(
            "/api/media/detach/",
            data={
                "entity_type": "machine-model",
                "slug": machine_model.slug,
                "asset_uuid": str(asset.uuid),
            },
            content_type="application/json",
        )

        assert resp.status_code == 404

    def test_auth_required(self, anon_client, machine_model, asset, attached):
        """Anonymous users cannot detach."""
        resp = anon_client.post(
            "/api/media/detach/",
            data={
                "entity_type": "machine-model",
                "slug": machine_model.slug,
                "asset_uuid": str(asset.uuid),
            },
            content_type="application/json",
        )

        assert resp.status_code in (401, 403)
        assert EntityMedia.objects.filter(asset=asset).exists()

    def test_unknown_entity_type(self, auth_client, asset):
        resp = auth_client.post(
            "/api/media/detach/",
            data={
                "entity_type": "nonexistent-type",
                "slug": "whatever",
                "asset_uuid": str(asset.uuid),
            },
            content_type="application/json",
        )

        assert resp.status_code == 400

    def test_unknown_slug(self, auth_client, asset):
        resp = auth_client.post(
            "/api/media/detach/",
            data={
                "entity_type": "machine-model",
                "slug": "no-such-machine",
                "asset_uuid": str(asset.uuid),
            },
            content_type="application/json",
        )

        assert resp.status_code == 400

    def test_unknown_asset_uuid(self, auth_client, machine_model):
        resp = auth_client.post(
            "/api/media/detach/",
            data={
                "entity_type": "machine-model",
                "slug": machine_model.slug,
                "asset_uuid": "00000000-0000-0000-0000-000000000000",
            },
            content_type="application/json",
        )

        assert resp.status_code == 404

    def test_malformed_asset_uuid(self, auth_client, machine_model):
        resp = auth_client.post(
            "/api/media/detach/",
            data={
                "entity_type": "machine-model",
                "slug": machine_model.slug,
                "asset_uuid": "not-a-uuid",
            },
            content_type="application/json",
        )

        assert resp.status_code == 404
