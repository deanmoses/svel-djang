"""Tests for the markdown rendering pipeline."""

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

    def test_bio_field(self):
        from apps.catalog.models import Person

        person = Person(name="Pat", slug="pat", bio="*italic*")
        result = render_markdown_fields(person)
        assert "bio_html" in result
        assert "<em>italic</em>" in result["bio_html"]

    def test_no_markdown_fields(self):
        from apps.catalog.models import CorporateEntity

        entity = CorporateEntity(name="Test")
        result = render_markdown_fields(entity)
        assert result == {}
