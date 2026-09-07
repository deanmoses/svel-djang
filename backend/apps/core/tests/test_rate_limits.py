"""Tests for the pre-auth (session/IP-keyed) rolling-window rate limiter.

Sibling of `apps.provenance.tests.test_rate_limits`, which covers the
per-user limiter. The two modules deliberately share no code (see the
module docstring of `apps.core.rate_limits` for rationale), so test
coverage is parallel rather than shared.

The critical regression test is the trust-disabled-default case
(:class:`TestTrustDisabled`): if a deploy ever rolls
``RATE_LIMIT_TRUST_PROXY_HEADERS`` back to its default, proxy headers
must be ignored so attacker-supplied values can't bypass IP-keyed
limiters by spraying distinct bucket keys.
"""

from __future__ import annotations

from unittest import mock

import pytest
from django.core.cache import cache
from django.http import HttpRequest
from django.test import RequestFactory
from pytest_django.fixtures import Settings

from apps.core.exceptions import StructuredApiError
from apps.core.rate_limits import (
    RateLimitExceededError,
    RateLimitSpec,
    _client_ip,
    check_and_record_ip,
    check_and_record_session,
    reset_ip,
    reset_session,
)

SPEC = RateLimitSpec(bucket="test", limit=3, window_seconds=60)


@pytest.fixture(autouse=True)
def _flush_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def request_with_session(db, rf: RequestFactory):
    """An HttpRequest with a real persisted session row (session_key set)."""
    from django.contrib.sessions.backends.db import SessionStore

    req = rf.get("/")
    req.session = SessionStore()
    req.session.save()  # force-allocate a session_key
    return req


@pytest.fixture
def request_without_session_key(rf: RequestFactory):
    """An HttpRequest whose session has not been persisted yet."""
    from django.contrib.sessions.backends.db import SessionStore

    req = rf.get("/")
    req.session = SessionStore()
    assert req.session.session_key is None
    return req


def _request(rf: RequestFactory, **meta: str) -> HttpRequest:
    """Build an HttpRequest with specific META values for IP-resolution tests."""
    req = rf.get("/")
    req.META.update(meta)
    return req


# ── _client_ip — proxy-header trust model ────────────────────────────


class TestTrustDisabled:
    """Default posture: proxy headers are noise; bucket keys off REMOTE_ADDR.

    This is the regression-test class. If a deploy accidentally rolls
    ``RATE_LIMIT_TRUST_PROXY_HEADERS`` back to its default False, an
    attacker spraying X-Real-IP / X-Forwarded-For values must NOT be
    able to influence the bucket key.
    """

    @pytest.fixture(autouse=True)
    def _disable_trust(self, settings: Settings) -> None:
        settings.RATE_LIMIT_TRUST_PROXY_HEADERS = False

    def test_real_ip_header_is_ignored(self, rf: RequestFactory) -> None:
        req = _request(rf, HTTP_X_REAL_IP="9.9.9.9", REMOTE_ADDR="127.0.0.1")
        assert _client_ip(req) == "127.0.0.1"

    def test_forwarded_for_header_is_ignored(self, rf: RequestFactory) -> None:
        req = _request(
            rf,
            HTTP_X_FORWARDED_FOR="9.9.9.9, 8.8.8.8",
            REMOTE_ADDR="127.0.0.1",
        )
        assert _client_ip(req) == "127.0.0.1"

    def test_both_headers_ignored_in_favor_of_remote_addr(
        self, rf: RequestFactory
    ) -> None:
        req = _request(
            rf,
            HTTP_X_REAL_IP="9.9.9.9",
            HTTP_X_FORWARDED_FOR="1.2.3.4",
            REMOTE_ADDR="127.0.0.1",
        )
        assert _client_ip(req) == "127.0.0.1"

    def test_remote_addr_missing_falls_back_to_unknown(
        self, rf: RequestFactory
    ) -> None:
        req = rf.get("/")
        req.META.pop("REMOTE_ADDR", None)
        assert _client_ip(req) == "unknown"


