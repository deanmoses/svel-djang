"""Session-keyed and IP-keyed rolling-window rate limiting.

Sibling of :mod:`apps.provenance.rate_limits`, which is per-user. This
module is for pre-auth flows (signup availability checks, submit, cancel)
where there's no User yet — so the bucket key is the session id or the
client IP. Same cache-backed rolling-window mechanics, same wire shape
(`RateLimitExceededError` → 429 with `Retry-After`), so frontend handling
is identical across both modules.

For the proxy-chain trust model and the deployment contract behind
``RATE_LIMIT_TRUST_PROXY_HEADERS``, see ``docs/Hosting.md`` § "Client IP
trust". :func:`_client_ip` is the single sanctioned reader of the
forwarded-IP header; do not add a second reader elsewhere.

If the two limiters (per-user vs. session/IP) diverge painfully later,
dedupe is a small follow-up refactor — not worth the upfront
genericization today.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import override

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest

from apps.core.exceptions import StructuredApiError
from apps.core.types import JsonBody

_CACHE_TTL_FUDGE_SECONDS = 60


class RateLimitExceededError(StructuredApiError):
    """Raised when a pre-auth bucket is full.

    Distinct class from `apps.provenance.rate_limits.RateLimitExceededError`
    so each module owns its own handler taxonomy, but the wire shape is
    identical: kind="rate_limit", `Retry-After` header, `{bucket, retry_after}`
    body fields.
    """

    kind = "rate_limit"
    status = 429

    def __init__(self, *, bucket: str, retry_after: int) -> None:
        super().__init__("Rate limit exceeded.")
        self.bucket = bucket
        self.retry_after = max(1, retry_after)

    @override
    def __str__(self) -> str:
        return f"Rate limit exceeded for bucket {self.bucket!r}"

    @override
    def to_body(self) -> JsonBody:
        return {"bucket": self.bucket, "retry_after": self.retry_after}

    @override
    def extra_headers(self) -> dict[str, str]:
        return {"Retry-After": str(self.retry_after)}


@dataclass(frozen=True)
class RateLimitSpec:
    bucket: str
    limit: int
    window_seconds: int


def _client_ip(request: HttpRequest) -> str:
    """Return the client IP used as a rate-limit bucket key.

    Reads ``X-Real-IP`` and never ``X-Forwarded-For`` — XFF parsing has
    no failure mode that's safe under upstream drift. Gated by
    ``RATE_LIMIT_TRUST_PROXY_HEADERS`` (default False); when off, keys
    off ``REMOTE_ADDR``. Both fail closed on drift: degrade to one
    shared bucket, never trust attacker-supplied input.

    Full trust model and deployment contract: ``docs/Hosting.md`` §
    "Client IP trust". Don't add a second forwarded-header reader
    elsewhere; this function is the single sanctioned reader.
    """
    meta = request.META
    if settings.RATE_LIMIT_TRUST_PROXY_HEADERS:
        real_ip = str(meta.get("HTTP_X_REAL_IP") or "").strip()
        if real_ip:
            return real_ip
    return str(meta.get("REMOTE_ADDR") or "unknown")


def _consume(cache_key: str, spec: RateLimitSpec) -> None:
    now = time.time()
    cutoff = now - spec.window_seconds
    timestamps = cache.get(cache_key, []) or []
    pruned = [ts for ts in timestamps if ts > cutoff]
    if len(pruned) >= spec.limit:
        oldest = min(pruned)
        retry_after = math.ceil(oldest + spec.window_seconds - now)
        # Persist the pruned list so the window can drain even if no
        # successful request arrives between rejections.
        cache.set(
            cache_key, pruned, timeout=spec.window_seconds + _CACHE_TTL_FUDGE_SECONDS
        )
        raise RateLimitExceededError(bucket=spec.bucket, retry_after=retry_after)
    pruned.append(now)
    cache.set(cache_key, pruned, timeout=spec.window_seconds + _CACHE_TTL_FUDGE_SECONDS)


def check_and_record_session(request: HttpRequest, spec: RateLimitSpec) -> None:
    """Consume a slot keyed by `request.session.session_key`.

    Caller must ensure a session key exists (anonymous requests don't
    persist one until something is written or `request.session.save()`
    is called explicitly — see `apps.accounts.pending.ensure_session_key`).
    """
    session_key = request.session.session_key
    assert session_key is not None, (
        "session_key is None — call ensure_session_key() before rate-limiting "
        "by session"
    )
    _consume(f"ratelimit:{spec.bucket}:session:{session_key}", spec)


def check_and_record_ip(request: HttpRequest, spec: RateLimitSpec) -> None:
    """Consume a slot keyed by the client IP."""
    _consume(f"ratelimit:{spec.bucket}:ip:{_client_ip(request)}", spec)


def reset_session(session_key: str, bucket: str) -> None:
    """Test helper: clear a session's bucket."""
    cache.delete(f"ratelimit:{bucket}:session:{session_key}")


def reset_ip(ip: str, bucket: str) -> None:
    """Test helper: clear an IP's bucket."""
    cache.delete(f"ratelimit:{bucket}:ip:{ip}")
