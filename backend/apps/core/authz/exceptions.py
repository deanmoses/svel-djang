"""Structured 403 raised when the policy denies an action.

``PolicyDeniedError`` subclasses :class:`StructuredApiError`, so it routes
through the single handler in ``config/api.py`` and serializes as
``{"detail": {"kind": "policy_denied", "message", "code", "context"}}``
without a per-class handler registration.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar, override

from apps.core.exceptions import StructuredApiError
from apps.core.types import JsonBody

from .types import DenialCode, Deny

# Closed-enum mapper: DenialCode → English message builder. One place.
# The completeness test pins the invariant. Each entry is a builder so
# static codes (lambda returning a constant) and context-aware codes
# (reading from ``decision.context``) compose through one lookup — no
# static-vs-dynamic fallback dance. Adding a new code is always "drop
# a builder into this dict." These strings are what the SPA renders
# today (``parseApiError`` falls through ``policy_denied`` to ``message``);
# the structured ``code`` + ``context`` are on the wire for a future
# per-code mapper but are unused by the current frontend.
_DENIAL_MESSAGE: dict[DenialCode, Callable[[Deny], str]] = {
    DenialCode.AUTH_REQUIRED: lambda _: "Sign in to continue.",
    DenialCode.ACCOUNT_DEACTIVATED: lambda _: "Your account is deactivated.",
    DenialCode.ROLE_REQUIRED: lambda _: "You don't have permission to do that.",
    DenialCode.OWNER_REQUIRED: lambda _: "Only the original author can do that.",
    DenialCode.VERIFICATION_REQUIRED: lambda _: (
        "Verify your email address to continue."
    ),
    DenialCode.EXPERIENCE_REQUIRED: lambda d: (
        f"You need {d.context['required']} edits before you can revert "
        f"others' changes — you have {d.context['current']}."
    ),
    DenialCode.RATE_LIMITED: lambda _: (
        "You're doing that too often. Try again shortly."
    ),
}


def _resolve_message(decision: Deny) -> str:
    return _DENIAL_MESSAGE[decision.code](decision)


class PolicyDeniedError(StructuredApiError):
    """Raised by ``enforce()`` (and inline ``check()`` callers) on Deny."""

    kind: ClassVar[str] = "policy_denied"
    status: ClassVar[int] = 403

    def __init__(self, decision: Deny) -> None:
        super().__init__(_resolve_message(decision))
        self.decision = decision

    @override
    def to_body(self) -> JsonBody:
        return {
            "code": self.decision.code.value,
            "context": dict(self.decision.context),
        }
