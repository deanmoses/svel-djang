"""Tests for the wikilinks renderer/picker registries.

Covers the four invariants the WikilinkableModel hoist locks in:
- non-Wikilinkable LinkableModels render but are absent from the picker;
- the picker's exact membership matches the explicit post-hoist target list;
- the default ``link_autocomplete_serialize`` produces the standard
  ``(public_id, name)`` shape;
- the renderer's ``LinkType`` registry and the ingest validator's
  catalog-model lookup agree on type-key → model resolution.

Plus smoke tests on registry contents (``TestLinkRegistry``).
"""

from __future__ import annotations

import pytest
from django.apps import apps as django_apps

from apps.catalog._walks import catalog_models
from apps.core.schemas import LinkTargetSchema
from apps.core.wikilinks import (
    get_enabled_link_types,
    get_link_type,
    get_picker_type,
    get_picker_types,
)

# Explicit post-hoist target — every model that should appear in the
# wikilink picker, by ``entity_type`` (kebab-case singular). Hard-coded so a
# missed ``WikilinkableModel`` inheritance fails this test rather than
# silently dropping an entity from the picker.
EXPECTED_PICKER_TYPES: frozenset[str] = frozenset(
    {
        # Catalog entities
        "title",
        "model",
        "manufacturer",
        "person",
        "corporate-entity",
        "system",
        "technology-generation",
        "technology-subgeneration",
        "display-type",
        "display-subtype",
        "cabinet",
        "game-format",
        "reward-type",
        "tag",
        "credit-role",
        "theme",
        "gameplay-feature",
        "franchise",
        "series",
        # Cross-app picker entries
        "cite",
    }
)


class TestPickerMembership:
    def test_picker_matches_expected_target(self):
        """The registered ``PickerType`` set is exactly EXPECTED_PICKER_TYPES.

        Catches a missed ``WikilinkableModel`` inheritance on any of the
        catalog entities, and catches accidental adds.
        """
        registered = {entry["name"] for entry in get_picker_types()}
        assert registered == EXPECTED_PICKER_TYPES

    def test_location_renders_but_is_absent_from_picker(self):
        """Negative: ``Location`` is a ``LinkableModel`` (CatalogModel) but
        not a ``WikilinkableModel``. It registers a ``LinkType`` (so
        ``[[location:...]]`` markdown still resolves) but has no
        ``PickerType``. This is the live structural-suppression case the
        hoist replaces the ``link_autocomplete_serialize = None`` sentinel
        with.
        """
        assert get_link_type("location") is not None
        assert get_picker_type("location") is None


class TestDefaultLinkSerialize:
    def test_default_serializer_produces_public_id_and_name(self, db):
        """An entity without an explicit ``link_autocomplete_serialize``
        override produces ``LinkTargetSchema(ref=public_id, label=name)``.
        """
        from apps.catalog.models import Manufacturer

        manufacturer = Manufacturer.objects.create(name="Williams", slug="williams")
        # ``link_autocomplete_serialize`` is the inherited
        # ``WikilinkableModel`` default for Manufacturer (no override).
        result = Manufacturer.link_autocomplete_serialize(manufacturer)
        assert isinstance(result, LinkTargetSchema)
        assert result.ref == "williams"
        assert result.label == "Williams"


class TestRendererValidatorParity:
    def test_link_type_keys_match_catalog_model_walk(self):
        """For every catalog ``LinkType``, the same ``entity_type`` key is
        reachable from the ingest validator's CatalogModel walk and points
        to the same model class.

        The validator at ``ingest_pinbase.validate_cross_entity_wikilinks``
        builds its lookup as ``{model.entity_type: model for model in
        catalog_models()}``; the renderer's registration loop builds
        ``LinkType.name = model.entity_type``.
        Both must resolve any ``[[<entity-type>:<public-id>]]`` to the
        same row.
        """
        validator_lookup = {model.entity_type: model for model in catalog_models()}

        catalog_link_types = [
            lt
            for lt in get_enabled_link_types()
            if lt.model_path.startswith("catalog.")
        ]
        # Sanity: at least the 20 catalog entities
        assert len(catalog_link_types) >= 20

        for lt in catalog_link_types:
            assert lt.name in validator_lookup, (
                f"LinkType {lt.name!r} has no matching CatalogModel "
                f"with entity_type={lt.name!r}"
            )
            renderer_model = django_apps.get_model(lt.model_path)
            validator_model = validator_lookup[lt.name]
            assert renderer_model is validator_model, (
                f"LinkType {lt.name!r}: renderer points to "
                f"{renderer_model.__name__}, validator points to "
                f"{validator_model.__name__}"
            )


@pytest.mark.parametrize(
    "name",
    sorted(EXPECTED_PICKER_TYPES - {"cite"}),
)
def test_every_catalog_picker_type_has_matching_link_type(name):
    """Every catalog picker type also has a renderer ``LinkType`` under the
    same key. Sanity-check the two registries agree on naming."""
    assert get_link_type(name) is not None, (
        f"PickerType {name!r} has no matching LinkType — the renderer "
        f"can't resolve [[{name}:public-id]]"
    )


class TestLinkRegistry:
    """Smoke tests on ``LinkType`` registry contents."""

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

    def test_picker_types_include_custom_flow(self):
        """``get_picker_types()`` includes types with ``flow='custom'``
        (citations) alongside standard-flow types."""
        types = get_picker_types()
        types_by_name = {t["name"]: t for t in types}
        assert "cite" in types_by_name
        assert types_by_name["cite"]["flow"] == "custom"

    def test_picker_types_have_flow_field(self):
        for t in get_picker_types():
            assert "flow" in t, f"Missing 'flow' field on {t['name']}"

    def test_standard_types_have_standard_flow(self):
        types = get_picker_types()
        types_by_name = {t["name"]: t for t in types}
        assert types_by_name["manufacturer"]["flow"] == "standard"
