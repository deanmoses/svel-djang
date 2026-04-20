"""Tests for resolve_after_mutation() dispatch and alias auto-discovery."""

import pytest

from apps.catalog._alias_registry import discover_alias_types
from apps.catalog.claims import _get_literal_schemas, build_relationship_claim
from apps.catalog.models import (
    Manufacturer,
    TechnologyGeneration,
    Theme,
    Title,
)
from apps.catalog.resolve._dispatch import resolve_after_mutation
from apps.provenance.models import Claim, Source
from apps.catalog.tests.conftest import make_machine_model


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def source(db):
    return Source.objects.create(
        name="Test Source", source_type="editorial", priority=100
    )


@pytest.fixture
def theme(db):
    return Theme.objects.create(name="Placeholder Theme", slug="placeholder-theme")


@pytest.fixture
def title(db):
    return Title.objects.create(name="Placeholder Title", slug="placeholder-title")


@pytest.fixture
def manufacturer(db):
    return Manufacturer.objects.create(name="Placeholder Mfr", slug="placeholder-mfr")


@pytest.fixture
def pm(db):
    return make_machine_model(name="Placeholder", slug="placeholder")


# ---------------------------------------------------------------------------
# Auto-discovery tests
# ---------------------------------------------------------------------------


class TestDiscoverAliasTypes:
    def test_discovers_all_seven_alias_types(self):
        result = discover_alias_types()
        assert len(result) == 7

    def test_known_types_present(self):
        field_names = {fn for _, fn in discover_alias_types()}
        expected = {
            "theme_alias",
            "manufacturer_alias",
            "person_alias",
            "gameplay_feature_alias",
            "reward_type_alias",
            "corporate_entity_alias",
            "location_alias",
        }
        assert field_names == expected


class TestLiteralSchemasAutoPopulated:
    def test_contains_abbreviation(self):
        schemas = _get_literal_schemas()
        assert "abbreviation" in schemas

    def test_contains_all_alias_types(self):
        schemas = _get_literal_schemas()
        for _, field_name in discover_alias_types():
            assert field_name in schemas
            assert schemas[field_name].value_key == "alias_value"
            assert schemas[field_name].identity_key == "alias"


# ---------------------------------------------------------------------------
# resolve_after_mutation() routing tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMachineModelRouting:
    def test_scalars_resolved(self, pm, source):
        ss = TechnologyGeneration.objects.create(name="Solid State", slug="solid-state")
        Claim.objects.assert_claim(pm, "name", "Test Machine", source=source)
        Claim.objects.assert_claim(
            pm, "technology_generation", "solid-state", source=source
        )

        resolve_after_mutation(pm, field_names=["name", "technology_generation"])

        pm.refresh_from_db()
        assert pm.name == "Test Machine"
        assert pm.technology_generation == ss

    def test_m2m_resolved(self, pm, source):
        Claim.objects.assert_claim(pm, "name", "Test Machine", source=source)
        theme = Theme.objects.create(name="Adventure", slug="adventure")
        ck, val = build_relationship_claim("theme", {"theme": theme.pk})
        Claim.objects.assert_claim(pm, "theme", val, source=source, claim_key=ck)

        resolve_after_mutation(pm, field_names=["name", "theme"])

        assert theme in pm.themes.all()


@pytest.mark.django_db
class TestScalarResolution:
    def test_non_machine_model_scalars(self, theme, source):
        Claim.objects.assert_claim(theme, "name", "Updated Theme", source=source)

        resolve_after_mutation(theme, field_names=["name"])

        theme.refresh_from_db()
        assert theme.name == "Updated Theme"


@pytest.mark.django_db
class TestAliasDispatch:
    def test_theme_alias(self, theme, source):
        ck, val = build_relationship_claim("theme_alias", {"alias_value": "test-alias"})
        Claim.objects.assert_claim(
            theme, "theme_alias", val, source=source, claim_key=ck
        )

        resolve_after_mutation(theme, field_names=["theme_alias"])

        assert theme.aliases.filter(value="test-alias").exists()

    def test_manufacturer_alias(self, manufacturer, source):
        ck, val = build_relationship_claim(
            "manufacturer_alias", {"alias_value": "mfr-alias"}
        )
        Claim.objects.assert_claim(
            manufacturer, "manufacturer_alias", val, source=source, claim_key=ck
        )

        resolve_after_mutation(manufacturer, field_names=["manufacturer_alias"])

        assert manufacturer.aliases.filter(value="mfr-alias").exists()


@pytest.mark.django_db
class TestParentDispatch:
    def test_theme_parent(self, source):
        parent_theme = Theme.objects.create(name="Parent", slug="parent")
        child_theme = Theme.objects.create(name="Child", slug="child")

        ck, val = build_relationship_claim("theme_parent", {"parent": parent_theme.pk})
        Claim.objects.assert_claim(
            child_theme, "theme_parent", val, source=source, claim_key=ck
        )

        resolve_after_mutation(child_theme, field_names=["theme_parent"])

        assert parent_theme in child_theme.parents.all()


@pytest.mark.django_db
class TestCustomDispatch:
    def test_abbreviation(self, title, source):
        Claim.objects.assert_claim(title, "name", title.name, source=source)
        ck, val = build_relationship_claim("abbreviation", {"value": "TST"})
        Claim.objects.assert_claim(
            title, "abbreviation", val, source=source, claim_key=ck
        )

        resolve_after_mutation(title, field_names=["abbreviation"])

        assert title.abbreviations.filter(value="TST").exists()


@pytest.mark.django_db
class TestEntityTypeGuard:
    def test_mismatched_alias_namespace_ignored(self, manufacturer, source):
        """theme_alias on a Manufacturer should not call the Theme alias resolver."""
        resolve_after_mutation(manufacturer, field_names=["theme_alias"])
        # No error, no side effects — the namespace is silently skipped.

    def test_mismatched_custom_namespace_ignored(self, theme, source):
        """abbreviation on a Theme should not call the Title abbreviation resolver."""
        resolve_after_mutation(theme, field_names=["abbreviation"])


@pytest.mark.django_db
class TestFieldNamesNone:
    def test_resolves_scalars(self, theme, source):
        Claim.objects.assert_claim(theme, "name", "Fallback Theme", source=source)

        resolve_after_mutation(theme, field_names=None)

        theme.refresh_from_db()
        assert theme.name == "Fallback Theme"

    def test_resolves_aliases(self, theme, source):
        ck, val = build_relationship_claim(
            "theme_alias", {"alias_value": "fallback-alias"}
        )
        Claim.objects.assert_claim(
            theme, "theme_alias", val, source=source, claim_key=ck
        )

        resolve_after_mutation(theme, field_names=None)

        assert theme.aliases.filter(value="fallback-alias").exists()
