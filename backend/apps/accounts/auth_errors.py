"""Structured exceptions for the signup (onboarding) flow.

Each subclass declares `kind` and `status` as class-level constants
(required by `StructuredApiError.__init_subclass__`). The global handler
in `config/api.py` wraps them uniformly as:

    {"detail": {"kind": <kind>, "message": <message>, **to_body()}}

Three classes rather than two so the `kind` axis fully discriminates on
the wire: `UsernameRejectedError` carries a `reason` body field for the
format/reserved sub-cases (400), while `UsernameTakenError` is its own
kind (409) — splitting them lets each subclass keep its `status` as an
immutable class constant.
"""

from __future__ import annotations

from typing import override

from apps.core.exceptions import StructuredApiError
from apps.core.types import JsonBody

from .usernames import UsernameFormatRejectReason


class PendingInvalidError(StructuredApiError):
    """Pending-session payload is missing or expired."""

    kind = "pending_invalid"
    status = 401

    def __init__(self) -> None:
        super().__init__("Sign-in session has expired. Please start over.")


class UsernameRejectedError(StructuredApiError):
    """Candidate username failed format validation or hit the reserved list."""

    kind = "username_rejected"
    status = 400

    def __init__(self, *, reason: UsernameFormatRejectReason) -> None:
        # Keyword-only: raise sites read `UsernameRejectedError(reason="reserved")`,
        # which is louder at a glance than the positional form and resists
        # accidental positional confusion if a second field is ever added.
        super().__init__("Username rejected.")
        self.reason = reason

    @override
    def to_body(self) -> JsonBody:
        return {"reason": self.reason}


class UsernameTakenError(StructuredApiError):
    """Username collided with an existing row on submit."""

    kind = "username_taken"
    status = 409

    def __init__(self) -> None:
        super().__init__("Username is taken.")
