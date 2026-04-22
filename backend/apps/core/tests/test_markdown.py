"""Tests for the markdown rendering pipeline."""

from typing import Any

import pytest

from apps.core.markdown import render_markdown_fields, render_markdown_html


class TestRenderMarkdownHtml:
    def test_empty_string(self):
        assert render_markdown_html("") == ""

    def test_none_input(self):
        assert render_markdown_html(None) == ""

    def test_bold(self):
        result = render_markdown_html("**bold**")
        assert "<strong>bold</strong>" in result

    def test_italic(self):
        result = render_markdown_html("*italic*")
        assert "<em>italic</em>" in result

    def test_link(self):
        result = render_markdown_html("[text](https://example.com)")
        assert 'href="https://example.com"' in result
        assert ">text</a>" in result

    def test_unordered_list(self):
        result = render_markdown_html("- item 1\n- item 2")
        assert "<ul>" in result
        assert "<li>item 1</li>" in result

    def test_heading(self):
        result = render_markdown_html("## Heading")
        assert "<h2>Heading</h2>" in result

    def test_xss_script_stripped(self):
        result = render_markdown_html('<script>alert("xss")</script>')
        assert "<script>" not in result
        assert "alert" not in result

    def test_xss_onerror_stripped(self):
        result = render_markdown_html('<img src=x onerror="alert(1)">')
        assert "onerror" not in result

    def test_auto_linkify(self):
        result = render_markdown_html("Visit https://example.com today")
        assert 'href="https://example.com"' in result

    def test_line_breaks(self):
        result = render_markdown_html("line 1\nline 2")
        assert "<br>" in result

    def test_task_list_unchecked(self):
        result = render_markdown_html("- [ ] todo")
        assert 'type="checkbox"' in result
        assert "checked" not in result

    def test_task_list_checked(self):
        result = render_markdown_html("- [x] done")
        assert 'type="checkbox"' in result
        assert "checked" in result

    def test_table(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        result = render_markdown_html(md)
        assert "<table>" in result
        assert "<td>" in result

    def test_strikethrough(self):
        result = render_markdown_html("~~deleted~~")
        assert "<s>deleted</s>" in result

    @pytest.mark.django_db
    def test_broken_link_renders(self):
        result = render_markdown_html("See [[manufacturer:id:99999]]")
        assert "broken link" in result

    @pytest.mark.django_db
    def test_metadata_out_collects_citations(self):
        from apps.citation.models import CitationSource
        from apps.provenance.models import CitationInstance

        src = CitationSource.objects.create(
            name="Source Book", source_type="book", author="A. Author"
        )
        ci = CitationInstance.objects.create(citation_source=src, locator="ch. 3")
        metadata: list[dict[str, Any]] = []
        html = render_markdown_html(f"Fact.[[cite:{ci.pk}]]", metadata_out=metadata)
        assert "data-cite-id" in html
        assert len(metadata) == 1
        assert metadata[0]["source_name"] == "Source Book"

    def test_metadata_out_default_none(self):
        """metadata_out defaults to None; existing callers unaffected."""
        result = render_markdown_html("plain text")
        assert "plain text" in result


class TestRenderMarkdownFields:
    def test_returns_html_for_markdown_fields(self):
        from apps.catalog.models import Manufacturer

        mfr = Manufacturer(name="Test", slug="test", description="**bold**")
        result = render_markdown_fields(mfr)
        assert "description_html" in result
        assert "<strong>bold</strong>" in result["description_html"]

    def test_empty_description(self):
        from apps.catalog.models import Manufacturer

        mfr = Manufacturer(name="Test", slug="test", description="")
        result = render_markdown_fields(mfr)
        assert result["description_html"] == ""

    def test_person_description_field(self):
        from apps.catalog.models import Person

        person = Person(name="Pat", slug="pat", description="*italic*")
        result = render_markdown_fields(person)
        assert "description_html" in result
        assert "<em>italic</em>" in result["description_html"]

    def test_no_markdown_fields(self):
        from apps.catalog.models import Location

        loc = Location(
            location_path="usa", slug="usa", name="USA", location_type="country"
        )
        result = render_markdown_fields(loc)
        assert result == {}

    @pytest.mark.django_db
    def test_citations_key_included(self):
        from apps.catalog.models import Manufacturer
        from apps.citation.models import CitationSource
        from apps.provenance.models import CitationInstance

        src = CitationSource.objects.create(name="Book", source_type="book")
        ci = CitationInstance.objects.create(citation_source=src, locator="p. 1")
        mfr = Manufacturer(
            name="Test", slug="test", description=f"Info.[[cite:{ci.pk}]]"
        )
        result = render_markdown_fields(mfr)
        citations = result["description_citations"]
        assert isinstance(citations, list)
        assert citations
        citation = citations[0]
        assert isinstance(citation, dict)
        assert "description_html" in result
        assert "description_citations" in result
        assert len(citations) == 1
        assert citation["id"] == ci.pk

    def test_no_citations_key_when_empty(self):
        from apps.catalog.models import Manufacturer

        mfr = Manufacturer(name="Test", slug="test", description="No citations here")
        result = render_markdown_fields(mfr)
        assert "description_citations" not in result
