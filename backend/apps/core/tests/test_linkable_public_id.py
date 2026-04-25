"""Tests for LinkableModel.public_id / get_absolute_url and the system check."""

from __future__ import annotations

import pytest
from django.core import checks


@pytest.mark.django_db
def test_public_id_returns_slug_for_default_subclass() -> None:
    from apps.catalog.models import Theme

    theme = Theme.objects.create(name="Sci-Fi", slug="sci-fi")

    assert theme.public_id_field == "slug"
    assert theme.public_id == "sci-fi"
    assert theme.public_id == theme.slug


@pytest.mark.django_db
def test_get_absolute_url_uses_plural_and_public_id() -> None:
    from apps.catalog.models import Theme

    theme = Theme.objects.create(name="Sci-Fi", slug="sci-fi")

    assert theme.get_absolute_url() == "/themes/sci-fi"


def test_linkable_public_id_check_passes_for_real_models() -> None:
    """The registered system check should be clean against the real models."""
    errors = checks.run_checks(tags=[checks.Tags.models])
    relevant = [
        e
        for e in errors
        if isinstance(e, checks.Error)
        and e.id is not None
        and e.id.startswith("core.E00")
    ]
    assert relevant == []


def test_linkable_public_id_check_flags_non_unique_field() -> None:
    """A LinkableModel whose public_id_field points at a non-unique field is flagged."""
    from unittest.mock import patch

    from apps.catalog.models import Theme
    from apps.core import checks as core_checks

    # ``status`` is not unique on Theme; pointing public_id_field there should fail.
    with patch.object(Theme, "public_id_field", "status"):
        errors = core_checks.check_linkable_public_id_field_unique()

    assert any(
        e.id == "core.E002" and "Theme" in e.msg and "status" in e.msg for e in errors
    ), errors


def test_linkable_public_id_check_flags_unknown_field() -> None:
    from unittest.mock import patch

    from apps.catalog.models import Theme
    from apps.core import checks as core_checks

    with patch.object(Theme, "public_id_field", "does_not_exist"):
        errors = core_checks.check_linkable_public_id_field_unique()

    assert any(e.id == "core.E001" and "Theme" in e.msg for e in errors), errors
