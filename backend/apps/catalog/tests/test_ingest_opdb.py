"""Integration tests for the ingest_opdb command."""

import json
import tempfile

import pytest
from django.core.management import call_command

from apps.catalog.models import MachineModel, Title
from apps.provenance.models import Source

FIXTURES = "apps/catalog/tests/fixtures"


@pytest.fixture
def _setup_ipdb_first(db):
    """Seed IPDB data so OPDB can match by ipdb_id."""
    call_command("ingest_ipdb", ipdb=f"{FIXTURES}/ipdb_sample.json")


@pytest.fixture
def _run_opdb(db, _setup_ipdb_first):
    """Run ingest_opdb with groups after IPDB seed."""
    call_command(
        "ingest_opdb",
        opdb=f"{FIXTURES}/opdb_sample.json",
        groups=f"{FIXTURES}/opdb_groups_sample.json",
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("_run_opdb")
class TestIngestOpdb:
    def test_creates_source(self):
        source = Source.objects.get(slug="opdb")
        assert source.name == "OPDB"
        assert source.priority == 200

    def test_matches_by_ipdb_id(self):
        pm = MachineModel.objects.get(ipdb_id=4000)
        assert pm.opdb_id == "G1111-MTest1"

    def test_creates_new_for_unmatched(self):
        pm = MachineModel.objects.get(opdb_id="G2222-MTest2")
        assert pm.name == "Stern Exclusive Game"

    def test_opdb_claims_exist(self):
        pm = MachineModel.objects.get(opdb_id="G2222-MTest2")
        source = Source.objects.get(slug="opdb")
        claims = pm.claims.filter(source=source, is_active=True)
        field_names = set(claims.values_list("field_name", flat=True))
        assert "name" in field_names
        assert "display_type" in field_names
        assert "technology_generation" in field_names
        assert "year" in field_names

    def test_opdb_display_type_claim(self):
        pm = MachineModel.objects.get(opdb_id="G1111-MTest1")
        source = Source.objects.get(slug="opdb")
        display_claim = pm.claims.get(
            source=source, field_name="display_type", is_active=True
        )
        assert display_claim.value == "dot-matrix"

    def test_opdb_manufacturer_claim(self):
        pm = MachineModel.objects.get(opdb_id="G1111-MTest1")
        source = Source.objects.get(slug="opdb")
        mfr_claim = pm.claims.get(
            source=source, field_name="manufacturer", is_active=True
        )
        # OPDB resolves manufacturer name "Williams" to slug at ingest time.
        # IPDB runs first and auto-creates the Williams manufacturer.
        assert mfr_claim.value == "williams"

    def test_idempotent(self):
        initial_count = MachineModel.objects.count()
        call_command(
            "ingest_opdb",
            opdb=f"{FIXTURES}/opdb_sample.json",
            groups=f"{FIXTURES}/opdb_groups_sample.json",
        )
        assert MachineModel.objects.count() == initial_count


@pytest.mark.django_db
@pytest.mark.usefixtures("_run_opdb")
class TestIngestOpdbNewFields:
    def test_claims_common_name(self):
        pm = MachineModel.objects.get(opdb_id="G2222-MTest2")
        source = Source.objects.get(slug="opdb")
        claim = pm.claims.get(source=source, field_name="common_name", is_active=True)
        assert claim.value == "SEG"

    def test_no_common_name_when_null(self):
        pm = MachineModel.objects.get(opdb_id="G1111-MTest1")
        source = Source.objects.get(slug="opdb")
        assert not pm.claims.filter(
            source=source, field_name="common_name", is_active=True
        ).exists()

    def test_claims_shortname(self):
        pm = MachineModel.objects.get(opdb_id="G2222-MTest2")
        source = Source.objects.get(slug="opdb")
        claim = pm.claims.get(source=source, field_name="abbreviation", is_active=True)
        assert claim.value == {"value": "SEG", "exists": True}

    def test_claims_images(self):
        pm = MachineModel.objects.get(opdb_id="G1111-MTest1")
        source = Source.objects.get(slug="opdb")
        claim = pm.claims.get(source=source, field_name="images", is_active=True)
        assert len(claim.value) == 1
        assert claim.value[0]["type"] == "backglass"
        assert "large" in claim.value[0]["urls"]

    def test_no_images_when_empty(self):
        pm = MachineModel.objects.get(opdb_id="G2222-MTest2")
        source = Source.objects.get(slug="opdb")
        assert not pm.claims.filter(
            source=source, field_name="images", is_active=True
        ).exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("_run_opdb")
class TestIngestOpdbGroups:
    def test_creates_titles(self):
        assert Title.objects.count() == 3
        mm = Title.objects.get(opdb_id="G1111")
        assert mm.name == "Medieval Madness"
        assert list(mm.abbreviations.values_list("value", flat=True)) == ["MM"]

    def test_title_claim_on_machine(self):
        pm = MachineModel.objects.get(opdb_id="G1111-MTest1")
        source = Source.objects.get(slug="opdb")
        claim = pm.claims.get(source=source, field_name="title", is_active=True)
        assert claim.value == "G1111"

    def test_title_claim_on_unmatched_machine(self):
        pm = MachineModel.objects.get(opdb_id="G2222-MTest2")
        source = Source.objects.get(slug="opdb")
        claim = pm.claims.get(source=source, field_name="title", is_active=True)
        assert claim.value == "G2222"


@pytest.mark.django_db
@pytest.mark.usefixtures("_run_opdb")
class TestIngestOpdbAliases:
    def test_alias_created(self):
        variant = MachineModel.objects.get(opdb_id="G1111-MTest1-AAlias")
        assert variant.name == "Medieval Madness (LE)"

    def test_alias_linked_to_parent(self):
        parent = MachineModel.objects.get(opdb_id="G1111-MTest1")
        variant = MachineModel.objects.get(opdb_id="G1111-MTest1-AAlias")
        assert variant.variant_of == parent

    def test_alias_has_claims(self):
        variant = MachineModel.objects.get(opdb_id="G1111-MTest1-AAlias")
        source = Source.objects.get(slug="opdb")
        claims = variant.claims.filter(source=source, is_active=True)
        field_names = set(claims.values_list("field_name", flat=True))
        assert "name" in field_names
        assert "variant_features" in field_names
        assert "title" in field_names

    def test_alias_features_claim(self):
        variant = MachineModel.objects.get(opdb_id="G1111-MTest1-AAlias")
        source = Source.objects.get(slug="opdb")
        claim = variant.claims.get(
            source=source, field_name="variant_features", is_active=True
        )
        assert "Gold trim" in claim.value

    def test_total_model_count(self):
        # 4 from IPDB + 1 new OPDB machine (G2222) + 1 variant (G1111-AAlias)
        # + 2 from non-physical group (1 promoted + 1 variant) = 8
        assert MachineModel.objects.count() == 8


@pytest.mark.django_db
@pytest.mark.usefixtures("_run_opdb")
class TestIngestOpdbNonPhysical:
    def test_non_physical_machine_not_created(self):
        """The non-physical combo label should NOT become a MachineModel."""
        assert not MachineModel.objects.filter(opdb_id="G3333-MCombo").exists()

    def test_premium_alias_promoted(self):
        """The alias with 'Premium edition' feature should be a standalone model."""
        pm = MachineModel.objects.get(opdb_id="G3333-MCombo-APrem")
        assert pm.variant_of is None

    def test_le_alias_points_to_promoted(self):
        """The remaining alias should point to the promoted model."""
        promoted = MachineModel.objects.get(opdb_id="G3333-MCombo-APrem")
        variant = MachineModel.objects.get(opdb_id="G3333-MCombo-ALE")
        assert variant.variant_of == promoted

    def test_non_physical_idempotent(self):
        """Re-running ingest should not change the result."""
        initial_count = MachineModel.objects.count()
        call_command(
            "ingest_opdb",
            opdb=f"{FIXTURES}/opdb_sample.json",
            groups=f"{FIXTURES}/opdb_groups_sample.json",
        )
        assert MachineModel.objects.count() == initial_count
        # Verify relationships preserved.
        promoted = MachineModel.objects.get(opdb_id="G3333-MCombo-APrem")
        variant = MachineModel.objects.get(opdb_id="G3333-MCombo-ALE")
        assert promoted.variant_of is None
        assert variant.variant_of == promoted


@pytest.mark.django_db
class TestOpdbNonPhysicalHeuristics:
    def test_le_preferred_over_ce(self):
        """Limited Edition is promoted over Collector's Edition."""
        path = _opdb_dump(
            machines=[
                {
                    "opdb_id": "GTEST-MNP",
                    "name": "Test (LE/CE)",
                    "physical_machine": 0,
                }
            ],
            aliases=[
                {
                    "opdb_id": "GTEST-MNP-ACE",
                    "name": "Test (CE)",
                    "features": ["Collector's edition"],
                },
                {
                    "opdb_id": "GTEST-MNP-ALE",
                    "name": "Test (LE)",
                    "features": ["Limited edition"],
                },
            ],
        )
        call_command("ingest_opdb", opdb=path)
        le = MachineModel.objects.get(opdb_id="GTEST-MNP-ALE")
        ce = MachineModel.objects.get(opdb_id="GTEST-MNP-ACE")
        assert le.variant_of is None
        assert ce.variant_of == le

    def test_pe_preferred_over_ce(self):
        """Platinum Edition is promoted over Collector's Edition."""
        path = _opdb_dump(
            machines=[
                {
                    "opdb_id": "GTEST-MNP2",
                    "name": "Test (PE/CE)",
                    "physical_machine": 0,
                }
            ],
            aliases=[
                {
                    "opdb_id": "GTEST-MNP2-ACE",
                    "name": "Test (CE)",
                    "features": ["Collector's edition"],
                },
                {
                    "opdb_id": "GTEST-MNP2-APE",
                    "name": "Test (PE)",
                    "features": ["Platinum edition"],
                },
            ],
        )
        call_command("ingest_opdb", opdb=path)
        pe = MachineModel.objects.get(opdb_id="GTEST-MNP2-APE")
        ce = MachineModel.objects.get(opdb_id="GTEST-MNP2-ACE")
        assert pe.variant_of is None
        assert ce.variant_of == pe

    def test_ce_never_promoted_when_alternative_exists(self):
        """Collector's Edition is always a variant, even without known features."""
        path = _opdb_dump(
            machines=[
                {
                    "opdb_id": "GTEST-MNP3",
                    "name": "Test (Standard/CE)",
                    "physical_machine": 0,
                }
            ],
            aliases=[
                {
                    "opdb_id": "GTEST-MNP3-ACE",
                    "name": "Test (CE)",
                    "features": ["Collector's edition"],
                },
                {
                    "opdb_id": "GTEST-MNP3-AStd",
                    "name": "Test (Standard)",
                    "features": [],
                },
            ],
        )
        call_command("ingest_opdb", opdb=path)
        std = MachineModel.objects.get(opdb_id="GTEST-MNP3-AStd")
        ce = MachineModel.objects.get(opdb_id="GTEST-MNP3-ACE")
        assert std.variant_of is None
        assert ce.variant_of == std


@pytest.mark.django_db
class TestIngestOpdbChangelog:
    def test_changelog_moves_opdb_id(self, db):
        MachineModel.objects.create(name="Stale Machine", opdb_id="GSTALE-MOld1")
        call_command(
            "ingest_opdb",
            opdb=f"{FIXTURES}/opdb_sample.json",
            changelog=f"{FIXTURES}/opdb_changelog_sample.json",
        )
        pm = MachineModel.objects.get(name="Stale Machine")
        assert pm.opdb_id == "GFRESH-MNew1"

    def test_changelog_does_not_delete(self, db):
        MachineModel.objects.create(name="Dead Machine", opdb_id="GDEAD-MDel1")
        call_command(
            "ingest_opdb",
            opdb=f"{FIXTURES}/opdb_sample.json",
            changelog=f"{FIXTURES}/opdb_changelog_sample.json",
        )
        assert MachineModel.objects.filter(name="Dead Machine").exists()

    def test_changelog_no_overwrite_existing(self, db):
        MachineModel.objects.create(name="Stale Machine", opdb_id="GSTALE-MOld1")
        MachineModel.objects.create(name="New Machine", opdb_id="GFRESH-MNew1")
        call_command(
            "ingest_opdb",
            opdb=f"{FIXTURES}/opdb_sample.json",
            changelog=f"{FIXTURES}/opdb_changelog_sample.json",
        )
        stale = MachineModel.objects.get(name="Stale Machine")
        assert stale.opdb_id == "GSTALE-MOld1"


def _opdb_dump(machines=None, aliases=None):
    data = []
    for m in machines or []:
        m.setdefault("is_machine", True)
        m.setdefault("physical_machine", 1)
        data.append(m)
    for a in aliases or []:
        a.setdefault("is_alias", True)
        data.append(a)
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return f.name


@pytest.mark.django_db
class TestOpdbSkipsMissingOpdbId:
    def test_machine_without_opdb_id_skipped(self):
        path = _opdb_dump(machines=[{"name": "No ID Game"}])
        call_command("ingest_opdb", opdb=path)
        assert not MachineModel.objects.filter(name="No ID Game").exists()

    def test_alias_without_opdb_id_skipped(self):
        path = _opdb_dump(aliases=[{"name": "No ID Alias"}])
        call_command("ingest_opdb", opdb=path)
        assert not MachineModel.objects.filter(name="No ID Alias").exists()


@pytest.mark.django_db
class TestOpdbConflictBranches:
    def test_matched_model_keeps_existing_opdb_id(self):
        MachineModel.objects.create(name="Test Game", ipdb_id=9999, opdb_id="GOLD-M1")
        path = _opdb_dump(
            machines=[{"opdb_id": "GNEW-M1", "ipdb_id": 9999, "name": "Test Game"}]
        )
        call_command("ingest_opdb", opdb=path)
        pm = MachineModel.objects.get(ipdb_id=9999)
        assert pm.opdb_id == "GOLD-M1"

    def test_opdb_id_set_when_no_conflict(self):
        MachineModel.objects.create(name="Test Game", ipdb_id=9999)
        path = _opdb_dump(
            machines=[{"opdb_id": "GNEW-M1", "ipdb_id": 9999, "name": "Test Game"}]
        )
        call_command("ingest_opdb", opdb=path)
        pm = MachineModel.objects.get(ipdb_id=9999)
        assert pm.opdb_id == "GNEW-M1"

    def test_opdb_id_not_set_when_already_owned(self):
        MachineModel.objects.create(name="Owner", opdb_id="GNEW-M1")
        MachineModel.objects.create(name="Test Game", ipdb_id=9999)
        path = _opdb_dump(
            machines=[{"opdb_id": "GNEW-M1", "ipdb_id": 9999, "name": "Test Game"}]
        )
        call_command("ingest_opdb", opdb=path)
        pm = MachineModel.objects.get(ipdb_id=9999)
        assert pm.opdb_id is None


@pytest.mark.django_db
class TestOpdbAliasEdgeCases:
    def test_alias_skipped_when_parent_missing(self):
        path = _opdb_dump(
            aliases=[{"opdb_id": "GORPHAN-M1-AAlias", "name": "Orphan Alias"}]
        )
        call_command("ingest_opdb", opdb=path)
        assert not MachineModel.objects.filter(name="Orphan Alias").exists()

    def test_alias_links_to_parent_from_same_run(self):
        path = _opdb_dump(
            machines=[{"opdb_id": "GNEW-M1", "name": "New Parent"}],
            aliases=[{"opdb_id": "GNEW-M1-AAlias", "name": "New Alias"}],
        )
        call_command("ingest_opdb", opdb=path)
        parent = MachineModel.objects.get(opdb_id="GNEW-M1")
        alias = MachineModel.objects.get(opdb_id="GNEW-M1-AAlias")
        assert alias.variant_of == parent
