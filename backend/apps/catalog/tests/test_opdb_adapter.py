"""Plan-boundary tests for the OPDB adapter.

Tests build_opdb_plan() directly: given these OPDB records and this DB state,
what plan is produced?  No apply_plan() calls — these verify the adapter's
output, not the framework's execution.
"""

from __future__ import annotations

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import CommandError

from apps.catalog.ingestion.opdb.adapter import build_opdb_plan, parse_opdb_records
from apps.catalog.ingestion.opdb.records import OpdbRecord
from apps.catalog.models import (
    GameplayFeature,
    MachineModel,
)
from apps.provenance.models import Source
from apps.catalog.tests.conftest import make_machine_model


@pytest.fixture
def opdb_source(db):
    return Source.objects.create(
        slug="opdb",
        name="OPDB",
        source_type="database",
        priority=200,
    )


def _make_record(**overrides) -> OpdbRecord:
    """Build a minimal OpdbRecord with sensible defaults."""
    defaults = {
        "opdb_id": "GTEST-M1",
        "name": "Test Game",
        "is_machine": True,
        "physical_machine": 1,
    }
    defaults.update(overrides)
    return OpdbRecord(**defaults)


def _assertion_fields(plan, *, handle=None, object_id=None) -> set[str]:
    """Extract field_names from assertions targeting a handle or object_id."""
    result = set()
    for a in plan.assertions:
        if handle is not None and a.handle == handle:
            result.add(a.field_name)
        elif object_id is not None and a.object_id == object_id:
            result.add(a.field_name)
    return result


def _assertion_value(plan, field_name, *, handle=None, object_id=None):
    """Get the value of a specific assertion."""
    for a in plan.assertions:
        if a.field_name != field_name:
            continue
        if handle is not None and a.handle == handle:
            return a.value
        if object_id is not None and a.object_id == object_id:
            return a.value
    raise AssertionError(
        f"No assertion for field_name={field_name!r} "
        f"with handle={handle!r} object_id={object_id!r}"
    )


@pytest.mark.django_db
class TestPlanForNewEntities:
    """OPDB records with no matching pindata MachineModel abort plan building."""

    def test_new_machine_raises_command_error(self, opdb_source):
        rec = _make_record(opdb_id="GNEW-M1", name="Brand New")
        with pytest.raises(CommandError, match="do not match any existing"):
            build_opdb_plan([rec], opdb_source, "test-fp")

    def test_error_lists_opdb_id_and_name(self, opdb_source):
        rec = _make_record(opdb_id="GNEW-M1", name="Brand New")
        with pytest.raises(CommandError) as exc:
            build_opdb_plan([rec], opdb_source, "test-fp")
        assert "GNEW-M1" in str(exc.value)
        assert "Brand New" in str(exc.value)


@pytest.mark.django_db
class TestPlanForExistingEntities:
    """When OPDB records match existing models, assertions target the entity PK."""

    def test_matched_by_opdb_id(self, opdb_source):
        pm = make_machine_model(
            name="Existing Game",
            slug="existing-game",
            opdb_id="GEXIST-M1",
        )
        rec = _make_record(opdb_id="GEXIST-M1", name="Existing Game")
        plan = build_opdb_plan([rec], opdb_source, "test-fp")

        assert len(plan.entities) == 0
        fields = _assertion_fields(plan, object_id=pm.pk)
        assert "name" in fields
        assert "opdb_id" in fields
        # No slug claim for existing entities.
        assert "slug" not in fields

    def test_matched_by_ipdb_id(self, opdb_source):
        pm = make_machine_model(
            name="IPDB Game",
            slug="ipdb-game",
            ipdb_id=9999,
        )
        rec = _make_record(opdb_id="GCROSS-M1", name="IPDB Game", ipdb_id=9999)
        plan = build_opdb_plan([rec], opdb_source, "test-fp")

        assert len(plan.entities) == 0
        fields = _assertion_fields(plan, object_id=pm.pk)
        assert "name" in fields
        assert "opdb_id" in fields

    def test_plan_counts_matched(self, opdb_source):
        make_machine_model(
            name="Existing",
            slug="existing",
            opdb_id="GEXIST-M1",
        )
        rec = _make_record(opdb_id="GEXIST-M1")
        plan = build_opdb_plan([rec], opdb_source, "test-fp")

        assert plan.records_parsed == 1
        assert plan.records_matched == 1

    def test_assertions_target_content_type(self, opdb_source):
        pm = make_machine_model(
            name="Existing",
            slug="existing",
            opdb_id="GEXIST-M1",
        )
        rec = _make_record(opdb_id="GEXIST-M1")
        plan = build_opdb_plan([rec], opdb_source, "test-fp")

        ct_id = ContentType.objects.get_for_model(MachineModel).pk
        for a in plan.assertions:
            if a.object_id == pm.pk:
                assert a.content_type_id == ct_id


