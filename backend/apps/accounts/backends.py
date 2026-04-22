"""Authentication backend for users authenticated via WorkOS AuthKit.

This backend does not implement authenticate() because the actual
authentication happens via the WorkOS SDK in the callback view.
It only implements get_user() so Django's session framework can
reload the user from the session.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model

User = get_user_model()


class WorkOSBackend:
    def authenticate(self, request, **kwargs):
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