class TestTrustEnabled:
    """Production posture: X-Real-IP is trusted; XFF is still ignored."""

    @pytest.fixture(autouse=True)
    def _enable_trust(self, settings: Settings) -> None:
        settings.RATE_LIMIT_TRUST_PROXY_HEADERS = True

    def test_real_ip_is_used(self, rf: RequestFactory) -> None:
        req = _request(rf, HTTP_X_REAL_IP="203.0.113.7", REMOTE_ADDR="127.0.0.1")
        assert _client_ip(req) == "203.0.113.7"

    def test_forwarded_for_is_still_ignored(self, rf: RequestFactory) -> None:
        # Asserts the parsing-bug class is gone: even with trust enabled,
        # XFF is never read, so attacker-supplied left-most entries can't
        # influence the bucket key.
        req = _request(
            rf,
            HTTP_X_FORWARDED_FOR="9.9.9.9, 8.8.8.8",
            REMOTE_ADDR="127.0.0.1",
        )
        assert _client_ip(req) == "127.0.0.1"

    def test_real_ip_preferred_over_forwarded_for(self, rf: RequestFactory) -> None:
        req = _request(
            rf,
            HTTP_X_REAL_IP="203.0.113.7",
            HTTP_X_FORWARDED_FOR="9.9.9.9",
            REMOTE_ADDR="127.0.0.1",
        )
        assert _client_ip(req) == "203.0.113.7"

    def test_empty_real_ip_falls_back_to_remote_addr(self, rf: RequestFactory) -> None:
        req = _request(rf, HTTP_X_REAL_IP="   ", REMOTE_ADDR="127.0.0.1")
        assert _client_ip(req) == "127.0.0.1"

    def test_missing_real_ip_falls_back_to_remote_addr(
        self, rf: RequestFactory
    ) -> None:
        req = _request(rf, REMOTE_ADDR="127.0.0.1")
        assert _client_ip(req) == "127.0.0.1"


# ── Session-keyed limiter ────────────────────────────────────────────


class TestSessionRateLimit:
    def test_under_limit_passes(self, request_with_session):
        for _ in range(SPEC.limit):
            check_and_record_session(request_with_session, SPEC)

    def test_over_limit_raises(self, request_with_session):
        for _ in range(SPEC.limit):
            check_and_record_session(request_with_session, SPEC)
        with pytest.raises(RateLimitExceededError) as exc:
            check_and_record_session(request_with_session, SPEC)
        assert exc.value.bucket == "test"
        assert exc.value.retry_after >= 1

    def test_distinct_sessions_have_independent_buckets(self, db, rf):
        from django.contrib.sessions.backends.db import SessionStore

        req_a = rf.get("/")
        req_a.session = SessionStore()
        req_a.session.save()

        req_b = rf.get("/")
        req_b.session = SessionStore()
        req_b.session.save()

        assert req_a.session.session_key != req_b.session.session_key

        for _ in range(SPEC.limit):
            check_and_record_session(req_a, SPEC)
        # Session B is untouched.
        for _ in range(SPEC.limit):
            check_and_record_session(req_b, SPEC)
        with pytest.raises(RateLimitExceededError):
            check_and_record_session(req_a, SPEC)

    def test_window_expiry_drains_bucket(self, request_with_session):
        base = 1_000_000.0
        with mock.patch("apps.core.rate_limits.time.time") as fake_time:
            fake_time.return_value = base
            for _ in range(SPEC.limit):
                check_and_record_session(request_with_session, SPEC)
            fake_time.return_value = base + SPEC.window_seconds + 1
            # After the window elapses, the bucket is empty again.
            check_and_record_session(request_with_session, SPEC)

    def test_retry_after_does_not_drift_on_repeated_rejection(
        self, request_with_session
    ):
        """A flood of rejected retries must not extend the lockout horizon.

        The horizon is anchored to the oldest admitted attempt, so the
        retry_after value reported on later (rejected) calls should not
        exceed the one reported on the first rejection.
        """
        base = 1_000_000.0
        with mock.patch("apps.core.rate_limits.time.time") as fake_time:
            fake_time.return_value = base
            for _ in range(SPEC.limit):
                check_and_record_session(request_with_session, SPEC)

            fake_time.return_value = base + 5
            with pytest.raises(RateLimitExceededError) as first:
                check_and_record_session(request_with_session, SPEC)

            last = first
            for i in range(1, 20):
                fake_time.return_value = base + 5 + i
                with pytest.raises(RateLimitExceededError) as exc:
                    check_and_record_session(request_with_session, SPEC)
                last = exc

        assert first.value.retry_after >= last.value.retry_after

    def test_missing_session_key_asserts(self, request_without_session_key):
        """The session limiter is a contract: callers must seed session_key first."""
        with pytest.raises(AssertionError, match="session_key is None"):
            check_and_record_session(request_without_session_key, SPEC)

    def test_reset_session_clears_bucket(self, request_with_session):
        for _ in range(SPEC.limit):
            check_and_record_session(request_with_session, SPEC)
        with pytest.raises(RateLimitExceededError):
            check_and_record_session(request_with_session, SPEC)

        session_key = request_with_session.session.session_key
        assert session_key is not None
        reset_session(session_key, SPEC.bucket)
        # After reset, the bucket is empty.
        check_and_record_session(request_with_session, SPEC)


