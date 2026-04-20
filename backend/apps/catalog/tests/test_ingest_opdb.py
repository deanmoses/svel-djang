"""Integration tests for the ingest_opdb command."""

import json
import tempfile

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.catalog.models import MachineModel, System, SystemMpuString
from apps.provenance.models import Claim, Source
from apps.catalog.tests.conftest import make_machine_model

FIXTURES = "apps/catalog/tests/fixtures"


@pytest.fixture
def _mpu_strings(db):
    """Create SystemMpuString records matching the fixture's system.json."""
    system = System.objects.create(slug="wpc-95", name="WPC-95")
    SystemMpuString.objects.create(system=system, value="Williams WPC-95")


@pytest.fixture
def _ipdb_sample_models(db):
    """Pre-seed MachineModels for ipdb_sample.json."""
    make_machine_model(name="Medieval Madness", slug="medieval-madness", ipdb_id=4000)
    make_machine_model(name="A-B-C Bowler", slug="a-b-c-bowler", ipdb_id=20)
    make_machine_model(name="The Addams Family", slug="the-addams-family", ipdb_id=61)
    make_machine_model(name="Baffle Ball", slug="baffle-ball", ipdb_id=100)


@pytest.fixture
def _opdb_sample_models(db, _ipdb_sample_models):
    """Pre-seed OPDB machines/aliases from opdb_sample.json.

    The adapter now requires every OPDB record to match an existing
    MachineModel — pindata is the authoritative superset. This fixture
    mirrors that: pre-seed the OPDB-only records (G2222) and the alias
    of the IPDB-matched machine (G1111-MTest1-AAlias). G3333-MCombo is
    non-physical and its aliases have no resolvable parent, so both are
    skipped by the adapter filter/reconciliation — no pre-seed needed.
    """
    # G1111-MTest1 is matched via ipdb_id=4000 by the existing "Medieval Madness" MM.
    # Backfill its opdb_id here to simulate pindata having both IDs.
    mm = MachineModel.objects.get(ipdb_id=4000)
    mm.opdb_id = "G1111-MTest1"
    mm.save()

    make_machine_model(
        name="Stern Exclusive Game",
        slug="stern-exclusive-game",
        opdb_id="G2222-MTest2",
    )
    make_machine_model(
        name="Medieval Madness (LE)",
        slug="medieval-madness-le",
        opdb_id="G1111-MTest1-AAlias",
    )


@pytest.fixture
def _setup_ipdb_first(
    db,
    _mpu_strings,
    ingest_taxonomy,
    ipdb_locations,
    ipdb_narrative_features,
    credit_roles,
    _ipdb_sample_models,
):
    """Seed IPDB data so OPDB can match by ipdb_id."""
    call_command(
        "ingest_ipdb",
        ipdb=f"{FIXTURES}/ipdb_sample.json",
    )


