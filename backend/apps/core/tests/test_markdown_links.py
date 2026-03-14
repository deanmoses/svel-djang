"""Tests for the markdown link registry, conversion, and reference syncing."""

import pytest

from apps.core.markdown_links import (
    convert_authoring_to_storage,
    convert_storage_to_authoring,
    get_enabled_link_types,
    get_link_type,
    render_all_links,
    sync_references,
)
from apps.core.models import RecordReference


@pytest.fixture(autouse=True)
def _ensure_link_types_registered():
    """Link types are registered on app startup; just verify they exist."""
    assert get_link_type("manufacturer") is not None
    assert get_link_type("system") is not None


@pytest.fixture
def manufacturer(db):
    from apps.catalog.models import Manufacturer

    return Manufacturer.objects.create(name="Williams", slug="williams")


@pytest.fixture
def system(db):
    from apps.catalog.models import System

    return System.objects.create(name="WPC-95", slug="wpc-95")


class TestLinkRegistry:
    def test_manufacturer_registered(self):
        lt = get_link_type("manufacturer")
        assert lt is not None
        assert lt.slug_field == "slug"
        assert lt.url_pattern == "/manufacturers/{slug}"

    def test_system_registered(self):
        lt = get_link_type("system")
        assert lt is not None
        assert lt.url_pattern == "/systems/{slug}"

    def test_enabled_link_types_non_empty(self):
        types = get_enabled_link_types()
        names = [lt.name for lt in types]
        assert "manufacturer" in names
        assert "system" in names


class TestRenderAllLinks:
    def test_render_storage_format(self, manufacturer):
        text = f"Made by [[manufacturer:id:{manufacturer.pk}]]"
        result = render_all_links(text)
        assert "[Williams](/manufacturers/williams)" in result

    def test_render_authoring_format(self, manufacturer):
        text = "Made by [[manufacturer:williams]]"
        result = render_all_links(text)
        assert "[Williams](/manufacturers/williams)" in result

    def test_render_broken_link(self, db):
        text = "See [[manufacturer:id:99999]]"
        result = render_all_links(text)
        assert "*[broken link]*" in result

    def test_render_broken_link_plain_text(self, db):
        text = "See [[manufacturer:id:99999]]"
        result = render_all_links(text, plain_text=True)
        assert "[broken link]" in result
        assert "*" not in result

    def test_render_with_base_url(self, manufacturer):
        text = f"See [[manufacturer:id:{manufacturer.pk}]]"
        result = render_all_links(text, base_url="https://pinbase.app")
        assert "https://pinbase.app/manufacturers/williams" in result

    def test_render_multiple_links(self, manufacturer, system):
        text = (
            f"Made by [[manufacturer:id:{manufacturer.pk}]] "
            f"on [[system:id:{system.pk}]]"
        )
        result = render_all_links(text)
        assert "[Williams](/manufacturers/williams)" in result
        assert "[WPC-95](/systems/wpc-95)" in result


class TestAuthoringToStorage:
    def test_converts_slug_to_id(self, manufacturer):
        result = convert_authoring_to_storage("See [[manufacturer:williams]]")
        assert f"[[manufacturer:id:{manufacturer.pk}]]" in result

    def test_invalid_slug_raises_validation_error(self, db):
        with pytest.raises(Exception, match="not found"):
            convert_authoring_to_storage("See [[manufacturer:nonexistent]]")

    def test_empty_string(self):
        assert convert_authoring_to_storage("") == ""

    def test_no_links_unchanged(self):
        text = "Just plain text"
        assert convert_authoring_to_storage(text) == text


class TestStorageToAuthoring:
    def test_converts_id_to_slug(self, manufacturer):
        text = f"See [[manufacturer:id:{manufacturer.pk}]]"
        result = convert_storage_to_authoring(text)
        assert "[[manufacturer:williams]]" in result

    def test_broken_link_kept_as_storage(self, db):
        text = "See [[manufacturer:id:99999]]"
        result = convert_storage_to_authoring(text)
        assert "[[manufacturer:id:99999]]" in result

    def test_empty_string(self):
        assert convert_storage_to_authoring("") == ""


class TestSyncReferences:
    def test_creates_references(self, manufacturer, system):
        text = (
            f"Links to [[manufacturer:id:{manufacturer.pk}]] "
            f"and [[system:id:{system.pk}]]"
        )
        # Use system as the source (it has a MarkdownField)
        sync_references(system, text)
        refs = RecordReference.objects.all()
        assert refs.count() == 2

    def test_removes_stale_references(self, manufacturer, system):
        # First sync with a link
        text = f"Links to [[manufacturer:id:{manufacturer.pk}]]"
        sync_references(system, text)
        assert RecordReference.objects.count() == 1

        # Second sync without the link
        sync_references(system, "No links here")
        assert RecordReference.objects.count() == 0

    def test_idempotent(self, manufacturer, system):
        text = f"Links to [[manufacturer:id:{manufacturer.pk}]]"
        sync_references(system, text)
        sync_references(system, text)
        assert RecordReference.objects.count() == 1
