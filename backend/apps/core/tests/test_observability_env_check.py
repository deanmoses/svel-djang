"""Tests for ``apps.core.checks.check_observability_env``.

Guards the deploy-time contract that all Sentry env vars required for
production observability are set on the Railway service. The check ids
(``core.E201``–``E207``) are the operator-facing contract — pinned here
so a rename in the message string doesn't silently break log greps.
"""

from __future__ import annotations

import pytest
from pytest_django.fixtures import Settings

from apps.core.checks import check_observability_env

MonkeyPatch = pytest.MonkeyPatch

_SENTRY_ENV: dict[str, str] = {
    "SENTRY_DSN": "https://abc@o1.ingest.sentry.io/2",
    "PUBLIC_SENTRY_DSN": "https://def@o1.ingest.sentry.io/3",
    "SENTRY_AUTH_TOKEN": "tok",
    "SENTRY_ORG": "the-flip",
    "SENTRY_PROJECT": "flipcommons-frontend",
    "RAILWAY_GIT_COMMIT_SHA": "deadbeef",
}


@pytest.fixture
def sentry_env(monkeypatch: MonkeyPatch) -> None:
    """Set every observability env var to a well-formed value."""
    for key, value in _SENTRY_ENV.items():
        monkeypatch.setenv(key, value)


class TestObservabilityEnvCheck:
    def test_passes_when_debug_is_true(
        self, settings: Settings, monkeypatch: MonkeyPatch
    ) -> None:
        # DEBUG short-circuits the check before any env reads.
        settings.DEBUG = True
        for key in _SENTRY_ENV:
            monkeypatch.delenv(key, raising=False)
        assert check_observability_env(app_configs=None) == []

    def test_passes_when_all_env_set(
        self, settings: Settings, sentry_env: None
    ) -> None:
        _ = sentry_env
        settings.DEBUG = False
        assert check_observability_env(app_configs=None) == []

    @pytest.mark.parametrize(
        ("missing_var", "expected_id"),
        [
            ("SENTRY_DSN", "core.E201"),
            ("PUBLIC_SENTRY_DSN", "core.E202"),
            ("SENTRY_AUTH_TOKEN", "core.E203"),
            ("SENTRY_ORG", "core.E204"),
            ("SENTRY_PROJECT", "core.E205"),
        ],
    )
    def test_errors_per_missing_required_var(
        self,
        settings: Settings,
        sentry_env: None,
        monkeypatch: MonkeyPatch,
        missing_var: str,
        expected_id: str,
    ) -> None:
        _ = sentry_env
        settings.DEBUG = False
        monkeypatch.delenv(missing_var)
        messages = check_observability_env(app_configs=None)
        ids = {m.id for m in messages}
        assert expected_id in ids
        assert all(m.id != "core.E207" for m in messages)  # SHA still set

    def test_whitespace_only_counts_as_empty(
        self,
        settings: Settings,
        sentry_env: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        # Mirrors settings.py's .strip()-then-truthy idiom.
        _ = sentry_env
        settings.DEBUG = False
        monkeypatch.setenv("SENTRY_DSN", "   ")
        ids = {m.id for m in check_observability_env(app_configs=None)}
        assert "core.E201" in ids

    @pytest.mark.parametrize(
        ("var", "expected_id"),
        [
            ("SENTRY_DSN", "core.E201"),
            ("PUBLIC_SENTRY_DSN", "core.E202"),
        ],
    )
    def test_dsn_must_have_https_scheme(
        self,
        settings: Settings,
        sentry_env: None,
        monkeypatch: MonkeyPatch,
        var: str,
        expected_id: str,
    ) -> None:
        # An http:// DSN is a misconfiguration we want to catch before
        # the deploy goes live, not silently accept.
        _ = sentry_env
        settings.DEBUG = False
        monkeypatch.setenv(var, "http://abc@o1.ingest.sentry.io/2")
        ids = {m.id for m in check_observability_env(app_configs=None)}
        assert expected_id in ids

    @pytest.mark.parametrize(
        ("var", "expected_id"),
        [
            ("SENTRY_DSN", "core.E201"),
            ("PUBLIC_SENTRY_DSN", "core.E202"),
        ],
    )
    @pytest.mark.parametrize(
        "bad_value",
        [
            "https://",  # scheme only — no host or project
            "https://abc@o1.ingest.sentry.io",  # no project path
            "https://abc@o1.ingest.sentry.io/",  # empty project path
            "not-a-url",
        ],
    )
    def test_dsn_must_have_host_and_project(
        self,
        settings: Settings,
        sentry_env: None,
        monkeypatch: MonkeyPatch,
        var: str,
        expected_id: str,
        bad_value: str,
    ) -> None:
        # `startswith("https://")` alone accepts these malformed values.
        # urlparse-based shape check catches them before the deploy goes live.
        _ = sentry_env
        settings.DEBUG = False
        monkeypatch.setenv(var, bad_value)
        ids = {m.id for m in check_observability_env(app_configs=None)}
        assert expected_id in ids

    def test_errors_when_dsns_are_equal(
        self,
        settings: Settings,
        sentry_env: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        # The two DSNs must point at different Sentry projects.
        # Equal values route one half's errors into the wrong project.
        _ = sentry_env
        settings.DEBUG = False
        dupe = "https://abc@o1.ingest.sentry.io/2"
        monkeypatch.setenv("SENTRY_DSN", dupe)
        monkeypatch.setenv("PUBLIC_SENTRY_DSN", dupe)
        ids = {m.id for m in check_observability_env(app_configs=None)}
        assert "core.E206" in ids

    def test_errors_when_commit_sha_missing(
        self,
        settings: Settings,
        sentry_env: None,
        monkeypatch: MonkeyPatch,
    ) -> None:
        # Missing SHA → uploaded sourcemaps don't resolve at runtime
        # (release tags don't match), so browser stack traces show as
        # minified. Same failure mode as missing SENTRY_AUTH_TOKEN,
        # treated as Error per docs/DeployChecks.md.
        _ = sentry_env
        settings.DEBUG = False
        monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA")
        messages = check_observability_env(app_configs=None)
        assert len(messages) == 1
        assert messages[0].id == "core.E207"

    def test_accepts_django_kwargs_forward_compat(
        self,
        settings: Settings,
        sentry_env: None,
    ) -> None:
        _ = sentry_env
        settings.DEBUG = False
        assert check_observability_env(app_configs=None, databases=["default"]) == []
