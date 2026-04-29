"""Tests for the AI desc source registry and validate_cross_entity_wikilinks.

Locks in that the registry derives Location from CatalogModel walks (no
manual extras) and that the wikilink validator accepts Location's
multi-segment ``location_path`` ids.
"""

from __future__ import annotations

import io
import json

import pytest

from apps.catalog.management.commands.ingest_pinbase import (
    _ai_desc_source_registry,
    validate_cross_entity_wikilinks,
)
from apps.catalog.models import GameplayFeature, Location


def test_ai_desc_registry_contains_location():
    """The CatalogModel walk picks Location up — no Location-specific extra needed."""
    assert (Location, "location") in _ai_desc_source_registry()


def test_ai_desc_registry_entries_are_unique():
    slugs = [slug for _, slug in _ai_desc_source_registry()]
    assert len(slugs) == len(set(slugs))


def _write_taxonomy_with_link(tmp_path, link: str):
    """Write a minimal franchise.json containing a [[link]] in a description."""
    (tmp_path / "franchise.json").write_text(
        json.dumps(
            [
                {
                    "slug": "test-franchise",
                    "name": "Test",
                    "description": f"See {link} for details.",
                }
            ]
        )
    )


@pytest.mark.django_db
class TestValidateCrossEntityWikilinks:
    @pytest.fixture
    def chicago(self):
        usa = Location.objects.create(
            location_path="usa", slug="usa", name="USA", location_type="country"
        )
        il = Location.objects.create(
            location_path="usa/il",
            slug="il",
            name="Illinois",
            location_type="state",
            parent=usa,
        )
        return Location.objects.create(
            location_path="usa/il/chicago",
            slug="chicago",
            name="Chicago",
            location_type="city",
            parent=il,
        )

    def test_resolves_location_path_with_slashes(self, tmp_path, chicago):
        _write_taxonomy_with_link(tmp_path, "[[location:usa/il/chicago]]")
        stderr = io.StringIO()
        validate_cross_entity_wikilinks(tmp_path, io.StringIO(), stderr)
        assert stderr.getvalue() == ""

    def test_flags_broken_location_ref(self, tmp_path, chicago):
        _write_taxonomy_with_link(tmp_path, "[[location:does/not/exist]]")
        stderr = io.StringIO()
        validate_cross_entity_wikilinks(tmp_path, io.StringIO(), stderr)
        out = stderr.getvalue()
        assert "[[location:does/not/exist]] not found" in out

    def test_resolves_kebab_case_link_type(self, tmp_path):
        """Validator keys must match the markdown renderer's registration.

        Both the validator and the renderer key on ``model.entity_type``
        (kebab-case singular). Pindata authors the same form. A multi-word
        entity type like ``gameplay-feature`` exercises the case where
        ``__name__.lower()`` and ``entity_type`` diverge.
        """
        GameplayFeature.objects.create(slug="multiball", name="Multiball")
        _write_taxonomy_with_link(tmp_path, "[[gameplay-feature:multiball]]")
        stderr = io.StringIO()
        validate_cross_entity_wikilinks(tmp_path, io.StringIO(), stderr)
        assert stderr.getvalue() == ""

    def test_malformed_path_does_not_crash(self, tmp_path, chicago):
        """Double-slash paths tokenize and surface as broken-ref warnings."""
        _write_taxonomy_with_link(tmp_path, "[[location:foo//bar]]")
        stderr = io.StringIO()
        validate_cross_entity_wikilinks(tmp_path, io.StringIO(), stderr)
        assert "[[location:foo//bar]] not found" in stderr.getvalue()
