"""Tests for model-level validation (clean()) on media models."""

import pytest
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from apps.media.models import EntityMedia, MediaAsset

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _asset_kwargs(user, **overrides):
    """Return valid MediaAsset kwargs."""
    defaults = {
        "kind": "image",
        "original_filename": "photo.jpg",
        "mime_type": "image/jpeg",
        "byte_size": 5000,
        "width": 800,
        "height": 600,
        "status": "ready",
        "uploaded_by": user,
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user(db):
    return User.objects.create_user("mediatest")


@pytest.fixture
def asset(user):
    return MediaAsset.objects.create(**_asset_kwargs(user))


# ---------------------------------------------------------------------------
# EntityMedia.clean() — content type validation
# ---------------------------------------------------------------------------


class TestEntityMediaContentTypeValidation:
    def test_supported_content_type_accepted(self, asset):
        """MachineModel is MediaSupportedModel, so EntityMedia.clean() passes."""
        from apps.catalog.models import MachineModel

        ct = ContentType.objects.get_for_model(MachineModel)
        em = EntityMedia(asset=asset, content_type=ct, object_id=1)
        em.clean()  # should not raise

    def test_unsupported_content_type_rejected(self, asset):
        """User is not MediaSupportedModel, so EntityMedia.clean() raises."""
        ct = ContentType.objects.get_for_model(User)
        em = EntityMedia(asset=asset, content_type=ct, object_id=1)
        with pytest.raises(ValidationError) as exc_info:
            em.clean()
        assert "content_type" in exc_info.value.message_dict
