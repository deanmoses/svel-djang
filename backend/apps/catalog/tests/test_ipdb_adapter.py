"""Plan-boundary tests for the IPDB adapter.

Tests build_ipdb_plan() directly: given these IPDB records and this DB state,
what plan is produced?  No apply_plan() calls — these verify the adapter's
output, not the framework's execution.
"""

from __future__ import annotations

import pytest
from django.core.management.base import CommandError

from apps.catalog.ingestion.ipdb.adapter import build_ipdb_plan
from apps.catalog.ingestion.ipdb.records import IpdbRecord
from apps.catalog.models import (
    CorporateEntity,
    GameplayFeature,
    MachineModel,
    Person,
    RewardType,
    Theme,
)
from apps.catalog.tests.conftest import make_machine_model
from apps.provenance.models import Source

pytestmark = pytest.mark.django_db


@pytest.fixture
def ipdb_source(db):
    return Source.objects.create(
        slug="ipdb",
        name="IPDB",
        source_type="database",
        priority=100,
    )


@pytest.fixture
def _seed_mm_9999(db):
    """Pre-seed the default test MachineModel (ipdb_id=9999).

    The adapter requires every IPDB record to match an existing MachineModel;
    nearly every test here feeds _make_record(ipdb_id=9999, ...), so centralise
    the seed. Tests that want to test the unmatched-record behavior can omit
    this fixture and/or use a different ipdb_id.
    """
    return make_machine_model(name="Test Machine", slug="test-machine", ipdb_id=9999)


@pytest.fixture
def _seed_mm_9998_and_9999(_seed_mm_9999, db):
    """Pre-seed both ipdb_id=9998 and 9999 for tests that use both."""
    return (
        make_machine_model(
            name="Test Machine 9998", slug="test-machine-9998", ipdb_id=9998
        ),
        _seed_mm_9999,
    )


def _make_record(**overrides) -> IpdbRecord:
    """Build a minimal IpdbRecord with sensible defaults."""
    defaults = {"ipdb_id": 9999, "title": "Test Machine"}
    defaults.update(overrides)
    return IpdbRecord(**defaults)


def _assertion_fields(plan, *, handle=None, object_id=None) -> set[str]:
    """Extract field_names from assertions targeting a handle or object_id."""
    result = set()
    for a in plan.assertions:
        if (handle is not None and a.handle == handle) or (
            object_id is not None and a.object_id == object_id
        ):
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


def _assertions_for(plan, *, handle=None, object_id=None):
    """Return all assertions targeting a handle or object_id."""
    result = []
    for a in plan.assertions:
        if (handle is not None and a.handle == handle) or (
            object_id is not None and a.object_id == object_id
        ):
            result.append(a)
    return result


def _deferred_assertions(plan, field_name, *, handle=None, object_id=None):
    """Return deferred (identity_refs) assertions for a field."""
    result = []
    for a in plan.assertions:
        if a.field_name != field_name or not a.relationship_namespace:
            continue
        if (handle is not None and a.handle == handle) or (
            object_id is not None and a.object_id == object_id
        ):
            result.append(a)
    return result


# ---------------------------------------------------------------------------
# MachineModel reconciliation
# ---------------------------------------------------------------------------


