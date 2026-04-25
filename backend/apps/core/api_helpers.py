"""Cross-app helpers for Django Ninja API endpoints."""

from __future__ import annotations

from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpRequest


def authed_user(request: HttpRequest) -> User:
    """Narrow ``request.user`` to ``User``.

    The ``assert`` is type-narrowing only — stripped under ``python -O``. The
    runtime guarantee comes from ``@django_auth`` (or equivalent) on every
    consumer endpoint, not from this assert. The narrow goes away when
    ``docs/plans/UserModel.md`` lands and ``request.user`` types as ``User``
    directly.
    """
    assert not isinstance(request.user, AnonymousUser)
    return request.user
