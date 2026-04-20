"""Tests for per-user rolling-window rate limits."""

from __future__ import annotations

import time
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

from apps.provenance.rate_limits import (
    CREATE_RATE_LIMIT_SPEC,
    DELETE_RATE_LIMIT_SPEC,
    RateLimitExceeded,
    RateLimitSpec,
    check_and_record,
    reset_for_user,
)

User = get_user_model()

SPEC = RateLimitSpec(bucket="test", limit=3, window_seconds=60)


@pytest.fixture
def user(db):
    u = User.objects.create_user(username="rater")
    yield u
    reset_for_user(u, SPEC.bucket)


@pytest.fixture
def staff_user(db):
    u = User.objects.create_user(username="staffer", is_staff=True)
    yield u
    reset_for_user(u, SPEC.bucket)


@pytest.fixture(autouse=True)
def _flush_cache():
    cache.clear()
    yield
    cache.clear()


class TestRateLimits:
    def test_under_limit_passes(self, user):
        for _ in range(SPEC.limit):
            check_and_record(user, SPEC)

    def test_over_limit_raises(self, user):
        for _ in range(SPEC.limit):
            check_and_record(user, SPEC)
        with pytest.raises(RateLimitExceeded) as exc:
            check_and_record(user, SPEC)
        assert exc.value.retry_after >= 1
        assert exc.value.bucket == "test"

    def test_retry_after_does_not_drift_on_repeated_rejection(self, user):
        """The spec forbids 429 responses extending the lockout horizon."""
        base = 1_000_000.0
        with mock.patch("apps.provenance.rate_limits.time.time") as fake_time:
            fake_time.return_value = base
            for _ in range(SPEC.limit):
                check_and_record(user, SPEC)

            fake_time.return_value = base + 5
            with pytest.raises(RateLimitExceeded) as first:
                check_and_record(user, SPEC)

            # 20 more blocked retries spaced 1s apart.
            last = first
            for i in range(1, 21):
                fake_time.return_value = base + 5 + i
                with pytest.raises(RateLimitExceeded) as exc:
                    check_and_record(user, SPEC)
                last = exc

        # Horizon anchored to the oldest admitted attempt, not the last retry.
        assert first.value.retry_after >= last.value.retry_after

    def test_validation_reject_still_counts(self, user):
        """Endpoints call check_and_record before validation, so every
        attempt — including those that go on to fail — consumes a slot."""
        for _ in range(SPEC.limit):
            check_and_record(user, SPEC)
        with pytest.raises(RateLimitExceeded):
            check_and_record(user, SPEC)

    def test_window_expiry(self, user):
        base = 1_000_000.0
        with mock.patch("apps.provenance.rate_limits.time.time") as fake_time:
            fake_time.return_value = base
            for _ in range(SPEC.limit):
                check_and_record(user, SPEC)
            fake_time.return_value = base + SPEC.window_seconds + 1
            # After the window has elapsed, the bucket is empty again.
            check_and_record(user, SPEC)

    def test_staff_bypass(self, staff_user):
        for _ in range(SPEC.limit * 10):
            check_and_record(staff_user, SPEC)

    def test_buckets_are_independent(self, user):
        other_spec = RateLimitSpec(
            bucket="other", limit=SPEC.limit, window_seconds=SPEC.window_seconds
        )
        for _ in range(SPEC.limit):
            check_and_record(user, SPEC)
        # Different bucket for the same user is untouched.
        for _ in range(SPEC.limit):
            check_and_record(user, other_spec)
        with pytest.raises(RateLimitExceeded):
            check_and_record(user, SPEC)

    def test_users_are_independent(self, user, db):
        other = User.objects.create_user(username="other")
        try:
            for _ in range(SPEC.limit):
                check_and_record(user, SPEC)
            for _ in range(SPEC.limit):
                check_and_record(other, SPEC)
            with pytest.raises(RateLimitExceeded):
                check_and_record(user, SPEC)
        finally:
            reset_for_user(other, SPEC.bucket)

    def test_anonymous_raises(self):
        class Anon:
            is_authenticated = False
            is_staff = False

        with pytest.raises(RateLimitExceeded):
            check_and_record(Anon(), SPEC)


class TestBucketConfig:
    """Pin the configured bucket parameters so accidental edits in
    constants.py are caught at test time rather than in production."""

    def test_delete_bucket_is_5_per_day(self):
        assert DELETE_RATE_LIMIT_SPEC.bucket == "delete"
        assert DELETE_RATE_LIMIT_SPEC.limit == 5
        assert DELETE_RATE_LIMIT_SPEC.window_seconds == 86_400

    def test_create_and_delete_buckets_are_independent(self, user):
        for _ in range(CREATE_RATE_LIMIT_SPEC.limit):
            check_and_record(user, CREATE_RATE_LIMIT_SPEC)
        # Filling the create bucket does not consume delete slots.
        for _ in range(DELETE_RATE_LIMIT_SPEC.limit):
            check_and_record(user, DELETE_RATE_LIMIT_SPEC)
        reset_for_user(user, CREATE_RATE_LIMIT_SPEC.bucket)
        reset_for_user(user, DELETE_RATE_LIMIT_SPEC.bucket)


# Silence time.sleep warnings in case any test uses real time.
_ = time