class TestMachineModelReconciliation:
    @pytest.fixture(autouse=True)
    def _setup(self, ipdb_narrative_features):
        """Narrative features must exist for vocabulary validation."""

    def test_unmatched_record_raises(self, ipdb_source):
        """IPDB records with no matching MachineModel abort plan building."""
        rec = _make_record(ipdb_id=9999, title="Brand New")
        with pytest.raises(CommandError, match="do not match any existing"):
            build_ipdb_plan([rec], ipdb_source, "fp-1")

    def test_existing_machine_matched_no_entity_create(self, ipdb_source):
        make_machine_model(name="Existing", slug="existing", ipdb_id=9999)
        rec = _make_record(ipdb_id=9999, title="Existing")
        plan = build_ipdb_plan([rec], ipdb_source, "fp-1")

        mm_entities = [e for e in plan.entities if e.model_class is MachineModel]
        assert len(mm_entities) == 0
        assert plan.records_matched == 1

    def test_matched_machine_has_scalar_claims(self, ipdb_source, _seed_mm_9999):
        mm = _seed_mm_9999
        rec = _make_record(
            ipdb_id=9999,
            title="Test Game",
            players=4,
            average_fun_rating=8.5,
            date_of_manufacture="1997-06-01T00:00:00",
            type="Solid State (SS)",
            type_short_name="SS",
        )
        plan = build_ipdb_plan([rec], ipdb_source, "fp-1")

        fields = _assertion_fields(plan, object_id=mm.pk)
        assert "ipdb_id" in fields
        assert "player_count" in fields
        assert "ipdb_rating" in fields
        assert "year" in fields
        assert "month" in fields
        # IPDB never asserts name claims — pindata is authoritative for names.
        assert "name" not in fields
        assert "slug" not in fields

    def test_existing_machine_skips_name_claim(self, ipdb_source):
        mm = make_machine_model(name="Existing", slug="existing", ipdb_id=9999)
        rec = _make_record(ipdb_id=9999, title="Existing")
        plan = build_ipdb_plan([rec], ipdb_source, "fp-1")

        fields = _assertion_fields(plan, object_id=mm.pk)
        assert "name" not in fields
        assert "slug" not in fields


# ---------------------------------------------------------------------------
# CorporateEntity reconciliation
# ---------------------------------------------------------------------------


class TestCorporateEntityReconciliation:
    @pytest.fixture(autouse=True)
    def _setup(self, ipdb_narrative_features, ipdb_locations, _seed_mm_9998_and_9999):
        """Locations + narrative features must exist."""

    def test_existing_ce_matched_by_ipdb_id(self, ipdb_source):
        """CE with matching ipdb_manufacturer_id → no new entity, claims asserted."""
        rec = _make_record(
            ipdb_id=9999,
            manufacturer="D. Gottlieb & Company, of Chicago, Illinois (1931-1977) [Trade Name: Gottlieb]",
            manufacturer_id=93,
        )
        plan = build_ipdb_plan([rec], ipdb_source, "fp-1")

        ce_entities = [e for e in plan.entities if e.model_class is CorporateEntity]
        assert len(ce_entities) == 0

        # Should have claims on the existing CE.
        ce = CorporateEntity.objects.get(ipdb_manufacturer_id=93)
        fields = _assertion_fields(plan, object_id=ce.pk)
        assert "ipdb_manufacturer_id" in fields
        assert "manufacturer" in fields
        assert "name" in fields

    def test_extra_data_claims_on_machine_model(self, ipdb_source, _seed_mm_9999):
        """Parsed manufacturer string produces informational extra_data claims."""
        rec = _make_record(
            ipdb_id=9999,
            manufacturer="Williams Electronic Games, of Chicago, Illinois (1985-1999) [Trade Name: Williams]",
            manufacturer_id=351,
        )
        plan = build_ipdb_plan([rec], ipdb_source, "fp-1")
        mm_pk = _seed_mm_9999.pk

        fields = _assertion_fields(plan, object_id=mm_pk)
        assert "ipdb.corporate_entity_name" in fields
        assert "ipdb.manufacturer_trade_name" in fields
        assert (
            _assertion_value(plan, "ipdb.corporate_entity_name", object_id=mm_pk)
            == "Williams Electronic Games"
        )
        assert (
            _assertion_value(plan, "ipdb.manufacturer_trade_name", object_id=mm_pk)
            == "Williams"
        )

    def test_duplicate_mfr_id_skips_second_ce_processing(self, ipdb_source):
        """Two records with same manufacturer_id → CE claims asserted only once."""
        rec1 = _make_record(
            ipdb_id=9998,
            manufacturer="D. Gottlieb & Company, of Chicago, Illinois (1931-1977) [Trade Name: Gottlieb]",
            manufacturer_id=93,
        )
        rec2 = _make_record(
            ipdb_id=9999,
            manufacturer="D. Gottlieb & Company, of Chicago, Illinois (1931-1977) [Trade Name: Gottlieb]",
            manufacturer_id=93,
        )
        plan = build_ipdb_plan([rec1, rec2], ipdb_source, "fp-1")

        ce = CorporateEntity.objects.get(ipdb_manufacturer_id=93)
        ce_claims = _assertions_for(plan, object_id=ce.pk)
        # Should only have one set of CE claims (from the first record).
        ipdb_id_claims = [
            c for c in ce_claims if c.field_name == "ipdb_manufacturer_id"
        ]
        assert len(ipdb_id_claims) == 1


