"""Tests for ``apps.core.checks.check_rate_limit_proxy_trust``.

The check guards a deployment contract: in any non-DEBUG environment,
``RATE_LIMIT_TRUST_PROXY_HEADERS`` must be True or IP-keyed rate limits
silently degrade to one shared bucket.
"""

from __future__ import annotations

import pytest
from pytest_django.fixtures import Settings

from apps.core.checks import check_rate_limit_proxy_trust


class TestRateLimitProxyTrustCheck:
    def test_passes_when_debug_is_true(self, settings: Settings) -> None:
        settings.DEBUG = True
        settings.RATE_LIMIT_TRUST_PROXY_HEADERS = False
        assert check_rate_limit_proxy_trust(app_configs=None) == []

    def test_passes_when_trust_is_enabled(self, settings: Settings) -> None:
        settings.DEBUG = False
        settings.RATE_LIMIT_TRUST_PROXY_HEADERS = True
        assert check_rate_limit_proxy_trust(app_configs=None) == []

    def test_warns_when_prod_but_trust_disabled(self, settings: Settings) -> None:
        """The regression case: prod env without the trust env var."""
        settings.DEBUG = False
        settings.RATE_LIMIT_TRUST_PROXY_HEADERS = False
        messages = check_rate_limit_proxy_trust(app_configs=None)
        assert len(messages) == 1
        assert messages[0].id == "core.W001"
        assert "RATE_LIMIT_TRUST_PROXY_HEADERS" in messages[0].msg
        assert messages[0].hint is not None
        assert "RATE_LIMIT_TRUST_PROXY_HEADERS=true" in messages[0].hint

    @pytest.mark.parametrize(
        "kwargs",
        [
            {},
            {"databases": ["default"]},
            {"some_future_kwarg": "x"},
        ],
    )
    def test_accepts_django_kwargs_forward_compat(
        self, settings: Settings, kwargs: dict[str, object]
    ) -> None:
        """Django's check framework may pass extra kwargs; we must accept them."""
        settings.DEBUG = False
        settings.RATE_LIMIT_TRUST_PROXY_HEADERS = True
        assert check_rate_limit_proxy_trust(app_configs=None, **kwargs) == []
