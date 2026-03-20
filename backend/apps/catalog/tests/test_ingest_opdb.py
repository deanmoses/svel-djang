"""Integration tests for the ingest_opdb command."""

import json
import tempfile

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.catalog.models import MachineModel
from apps.provenance.models import Claim, Source

FIXTURES = "apps/catalog/tests/fixtures"


@pytest.fixture
def _setup_ipdb_first(db):
    """Seed IPDB data so OPDB can match by ipdb_id."""
    call_command(
        "ingest_ipdb",
        ipdb=f"{FIXTURES}/ipdb_sample.json",
        export_dir=FIXTURES,
    )


@pytest.fixture
def _run_opdb(db, _setup_ipdb_first):
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
        assert "opdb.variant_features" in field_names

    def test_alias_features_claim(self):
        variant = MachineModel.objects.get(opdb_id="G1111-MTest1-AAlias")
        source = Source.objects.get(slug="opdb")
        claim = variant.claims.get(
            source=source, field_name="opdb.variant_features", is_active=True
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
        MachineModel.objects.create(name="Test Game", opdb_id="GOLD-M1")
        path = _opdb_dump(machines=[{"opdb_id": "GOLD-M1", "name": "Test Game"}])
        call_command("ingest_opdb", opdb=path)
        pm = MachineModel.objects.get(opdb_id="GOLD-M1")
        assert pm.name == "Test Game"

    def test_new_model_created_with_opdb_id(self):
        path = _opdb_dump(machines=[{"opdb_id": "GNEW-M1", "name": "Brand New Game"}])
        call_command("ingest_opdb", opdb=path)
        pm = MachineModel.objects.get(opdb_id="GNEW-M1")
        assert pm.name == "Brand New Game"


@pytest.mark.django_db
class TestOpdbAliasEdgeCases:
    def test_alias_skipped_when_parent_missing(self):
        path = _opdb_dump(
            aliases=[{"opdb_id": "GORPHAN-M1-AAlias", "name": "Orphan Alias"}]
        )
        call_command("ingest_opdb", opdb=path)
        assert not MachineModel.objects.filter(name="Orphan Alias").exists()

    def test_alias_created_when_parent_exists(self):
        path = _opdb_dump(
            machines=[{"opdb_id": "GNEW-M1", "name": "New Parent"}],
            aliases=[{"opdb_id": "GNEW-M1-AAlias", "name": "New Alias"}],
        )
        call_command("ingest_opdb", opdb=path)
        assert MachineModel.objects.filter(opdb_id="GNEW-M1").exists()
        assert MachineModel.objects.filter(opdb_id="GNEW-M1-AAlias").exists()

    def test_alias_has_no_variant_of_claim(self):
        """Even when parent exists, OPDB does not assert variant_of."""
        path = _opdb_dump(
            machines=[{"opdb_id": "GNEW-M1", "name": "New Parent"}],
            aliases=[{"opdb_id": "GNEW-M1-AAlias", "name": "New Alias"}],
        )
        call_command("ingest_opdb", opdb=path)
        alias = MachineModel.objects.get(opdb_id="GNEW-M1-AAlias")
        source = Source.objects.get(slug="opdb")
        assert not alias.claims.filter(
            source=source, field_name="variant_of", is_active=True
        ).exists()


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


@pytest.mark.django_db
class TestOpdbStaleRelationshipCleanup:
    """Stale variant_of and title claims from prior OPDB runs are deactivated."""

    def test_stale_variant_of_deactivated(self):
        """Pre-existing OPDB variant_of claims are cleaned up."""
        source, _ = Source.objects.get_or_create(
            slug="opdb",
            defaults={"name": "OPDB", "source_type": "database", "priority": 200},
        )
        pm = MachineModel.objects.create(
            name="Old Variant", opdb_id="GSTALE-MVar", slug="old-variant"
        )
        from django.contrib.contenttypes.models import ContentType

        ct_id = ContentType.objects.get_for_model(MachineModel).pk
        Claim.objects.create(
            content_type_id=ct_id,
            object_id=pm.pk,
            source=source,
            field_name="variant_of",
            value="some-parent",
            is_active=True,
        )
        assert Claim.objects.filter(
            source=source, field_name="variant_of", is_active=True
        ).exists()

        call_command("ingest_opdb", opdb=f"{FIXTURES}/opdb_sample.json")

        assert not Claim.objects.filter(
            source=source, field_name="variant_of", is_active=True
        ).exists()

    def test_stale_title_deactivated(self):
        """Pre-existing OPDB title claims are cleaned up."""
        source, _ = Source.objects.get_or_create(
            slug="opdb",
            defaults={"name": "OPDB", "source_type": "database", "priority": 200},
        )
        pm = MachineModel.objects.create(
            name="Old Titled", opdb_id="GSTALE-MTit", slug="old-titled"
        )
        from django.contrib.contenttypes.models import ContentType

        ct_id = ContentType.objects.get_for_model(MachineModel).pk
        Claim.objects.create(
            content_type_id=ct_id,
            object_id=pm.pk,
            source=source,
            field_name="title",
            value="some-title",
            is_active=True,
        )
        assert Claim.objects.filter(
            source=source, field_name="title", is_active=True
        ).exists()

        call_command("ingest_opdb", opdb=f"{FIXTURES}/opdb_sample.json")

        assert not Claim.objects.filter(
            source=source, field_name="title", is_active=True
        ).exists()