# ---------------------------------------------------------------------------
# Person creation + credit claims
# ---------------------------------------------------------------------------


class TestPersonAndCredits:
    @pytest.fixture(autouse=True)
    def _setup(self, ipdb_narrative_features, credit_roles, _seed_mm_9999):
        """Credit roles + narrative features must exist."""

    def test_new_person_produces_entity_create(self, ipdb_source):
        rec = _make_record(ipdb_id=9999, design_by="Brian Eddy")
        plan = build_ipdb_plan([rec], ipdb_source, "fp-1")

        person_entities = [e for e in plan.entities if e.model_class is Person]
        assert len(person_entities) == 1
        assert person_entities[0].kwargs["name"] == "Brian Eddy"
        assert person_entities[0].kwargs["status"] == "active"

    def test_existing_person_no_entity_create(self, ipdb_source):
        Person.objects.create(name="Brian Eddy", slug="brian-eddy")
        rec = _make_record(ipdb_id=9999, design_by="Brian Eddy")
        plan = build_ipdb_plan([rec], ipdb_source, "fp-1")

        person_entities = [e for e in plan.entities if e.model_class is Person]
        assert len(person_entities) == 0

    def test_credit_claim_for_existing_person_is_concrete(self, ipdb_source):
        p = Person.objects.create(name="Brian Eddy", slug="brian-eddy")
        rec = _make_record(ipdb_id=9999, design_by="Brian Eddy")
        plan = build_ipdb_plan([rec], ipdb_source, "fp-1")

        credit_claims = [
            a for a in plan.assertions if a.field_name == "credit" and a.claim_key
        ]
        assert len(credit_claims) == 1
        assert credit_claims[0].value["person"] == p.pk
        assert credit_claims[0].value["exists"] is True

    def test_credit_claim_for_new_person_uses_identity_refs(
        self, ipdb_source, _seed_mm_9999
    ):
        rec = _make_record(ipdb_id=9999, design_by="Brian Eddy")
        plan = build_ipdb_plan([rec], ipdb_source, "fp-1")

        deferred = _deferred_assertions(plan, "credit", object_id=_seed_mm_9999.pk)
        assert len(deferred) == 1
        assert deferred[0].relationship_namespace == "credit"
        assert "person" in deferred[0].identity_refs
        assert "role" in deferred[0].identity

    def test_multi_credit_string(self, ipdb_source):
        rec = _make_record(ipdb_id=9999, design_by="Pat Lawlor, Larry DeMar")
        plan = build_ipdb_plan([rec], ipdb_source, "fp-1")

        person_entities = [e for e in plan.entities if e.model_class is Person]
        assert len(person_entities) == 2
        names = {e.kwargs["name"] for e in person_entities}
        assert names == {"Pat Lawlor", "Larry DeMar"}


# ---------------------------------------------------------------------------
# Theme creation + theme claims
# ---------------------------------------------------------------------------


