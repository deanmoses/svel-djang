import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.accounts.models import UserProfile

User = get_user_model()


def _profile(user) -> UserProfile:
    return UserProfile.objects.get(user=user)


@pytest.mark.django_db
class TestUserProfileAutoCreate:
    def test_profile_created_on_user_save(self):
        user = User.objects.create_user(username="testuser")
        assert UserProfile.objects.filter(user=user).exists()

    def test_profile_default_priority(self):
        user = User.objects.create_user(username="testuser2")
        assert _profile(user).priority == 10000

    def test_profile_deleted_with_user(self):
        user = User.objects.create_user(username="testuser3")
        user_id = user.pk
        user.delete()
        assert not UserProfile.objects.filter(user_id=user_id).exists()

    def test_priority_is_configurable(self):
        user = User.objects.create_user(username="editor")
        profile = _profile(user)
        profile.priority = 200
        profile.save()
        profile.refresh_from_db()
        assert profile.priority == 200


@pytest.mark.django_db
class TestWorkOSFields:
    def test_workos_user_id_default_null(self):
        user = User.objects.create_user(username="testuser")
        assert _profile(user).workos_user_id is None

    def test_workos_user_id_uniqueness(self, db):
        u1 = User.objects.create_user(username="user1")
        u1_profile = _profile(u1)
        u1_profile.workos_user_id = "user_01ABC"
        u1_profile.save()

        u2 = User.objects.create_user(username="user2")
        u2_profile = _profile(u2)
        u2_profile.workos_user_id = "user_01ABC"
        with pytest.raises(IntegrityError):
            u2_profile.save()

    def test_multiple_null_workos_user_id_allowed(self):
        """Legacy users can all have null workos_user_id."""
        User.objects.create_user(username="legacy1")
        User.objects.create_user(username="legacy2")
        # Both profiles have workos_user_id=None — no uniqueness violation
        assert UserProfile.objects.filter(workos_user_id=None).count() >= 2
