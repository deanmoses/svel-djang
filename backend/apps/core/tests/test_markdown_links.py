"""Tests for the markdown link registry, conversion, and reference syncing."""

from typing import Any

import pytest

from apps.core.markdown_links import (
    convert_authoring_to_storage,
    convert_storage_to_authoring,
    get_autocomplete_types,
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
    assert get_link_type("cite") is not None


@pytest.fixture
def manufacturer(db):
    from apps.catalog.models import Manufacturer

    return Manufacturer.objects.create(name="Williams", slug="williams")


@pytest.fixture
def system(db, manufacturer):
    from apps.catalog.models import System

    return System.objects.create(
        name="WPC-95", slug="wpc-95", manufacturer=manufacturer
    )


@pytest.fixture
def citation_source(db):
    from apps.citation.models import CitationSource

    return CitationSource.objects.create(
        name="The Encyclopedia of Pinball",
        source_type="book",
        author="Jeff Lawton",
        year=2001,
    )


@pytest.fixture
def citation_source_with_links(citation_source):
    from apps.citation.models import CitationSourceLink

    CitationSourceLink.objects.create(
        citation_source=citation_source,
        url="https://example.com/archive",
        label="Archive scan",
        link_type="archive",
    )
    return citation_source


@pytest.fixture
def citation_instance(citation_source):
    from apps.provenance.models import CitationInstance

    return CitationInstance.objects.create(
        citation_source=citation_source, locator="p. 30"
    )


class TestLinkRegistry:
    def test_manufacturer_registered(self):
        lt = get_link_type("manufacturer")
        assert lt is not None
        assert lt.public_id_field == "slug"
        assert lt.url_pattern == "/manufacturers/{public_id}"

    def test_system_registered(self):
        lt = get_link_type("system")
        assert lt is not None
        assert lt.url_pattern == "/systems/{public_id}"

    def test_enabled_link_types_non_empty(self):
        types = get_enabled_link_types()
        names = [lt.name for lt in types]
        assert "manufacturer" in names
        assert "system" in names

    def test_autocomplete_types_include_custom_flow(self):
        """get_autocomplete_types() includes types with autocomplete_flow='custom'
        even if they have no autocomplete_serialize."""
        types = get_autocomplete_types()
        types_by_name = {t["name"]: t for t in types}
        assert "cite" in types_by_name
        assert types_by_name["cite"]["flow"] == "custom"

    def test_autocomplete_types_have_flow_field(self):
        """Every type returned by get_autocomplete_types() has a 'flow' field."""
        for t in get_autocomplete_types():
            assert "flow" in t, f"Missing 'flow' field on {t['name']}"

    def test_standard_types_have_standard_flow(self):
        types = get_autocomplete_types()
        types_by_name = {t["name"]: t for t in types}
        assert types_by_name["manufacturer"]["flow"] == "standard"


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


class TestCitationLinkType:
    def test_cite_registered(self):
        lt = get_link_type("cite")
        assert lt is not None
        assert lt.public_id_field is None
        assert lt.format_link is not None
        assert lt.sort_order == 1

    def test_render_single_citation(self, citation_instance):
        text = f"Production was 4,000 units.[[cite:{citation_instance.pk}]]"
        result = render_all_links(text)
        pk = citation_instance.pk
        assert (
            f'<sup data-cite-id="{pk}" data-cite-index="1"'
            f' tabindex="0" role="button">[1]</sup>' in result
        )
        assert "[[cite:" not in result

    def test_render_multiple_citations(self, citation_source):
        from apps.provenance.models import CitationInstance

        ci1 = CitationInstance.objects.create(
            citation_source=citation_source, locator="p. 30"
        )
        ci2 = CitationInstance.objects.create(
            citation_source=citation_source, locator="p. 83"
        )
        text = f"First fact.[[cite:{ci1.pk}]] Second fact.[[cite:{ci2.pk}]]"
        result = render_all_links(text)
        assert (
            f'<sup data-cite-id="{ci1.pk}" data-cite-index="1"'
            f' tabindex="0" role="button">[1]</sup>' in result
        )
        assert (
            f'<sup data-cite-id="{ci2.pk}" data-cite-index="2"'
            f' tabindex="0" role="button">[2]</sup>' in result
        )

    def test_duplicate_citation_same_number(self, citation_instance):
        pk = citation_instance.pk
        text = f"First mention.[[cite:{pk}]] Second mention.[[cite:{pk}]]"
        result = render_all_links(text)
        # Both should be [1], not [1] and [2]
        assert result.count("[1]") == 2
        assert "[2]" not in result

    def test_render_broken_citation(self, db):
        text = "Cited.[[cite:99999]]"
        result = render_all_links(text)
        assert "<sup>[?]</sup>" in result

    def test_render_plain_text(self, citation_instance):
        text = f"Cited.[[cite:{citation_instance.pk}]]"
        result = render_all_links(text, plain_text=True)
        assert result == "Cited.[1]"

    def test_render_broken_plain_text(self, db):
        text = "Cited.[[cite:99999]]"
        result = render_all_links(text, plain_text=True)
        assert "[?]" in result
        assert "<sup>" not in result

    def test_mixed_citations_and_entity_links(self, manufacturer, citation_instance):
        text = (
            f"Made by [[manufacturer:id:{manufacturer.pk}]]."
            f"[[cite:{citation_instance.pk}]]"
        )
        result = render_all_links(text)
        assert "[Williams](/manufacturers/williams)" in result
        assert (
            f'<sup data-cite-id="{citation_instance.pk}" data-cite-index="1"'
            f' tabindex="0" role="button">[1]</sup>' in result
        )

    def test_sync_references_for_citations(self, citation_instance, system):
        text = f"Cited.[[cite:{citation_instance.pk}]]"
        sync_references(system, text)
        refs = RecordReference.objects.all()
        assert refs.count() == 1

    def test_cite_survives_html_pipeline(self, citation_instance):
        from apps.core.markdown import render_markdown_html

        text = f"Production was 4,000 units.[[cite:{citation_instance.pk}]]"
        html = render_markdown_html(text)
        pk = citation_instance.pk
        assert f'data-cite-id="{pk}"' in html
        assert 'data-cite-index="1"' in html
        assert 'tabindex="0"' in html
        assert 'role="button"' in html
        assert "[1]" in html


class TestMetadataCollection:
    """Tests for render_all_links metadata_out collection."""

    def test_collects_citation_metadata(self, citation_source_with_links):
        from apps.provenance.models import CitationInstance

        ci = CitationInstance.objects.create(
            citation_source=citation_source_with_links, locator="p. 42"
        )
        text = f"Cited.[[cite:{ci.pk}]]"
        metadata: list[dict[str, Any]] = []
        render_all_links(text, metadata_out=metadata)
        assert len(metadata) == 1
        entry = metadata[0]
        assert entry["id"] == ci.pk
        assert entry["index"] == 1
        assert entry["source_name"] == "The Encyclopedia of Pinball"
        assert entry["source_type"] == "book"
        assert entry["author"] == "Jeff Lawton"
        assert entry["year"] == 2001
        assert entry["locator"] == "p. 42"
        assert len(entry["links"]) == 1
        assert entry["links"][0]["url"] == "https://example.com/archive"
        assert entry["links"][0]["label"] == "Archive scan"

    def test_metadata_deduplicated_by_pk(self, citation_instance):
        pk = citation_instance.pk
        text = f"First.[[cite:{pk}]] Second.[[cite:{pk}]]"
        metadata: list[dict[str, Any]] = []
        render_all_links(text, metadata_out=metadata)
        assert len(metadata) == 1
        assert metadata[0]["id"] == pk

    def test_metadata_ordered_by_first_appearance(self, citation_source):
        from apps.provenance.models import CitationInstance

        ci1 = CitationInstance.objects.create(
            citation_source=citation_source, locator="p. 10"
        )
        ci2 = CitationInstance.objects.create(
            citation_source=citation_source, locator="p. 20"
        )
        text = f"First.[[cite:{ci1.pk}]] Second.[[cite:{ci2.pk}]]"
        metadata: list[dict[str, Any]] = []
        render_all_links(text, metadata_out=metadata)
        assert len(metadata) == 2
        assert metadata[0]["index"] == 1
        assert metadata[0]["id"] == ci1.pk
        assert metadata[1]["index"] == 2
        assert metadata[1]["id"] == ci2.pk

    def test_no_metadata_when_none(self, citation_instance):
        """metadata_out=None (default) doesn't break anything."""
        text = f"Cited.[[cite:{citation_instance.pk}]]"
        result = render_all_links(text)
        assert "data-cite-id" in result

    def test_no_metadata_for_entity_links(self, manufacturer):
        """Only link types with collect_metadata produce metadata."""
        text = f"See [[manufacturer:id:{manufacturer.pk}]]"
        metadata: list[dict[str, Any]] = []
        render_all_links(text, metadata_out=metadata)
        assert len(metadata) == 0
