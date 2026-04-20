"""Per-user rolling-window rate limiting.

Used to enforce caps on record creates, edits, and deletes. Backed by the
Django cache (any cache backend works; a persistent backend is preferable in
production so limits survive process restarts).

Semantics:

* Rolling window — not calendar-aligned. Sliding timestamps are pruned on
  each check.
* Per user. Anonymous users never hit this code path (endpoints are auth-gated
  upstream).
* Staff (``user.is_staff``) bypass all limits.
* Both successful and validation-rejected attempts consume a slot. The
  consuming call is :func:`check_and_record` and endpoints invoke it once at
  the top of the request.
* 429 refusals do NOT consume a slot. If a rejection bumped the horizon
  forward on every retry, the window would never drain.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

from django.core.cache import cache

from .constants import (
    CREATE_RATE_LIMIT,
    CREATE_WINDOW_SECONDS,
    DELETE_RATE_LIMIT,
    DELETE_WINDOW_SECONDS,
)

_CACHE_TTL_FUDGE_SECONDS = 60


class RateLimitExceeded(Exception):
    """Raised when a user has exceeded a rate-limit bucket."""

    def __init__(self, *, bucket: str, retry_after: int) -> None:
        self.bucket = bucket
        self.retry_after = max(1, retry_after)
        super().__init__(f"Rate limit exceeded for bucket {bucket!r}")


@dataclass(frozen=True)
class RateLimitSpec:
    bucket: str
    limit: int
    window_seconds: int


# Shared bucket for user-driven record creation (Title, Model, …). All record
# types share one bucket so that a burst of creates is capped in aggregate,
# not per-record-type. Restore uses this same bucket (it is semantically a
# create — a fresh ``status=active`` claim that brings a record back).
CREATE_RATE_LIMIT_SPEC = RateLimitSpec(
    bucket="create",
    limit=CREATE_RATE_LIMIT,
    window_seconds=CREATE_WINDOW_SECONDS,
)

# Shared bucket for user-driven record deletion. A cascading delete counts as
# one ChangeSet and consumes one slot here — not one per hidden child.
# Inverting one's own ChangeSet (Undo) is exempt and does not consume a slot.
DELETE_RATE_LIMIT_SPEC = RateLimitSpec(
    bucket="delete",
    limit=DELETE_RATE_LIMIT,
    window_seconds=DELETE_WINDOW_SECONDS,
)


def _cache_key(user_id: int, bucket: str) -> str:
    return f"ratelimit:{bucket}:user:{user_id}"


def check_and_record(user, spec: RateLimitSpec) -> None:
    """Consume one slot in the user's bucket, or raise if the bucket is full.

    Staff users bypass the check entirely and nothing is recorded for them.
    """
    if user is None or not user.is_authenticated:
        raise RateLimitExceeded(bucket=spec.bucket, retry_after=1)
    if user.is_staff:
        return

    now = time.time()
    cutoff = now - spec.window_seconds
    key = _cache_key(user.pk, spec.bucket)

    timestamps = cache.get(key, []) or []
    pruned = [ts for ts in timestamps if ts > cutoff]

    if len(pruned) >= spec.limit:
        oldest = min(pruned)
        retry_after = math.ceil(oldest + spec.window_seconds - now)
        cache.set(key, pruned, timeout=spec.window_seconds + _CACHE_TTL_FUDGE_SECONDS)
        raise RateLimitExceeded(bucket=spec.bucket, retry_after=retry_after)

    pruned.append(now)
    cache.set(key, pruned, timeout=spec.window_seconds + _CACHE_TTL_FUDGE_SECONDS)


def reset_for_user(user, bucket: str) -> None:
    """Test helper: clear a user's bucket."""
    cache.delete(_cache_key(user.pk, bucket))
