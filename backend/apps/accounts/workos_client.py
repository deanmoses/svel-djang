"""WorkOS client factory — centralised so tests can mock one import."""

from __future__ import annotations

from django.conf import settings
from workos import (
    AuthenticationError,
    AuthorizationError,
    BadRequestError,
    ConflictError,
    NotFoundError,
    RateLimitExceededError,
    ServerError,
    UnprocessableEntityError,
    WorkOSClient,
)

WORKOS_HTTP_ERRORS = (
    AuthenticationError,
    AuthorizationError,
    BadRequestError,
    ConflictError,
    NotFoundError,
    RateLimitExceededError,
    ServerError,
    UnprocessableEntityError,
)
"""The WorkOS errors that carry HTTP response diagnostics.

Every member descends from the SDK's `APIError`, so a handler catching this
tuple can read `status_code` and `request_id` off the exception. `APIError`
itself has no public import path, and its other descendants (`ConfigurationError`
and friends) are raised before a request goes out and carry neither field —
enumerating the HTTP set keeps those diagnostics type-checked instead of
`getattr`-ed off the `WorkOSError` base, which declares only `message`.
"""

REQUEST_TIMEOUT_SECONDS = 10
"""Per-request HTTP timeout. The SDK default is 60s.

The only WorkOS call that touches the network is the code exchange in the
auth callback, and the visitor is watching a browser redirect while it runs.
A minute of spinner is worse than an early trip to the styled error page.
"""

MAX_RETRIES = 0
"""Retry budget for retryable failures (429, 5xx). The SDK default is 3.

Off rather than merely reduced, because a retry budget does not bound the
wall clock. When a response carries `Retry-After` the SDK sleeps for exactly
that long — the header bypasses the 30s cap that applies to its exponential
backoff, and nothing imposes an overall deadline. `request_timeout` is per
HTTP request, so it does not cover the sleep either. A 429 answering the auth
callback would therefore park a gunicorn worker for as long as WorkOS asks,
while the visitor waits mid-redirect.

Giving up the one transient-failure retry costs little here: the only network
call we make is the code exchange, and a visitor who lands on the error page
retries by signing in again.
"""


def get_workos_client() -> WorkOSClient:
    return WorkOSClient(
        api_key=settings.WORKOS_API_KEY,
        client_id=settings.WORKOS_CLIENT_ID,
        request_timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=MAX_RETRIES,
    )