class TestThemes:
    @pytest.fixture(autouse=True)
    def _setup(self, ipdb_narrative_features, _seed_mm_9999):
        pass

    def test_new_theme_produces_entity_create(self, ipdb_source):
        rec = _make_record(ipdb_id=9999, theme="Medieval")
        plan = build_ipdb_plan([rec], ipdb_source, "fp-1")

        theme_entities = [e for e in plan.entities if e.model_class is Theme]
        assert len(theme_entities) == 1
        assert theme_entities[0].kwargs["slug"] == "medieval"

    def test_existing_theme_no_entity_create(self, ipdb_source):
        Theme.objects.create(name="Medieval", slug="medieval")
        rec = _make_record(ipdb_id=9999, theme="Medieval")
        plan = build_ipdb_plan([rec], ipdb_source, "fp-1")

        theme_entities = [e for e in plan.entities if e.model_class is Theme]
        assert len(theme_entities) == 0

    def test_theme_claim_for_existing_theme_is_concrete(self, ipdb_source):
        t = Theme.objects.create(name="Medieval", slug="medieval")
        rec = _make_record(ipdb_id=9999, theme="Medieval")
        plan = build_ipdb_plan([rec], ipdb_source, "fp-1")

        theme_claims = [
            a for a in plan.assertions if a.field_name == "theme" and a.claim_key
        ]
        assert len(theme_claims) == 1
        assert theme_claims[0].value["theme"] == t.pk

    def test_theme_claim_for_new_theme_uses_identity_refs(
        self, ipdb_source, _seed_mm_9999
    ):
        rec = _make_record(ipdb_id=9999, theme="Medieval")
        plan = build_ipdb_plan([rec], ipdb_source, "fp-1")

        deferred = _deferred_assertions(plan, "theme", object_id=_seed_mm_9999.pk)
        assert len(deferred) == 1
        assert deferred[0].relationship_namespace == "theme"
        assert "theme" in deferred[0].identity_refs


# ---------------------------------------------------------------------------
# Gameplay features + reward types
# ---------------------------------------------------------------------------


class TestGameplayFeatures:
    @pytest.fixture(autouse=True)
    def _setup(self, ipdb_narrative_features, _seed_mm_9999):
        pass

    def test_gameplay_feature_claim_with_count(self, ipdb_source):
        GameplayFeature.objects.create(slug="flippers", name="Flippers")
        rec = _make_record(ipdb_id=9999, notable_features="Flippers (2)")
        plan = build_ipdb_plan([rec], ipdb_source, "fp-1")

        gf_claims = [a for a in plan.assertions if a.field_name == "gameplay_feature"]
        assert len(gf_claims) == 1
        assert gf_claims[0].value["count"] == 2

    def test_reward_type_claim(self, ipdb_source):
        RewardType.objects.create(slug="bumper", name="Bumper")
        rec = _make_record(ipdb_id=9999, notable_features="A bumper in the center")
        plan = build_ipdb_plan([rec], ipdb_source, "fp-1")

        rt_claims = [a for a in plan.assertions if a.field_name == "reward_type"]
        assert len(rt_claims) == 1


# ---------------------------------------------------------------------------
# Abbreviations
# ---------------------------------------------------------------------------


class TestAbbreviations:
    @pytest.fixture(autouse=True)
    def _setup(self, ipdb_narrative_features, _seed_mm_9999):
        pass

    def test_abbreviation_claims(self, ipdb_source):
        rec = _make_record(ipdb_id=9999, common_abbreviations="MM, MedMad")
        plan = build_ipdb_plan([rec], ipdb_source, "fp-1")

        abbr_claims = [a for a in plan.assertions if a.field_name == "abbreviation"]
        assert len(abbr_claims) == 2
        values = {a.value["value"] for a in abbr_claims}
        assert values == {"MM", "MedMad"}


# ---------------------------------------------------------------------------
# Error conditions
# ---------------------------------------------------------------------------


class TestErrors:
    @pytest.fixture(autouse=True)
    def _setup(self, ipdb_narrative_features, _seed_mm_9999):
        pass

    def test_unknown_mpu_raises(self, ipdb_source):
        from django.core.management.base import CommandError

        rec = _make_record(ipdb_id=9999, mpu="Unknown Board X-99")
        with pytest.raises(CommandError, match="Unknown MPU strings"):
            build_ipdb_plan([rec], ipdb_source, "fp-1")