@pytest.fixture
def _run_opdb(db, _setup_ipdb_first, _opdb_sample_models):
    """Run ingest_opdb after IPDB seed."""
    call_command(
        "ingest_opdb",
        opdb=f"{FIXTURES}/opdb_sample.json",
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

    def test_no_manufacturer_claims(self):
        """OPDB no longer asserts manufacturer claims — MachineModel uses corporate_entity."""
        source = Source.objects.get(slug="opdb")
        assert not Claim.objects.filter(
            source=source, field_name="manufacturer", is_active=True
        ).exists()

    def test_no_title_claims(self):
        """OPDB no longer asserts title claims — Pinbase owns title grouping."""
        source = Source.objects.get(slug="opdb")
        assert not Claim.objects.filter(
            source=source, field_name="title", is_active=True
        ).exists()

    def test_no_variant_of_claims(self):
        """OPDB no longer asserts variant_of claims — Pinbase owns relationships."""
        source = Source.objects.get(slug="opdb")
        assert not Claim.objects.filter(
            source=source, field_name="variant_of", is_active=True
        ).exists()

    def test_idempotent(self):
        initial_count = MachineModel.objects.count()
        call_command(
            "ingest_opdb",
            opdb=f"{FIXTURES}/opdb_sample.json",
        )
        assert MachineModel.objects.count() == initial_count


@pytest.mark.django_db
@pytest.mark.usefixtures("_run_opdb")
class TestIngestOpdbNewFields:
    def test_claims_common_name(self):
        pm = MachineModel.objects.get(opdb_id="G2222-MTest2")
        source = Source.objects.get(slug="opdb")
        claim = pm.claims.get(
            source=source, field_name="opdb.common_name", is_active=True
        )
        assert claim.value == "SEG"

    def test_no_common_name_when_null(self):
        pm = MachineModel.objects.get(opdb_id="G1111-MTest1")
        source = Source.objects.get(slug="opdb")
        assert not pm.claims.filter(
            source=source, field_name="opdb.common_name", is_active=True
        ).exists()

    def test_claims_shortname(self):
        pm = MachineModel.objects.get(opdb_id="G2222-MTest2")
        source = Source.objects.get(slug="opdb")
        claim = pm.claims.get(source=source, field_name="abbreviation", is_active=True)
        assert claim.value == {"value": "SEG", "exists": True}

    def test_claims_images(self):
        pm = MachineModel.objects.get(opdb_id="G1111-MTest1")
        source = Source.objects.get(slug="opdb")
        claim = pm.claims.get(source=source, field_name="opdb.images", is_active=True)
        assert len(claim.value) == 1
        assert claim.value[0]["type"] == "backglass"
        assert "large" in claim.value[0]["urls"]

    def test_no_images_when_empty(self):
        pm = MachineModel.objects.get(opdb_id="G2222-MTest2")
        source = Source.objects.get(slug="opdb")
        assert not pm.claims.filter(
            source=source, field_name="opdb.images", is_active=True
        ).exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("_run_opdb")
class TestIngestOpdbAliases:
    def test_alias_created(self):
        variant = MachineModel.objects.get(opdb_id="G1111-MTest1-AAlias")
        assert variant.name == "Medieval Madness (LE)"

    def test_alias_no_variant_of(self):
        """OPDB aliases are flat models — no variant_of relationship."""
        variant = MachineModel.objects.get(opdb_id="G1111-MTest1-AAlias")
        source = Source.objects.get(slug="opdb")
        assert not variant.claims.filter(
            source=source, field_name="variant_of", is_active=True
        ).exists()

    def test_alias_has_scalar_claims(self):
        variant = MachineModel.objects.get(opdb_id="G1111-MTest1-AAlias")
        source = Source.objects.get(slug="opdb")
        claims = variant.claims.filter(source=source, is_active=True)
        field_names = set(claims.values_list("field_name", flat=True))
        assert "name" in field_names
        assert "opdb.features" in field_names

    def test_alias_features_claim(self):
        variant = MachineModel.objects.get(opdb_id="G1111-MTest1-AAlias")
        source = Source.objects.get(slug="opdb")
        claim = variant.claims.get(
            source=source, field_name="opdb.features", is_active=True
        )
        assert "Gold trim" in claim.value

    def test_non_physical_aliases_skipped(self):
        """Aliases whose parent is non-physical are skipped (parent not in lookup)."""
        assert not MachineModel.objects.filter(opdb_id="G3333-MCombo").exists()
        assert not MachineModel.objects.filter(opdb_id="G3333-MCombo-APrem").exists()
        assert not MachineModel.objects.filter(opdb_id="G3333-MCombo-ALE").exists()

    def test_total_model_count(self):
        # 4 from IPDB + 1 new OPDB machine (G2222) + 1 alias (G1111-AAlias) = 6
        # Non-physical parent (G3333-MCombo) skipped → its aliases also skipped.
        assert MachineModel.objects.count() == 6


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
class TestOpdbAbortsMissingOpdbId:
    def test_machine_without_opdb_id_aborts(self):
        path = _opdb_dump(machines=[{"name": "No ID Game"}])
        with pytest.raises(CommandError, match="failed to parse"):
            call_command("ingest_opdb", opdb=path)

    def test_alias_without_opdb_id_aborts(self):
        path = _opdb_dump(aliases=[{"name": "No ID Alias"}])
        with pytest.raises(CommandError, match="failed to parse"):
            call_command("ingest_opdb", opdb=path)


@pytest.mark.django_db
class TestOpdbConflictBranches:
    def test_matched_model_keeps_existing_opdb_id(self):
        """Models matched by opdb_id keep their existing opdb_id."""
        make_machine_model(name="Test Game", slug="test-game", opdb_id="GOLD-M1")
        path = _opdb_dump(machines=[{"opdb_id": "GOLD-M1", "name": "Test Game"}])
        call_command("ingest_opdb", opdb=path)
        pm = MachineModel.objects.get(opdb_id="GOLD-M1")
        assert pm.name == "Test Game"

    def test_unmatched_opdb_record_aborts(self):
        """OPDB records with no matching pindata MachineModel abort ingest."""
        path = _opdb_dump(machines=[{"opdb_id": "GNEW-M1", "name": "Brand New Game"}])
        with pytest.raises(CommandError, match="do not match any existing"):
            call_command("ingest_opdb", opdb=path)


@pytest.mark.django_db
class TestOpdbAliasEdgeCases:
    def test_alias_skipped_when_parent_missing(self):
        path = _opdb_dump(
            aliases=[{"opdb_id": "GORPHAN-M1-AAlias", "name": "Orphan Alias"}]
        )
        call_command("ingest_opdb", opdb=path)
        assert not MachineModel.objects.filter(name="Orphan Alias").exists()

    def test_unmatched_alias_with_parent_in_same_batch_aborts(self):
        """Even with parent in batch, an unmatched alias aborts ingest."""
        path = _opdb_dump(
            machines=[{"opdb_id": "GNEW-M1", "name": "New Parent"}],
            aliases=[{"opdb_id": "GNEW-M1-AAlias", "name": "New Alias"}],
        )
        with pytest.raises(CommandError, match="do not match any existing"):
            call_command("ingest_opdb", opdb=path)


@pytest.mark.django_db
@pytest.mark.usefixtures("_run_opdb")
class TestOpdbFKClaimGuards:
    """Structural guard: every FK set on a model must be backed by an OPDB claim."""

    # FK fields that _collect_claims emits for OPDB records.
    OPDB_FK_FIELDS = [
        "technology_generation",
        "display_type",
    ]

    @pytest.mark.parametrize("fk_field", OPDB_FK_FIELDS)
    def test_fk_field_has_opdb_claim(self, fk_field):
        """OPDB-authoritative models with an FK set must have a backing claim."""
        source = Source.objects.get(slug="opdb")
        # Scope to models that have an opdb_id (OPDB-authoritative).
        fk_attr = f"{fk_field}_id"
        models_with_fk = MachineModel.objects.filter(
            opdb_id__isnull=False,
            **{f"{fk_attr}__isnull": False},
        )
        for pm in models_with_fk:
            assert pm.claims.filter(
                source=source, field_name=fk_field, is_active=True
            ).exists(), (
                f"{pm.slug} (opdb_id={pm.opdb_id}) has {fk_field} set "
                f"but no active OPDB claim"
            )
