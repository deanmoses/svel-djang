"""Tests for media helpers: all_media() and primary_media()."""

from __future__ import annotations

import pytest

from apps.catalog.tests.conftest import make_machine_model
from apps.media.helpers import all_media, primary_media

pytestmark = pytest.mark.django_db


class TestAllMedia:
    def test_returns_list_when_prefetched(self):
        pm = make_machine_model(name="X", slug="x")
        # simulate media_prefetch() attaching the attr — it lives on
        # prefetched querysets, not on bare model instances, so we don't
        # type it at the class level. setattr (vs direct attribute
        # assignment) silences mypy's attr-defined error.
        setattr(pm, "all_media", [])  # noqa: B010 — mypy attr-defined workaround

        assert all_media(pm) == []

    def test_raises_when_not_prefetched(self):
        pm = make_machine_model(name="X", slug="x")

        with pytest.raises(AssertionError, match="media_prefetch"):
            all_media(pm)


class TestPrimaryMedia:
    def test_returns_list_when_prefetched(self):
        pm = make_machine_model(name="X", slug="x")
        setattr(pm, "primary_media", [])  # noqa: B010 — mypy attr-defined workaround

        assert primary_media(pm) == []

    def test_raises_when_not_prefetched(self):
        pm = make_machine_model(name="X", slug="x")

        with pytest.raises(AssertionError, match="primary_media"):
            primary_media(pm)