# ── IP-keyed limiter — bucket mechanics ──────────────────────────────


class TestIpRateLimit:
    """Bucket mechanics of the IP-keyed limiter.

    IP *resolution* semantics (which header is trusted) live in
    :class:`TestTrustDisabled` / :class:`TestTrustEnabled` above. These
    tests cover the rolling-window + bucket-key behavior using
    REMOTE_ADDR (which is what `_client_ip` returns under the default
    trust-disabled setting).
    """

    def _req(self, rf: RequestFactory, *, remote_addr: str = "203.0.113.10"):
        return _request(rf, REMOTE_ADDR=remote_addr)

    def test_under_limit_passes(self, rf: RequestFactory):
        req = self._req(rf)
        for _ in range(SPEC.limit):
            check_and_record_ip(req, SPEC)

    def test_over_limit_raises(self, rf: RequestFactory):
        req = self._req(rf)
        for _ in range(SPEC.limit):
            check_and_record_ip(req, SPEC)
        with pytest.raises(RateLimitExceededError) as exc:
            check_and_record_ip(req, SPEC)
        assert exc.value.bucket == "test"

    def test_distinct_ips_have_independent_buckets(self, rf: RequestFactory):
        req_a = self._req(rf, remote_addr="203.0.113.10")
        req_b = self._req(rf, remote_addr="203.0.113.20")
        for _ in range(SPEC.limit):
            check_and_record_ip(req_a, SPEC)
        # B from a different IP is untouched.
        for _ in range(SPEC.limit):
            check_and_record_ip(req_b, SPEC)
        with pytest.raises(RateLimitExceededError):
            check_and_record_ip(req_a, SPEC)

    def test_window_expiry_drains_bucket(self, rf: RequestFactory):
        req = self._req(rf)
        base = 1_000_000.0
        with mock.patch("apps.core.rate_limits.time.time") as fake_time:
            fake_time.return_value = base
            for _ in range(SPEC.limit):
                check_and_record_ip(req, SPEC)
            fake_time.return_value = base + SPEC.window_seconds + 1
            check_and_record_ip(req, SPEC)

    def test_reset_ip_clears_bucket(self, rf: RequestFactory):
        ip = "203.0.113.42"
        req = self._req(rf, remote_addr=ip)
        for _ in range(SPEC.limit):
            check_and_record_ip(req, SPEC)
        with pytest.raises(RateLimitExceededError):
            check_and_record_ip(req, SPEC)

        reset_ip(ip, SPEC.bucket)
        # After reset, the bucket is empty.
        check_and_record_ip(req, SPEC)


# ── Wire shape — what frontend / generated TS sees ───────────────────


class TestWireShape:
    """`RateLimitExceededError` must produce the exact envelope and
    headers the global handler in `config/api.py` emits. These tests pin
    the contract so a refactor of the base class can't quietly change
    what the frontend receives."""

    def test_is_structured_api_error_subclass(self):
        assert issubclass(RateLimitExceededError, StructuredApiError)

    def test_kind_and_status_constants(self):
        assert RateLimitExceededError.kind == "rate_limit"
        assert RateLimitExceededError.status == 429

    def test_to_body_carries_bucket_and_retry_after(self):
        exc = RateLimitExceededError(bucket="signup_check_session", retry_after=42)
        assert exc.to_body() == {
            "bucket": "signup_check_session",
            "retry_after": 42,
        }

    def test_retry_after_is_clamped_to_minimum_1(self):
        """Retry-After:0 is meaningless — the rolling-window math can
        produce 0 when the oldest admitted timestamp is exactly window
        seconds old. Clamp to 1 so the header always tells the caller to
        wait at least a second."""
        exc = RateLimitExceededError(bucket="b", retry_after=0)
        assert exc.retry_after == 1

    def test_extra_headers_emits_retry_after(self):
        exc = RateLimitExceededError(bucket="b", retry_after=17)
        assert exc.extra_headers() == {"Retry-After": "17"}

    def test_message_is_human_readable(self):
        exc = RateLimitExceededError(bucket="b", retry_after=1)
        assert exc.message == "Rate limit exceeded."