@pytest.mark.django_db
class TestPlanForAliases:
    """Alias records must match an existing pindata MachineModel too."""

    def test_unmatched_alias_with_parent_in_same_batch_raises(self, opdb_source):
        parent = _make_record(opdb_id="GNEW-M1", name="Parent")
        alias = OpdbRecord(
            opdb_id="GNEW-M1-AAlias",
            name="Alias",
            is_alias=True,
            is_machine=False,
        )
        with pytest.raises(CommandError, match="do not match any existing"):
            build_opdb_plan([parent, alias], opdb_source, "test-fp")

    def test_alias_matched_to_existing_mm(self, opdb_source):
        make_machine_model(
            name="Parent",
            slug="parent",
            opdb_id="GEXIST-M1",
        )
        alias_mm = make_machine_model(
            name="Alias",
            slug="alias",
            opdb_id="GEXIST-M1-AAlias",
        )
        alias = OpdbRecord(
            opdb_id="GEXIST-M1-AAlias",
            name="Alias",
            is_alias=True,
            is_machine=False,
        )
        plan = build_opdb_plan([alias], opdb_source, "test-fp")

        # No new entities — the alias matches an existing MachineModel.
        assert len(plan.entities) == 0
        # Claims target the existing MachineModel's PK.
        assert any(a.object_id == alias_mm.pk for a in plan.assertions)

    def test_orphan_alias_produces_warning(self, opdb_source):
        alias = OpdbRecord(
            opdb_id="GORPHAN-M1-AAlias",
            name="Orphan",
            is_alias=True,
            is_machine=False,
        )
        plan = build_opdb_plan([alias], opdb_source, "test-fp")

        assert len(plan.entities) == 0
        assert any("GORPHAN-M1" in w for w in plan.warnings)

    def test_non_physical_machine_excluded(self, opdb_source):
        """Non-physical machines (physical_machine=0) are skipped."""
        rec = _make_record(opdb_id="GVIRT-M1", name="Virtual", physical_machine=0)
        plan = build_opdb_plan([rec], opdb_source, "test-fp")

        assert len(plan.entities) == 0
        assert len(plan.assertions) == 0


@pytest.mark.django_db
class TestFeatureClassification:
    """OPDB features array terms are classified into vocabulary claims."""

    @pytest.fixture(autouse=True)
    def _seed(self, db):
        return make_machine_model(
            name="Test Game", slug="test-game", opdb_id="GTEST-M1"
        )

    def test_gameplay_feature_claim(self, opdb_source):
        GameplayFeature.objects.create(slug="multiball", name="Multiball")
        rec = _make_record(features=["Multiball"])
        plan = build_opdb_plan([rec], opdb_source, "test-fp")

        fields = [a.field_name for a in plan.assertions]
        assert "gameplay_feature" in fields

    def test_unknown_feature_in_warnings(self, opdb_source):
        rec = _make_record(features=["Completely Unknown Feature"])
        plan = build_opdb_plan([rec], opdb_source, "test-fp")

        assert any("unmatched" in w.lower() for w in plan.warnings)

    def test_variant_labels_silently_skipped(self, opdb_source):
        """Known variant labels (LE, Premium, etc.) produce no warnings."""
        rec = _make_record(features=["Limited Edition", "Premium"])
        plan = build_opdb_plan([rec], opdb_source, "test-fp")

        feature_warnings = [w for w in plan.warnings if "unmatched" in w.lower()]
        assert not feature_warnings


@pytest.mark.django_db
class TestIpdbCrossReferenceBackfill:
    """Parent matched by ipdb_id is findable by opdb_id for alias reconciliation."""

    def test_alias_finds_parent_matched_by_ipdb(self, opdb_source):
        """Parent matched via ipdb_id should still be findable by opdb_id for aliases."""
        make_machine_model(
            name="IPDB Parent",
            slug="ipdb-parent",
            ipdb_id=5555,
        )
        alias_mm = make_machine_model(
            name="Cross Alias",
            slug="cross-alias",
            opdb_id="GCROSS-M1-AAlias",
        )
        parent = _make_record(opdb_id="GCROSS-M1", name="IPDB Parent", ipdb_id=5555)
        alias = OpdbRecord(
            opdb_id="GCROSS-M1-AAlias",
            name="Cross Alias",
            is_alias=True,
            is_machine=False,
        )
        plan = build_opdb_plan([parent, alias], opdb_source, "test-fp")

        # Alias matched to its pre-seeded MM; no orphan warning.
        assert not any("GCROSS-M1" in w and "not found" in w for w in plan.warnings)
        assert any(a.object_id == alias_mm.pk for a in plan.assertions)


@pytest.mark.django_db
class TestResolveHooks:
    """The plan registers relationship resolve hooks."""

    def test_resolve_hooks_registered(self, opdb_source):
        make_machine_model(name="Test Game", slug="test-game", opdb_id="GTEST-M1")
        rec = _make_record()
        plan = build_opdb_plan([rec], opdb_source, "test-fp")

        ct_id = ContentType.objects.get_for_model(MachineModel).pk
        assert ct_id in plan.resolve_hooks
        assert (
            len(plan.resolve_hooks[ct_id]) == 4
        )  # gameplay, abbreviation, reward, tag


@pytest.mark.django_db
class TestParseOpdbRecords:
    """Test the parsing helper."""

    def test_valid_records(self):
        raw = [
            {"opdb_id": "G1-M1", "name": "Game One", "is_machine": True},
            {"opdb_id": "G2-M1", "name": "Game Two", "is_machine": True},
        ]
        records = parse_opdb_records(raw)
        assert len(records) == 2
        assert records[0].opdb_id == "G1-M1"

    def test_missing_opdb_id_raises(self):
        raw = [{"name": "No ID"}]
        with pytest.raises(ValueError, match="failed to parse"):
            parse_opdb_records(raw)

    def test_mixed_valid_and_invalid_raises(self):
        raw = [
            {"opdb_id": "G1-M1", "name": "Valid"},
            {"name": "Missing ID"},
        ]
        with pytest.raises(ValueError, match="1 OPDB record"):
            parse_opdb_records(raw)
