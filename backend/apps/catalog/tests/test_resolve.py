import pytest
from django.utils import timezone

from apps.catalog.claims import build_relationship_claim
from apps.catalog.models import (
    Title,
    MachineModel,
    System,
    TechnologyGeneration,
    Theme,
)
from apps.catalog.resolve import resolve_all, resolve_model, resolve_themes
from apps.provenance.models import Claim, Source


@pytest.fixture
def ipdb(db):
    return Source.objects.create(name="IPDB", source_type="database", priority=10)


@pytest.fixture
def opdb(db):
    return Source.objects.create(name="OPDB", source_type="database", priority=20)


@pytest.fixture
def editorial(db):
    return Source.objects.create(
        name="The Flip Editorial", source_type="editorial", priority=100
    )


@pytest.fixture
def pm(db):
    return MachineModel.objects.create(name="Placeholder")


class TestResolveModel:
    def test_basic_resolution(self, pm, ipdb):
        ss = TechnologyGeneration.objects.create(name="Solid State", slug="solid-state")
        Claim.objects.assert_claim(pm, "name", "Medieval Madness", source=ipdb)
        Claim.objects.assert_claim(pm, "year", 1997, source=ipdb)
        Claim.objects.assert_claim(
            pm, "technology_generation", "solid-state", source=ipdb
        )

        resolved = resolve_model(pm)
        assert resolved.name == "Medieval Madness"
        assert resolved.year == 1997
        assert resolved.technology_generation == ss

    def test_higher_priority_wins(self, pm, ipdb, editorial):
        Claim.objects.assert_claim(pm, "year", 1996, source=ipdb)
        Claim.objects.assert_claim(pm, "year", 1997, source=editorial)

        resolved = resolve_model(pm)
        assert resolved.year == 1997  # editorial has higher priority

    def test_same_priority_latest_wins(self, pm, ipdb, opdb):
        Claim.objects.assert_claim(pm, "name", "IPDB Name", source=ipdb)
        Claim.objects.assert_claim(pm, "name", "OPDB Name", source=opdb)

        resolved = resolve_model(pm)
        assert resolved.name == "OPDB Name"

    def test_extra_data_catchall(self, pm, ipdb):
        Claim.objects.assert_claim(pm, "model_number", "20021", source=ipdb)

        resolved = resolve_model(pm)
        assert resolved.extra_data["model_number"] == "20021"

    def test_abbreviation_relationship_claim(self, pm, ipdb):
        from apps.catalog.claims import build_relationship_claim

        claim_key, value = build_relationship_claim("abbreviation", {"value": "MM"})
        Claim.objects.assert_claim(
            pm, "abbreviation", value, source=ipdb, claim_key=claim_key
        )

        resolved = resolve_model(pm)
        assert list(resolved.abbreviations.values_list("value", flat=True)) == ["MM"]

    def test_int_coercion(self, pm, ipdb):
        Claim.objects.assert_claim(pm, "year", "1997", source=ipdb)
        Claim.objects.assert_claim(pm, "player_count", "4", source=ipdb)

        resolved = resolve_model(pm)
        assert resolved.year == 1997
        assert resolved.player_count == 4

    def test_decimal_coercion(self, pm, ipdb):
        from decimal import Decimal

        Claim.objects.assert_claim(pm, "ipdb_rating", "8.75", source=ipdb)

        resolved = resolve_model(pm)
        assert resolved.ipdb_rating == Decimal("8.75")

    def test_empty_string_coercion(self, pm, ipdb):
        Claim.objects.assert_claim(pm, "year", "", source=ipdb)
        resolved = resolve_model(pm)
        assert resolved.year is None

    def test_invalid_int_coercion(self, pm, ipdb):
        Claim.objects.assert_claim(pm, "year", "not-a-number", source=ipdb)
        resolved = resolve_model(pm)
        assert resolved.year is None

    def test_stale_values_cleared_on_re_resolve(self, pm, ipdb):
        Claim.objects.assert_claim(pm, "year", 1997, source=ipdb)
        Claim.objects.assert_claim(pm, "player_count", 4, source=ipdb)
        resolve_model(pm)
        assert pm.year == 1997
        assert pm.player_count == 4

        pm.claims.filter(is_active=True).update(is_active=False)
        resolve_model(pm)
        pm.refresh_from_db()
        assert pm.year is None
        assert pm.player_count is None
        assert pm.extra_data == {}

    def test_mixed_fields_and_extra_data(self, pm, ipdb, editorial):
        Claim.objects.assert_claim(pm, "name", "The Addams Family", source=ipdb)
        Claim.objects.assert_claim(pm, "year", 1992, source=ipdb)
        Claim.objects.assert_claim(pm, "toys", "Thing hand, bookcase", source=ipdb)
        Claim.objects.assert_claim(pm, "fun_facts", "A seminal game.", source=editorial)

        resolved = resolve_model(pm)
        assert resolved.name == "The Addams Family"
        assert resolved.year == 1992
        assert resolved.extra_data["toys"] == "Thing hand, bookcase"
        assert resolved.extra_data["fun_facts"] == "A seminal game."


@pytest.mark.django_db
class TestResolveAll:
    def test_basic(self):
        ipdb = Source.objects.create(
            name="IPDB", slug="ipdb", source_type="database", priority=10
        )
        ss = TechnologyGeneration.objects.create(name="Solid State", slug="solid-state")
        pm1 = MachineModel.objects.create(name="P1", slug="p1")
        pm2 = MachineModel.objects.create(name="P2", slug="p2")
        pm3 = MachineModel.objects.create(name="P3", slug="p3")

        Claim.objects.assert_claim(pm1, "name", "Medieval Madness", source=ipdb)
        Claim.objects.assert_claim(pm1, "year", 1997, source=ipdb)
        Claim.objects.assert_claim(pm2, "name", "The Addams Family", source=ipdb)
        Claim.objects.assert_claim(pm3, "name", "Twilight Zone", source=ipdb)
        Claim.objects.assert_claim(
            pm3, "technology_generation", "solid-state", source=ipdb
        )

        before = timezone.now()
        count = resolve_all()
        assert count == 3

        pm1.refresh_from_db()
        pm2.refresh_from_db()
        pm3.refresh_from_db()
        assert pm1.name == "Medieval Madness"
        assert pm1.year == 1997
        assert pm2.name == "The Addams Family"
        assert pm3.name == "Twilight Zone"
        assert pm3.technology_generation == ss

        assert pm1.updated_at >= before
        assert pm2.updated_at >= before
        assert pm3.updated_at >= before

    def test_matches_resolve_model(self):
        ipdb = Source.objects.create(
            name="IPDB", slug="ipdb", source_type="database", priority=10
        )
        opdb = Source.objects.create(
            name="OPDB", slug="opdb", source_type="database", priority=20
        )
        Title.objects.create(opdb_id="G1111", name="Medieval Madness", slug="mm")
        TechnologyGeneration.objects.create(name="Solid State", slug="solid-state")

        pm_bulk = MachineModel.objects.create(name="P1", slug="p1")
        pm_single = MachineModel.objects.create(name="P2", slug="p2")

        from apps.catalog.claims import build_relationship_claim

        abbr_key, abbr_val = build_relationship_claim("abbreviation", {"value": "MM"})

        for pm in (pm_bulk, pm_single):
            Claim.objects.assert_claim(pm, "name", "Medieval Madness", source=ipdb)
            Claim.objects.assert_claim(pm, "year", 1997, source=opdb)
            Claim.objects.assert_claim(pm, "title", "G1111", source=opdb)
            Claim.objects.assert_claim(
                pm, "abbreviation", abbr_val, source=ipdb, claim_key=abbr_key
            )
            Claim.objects.assert_claim(
                pm, "technology_generation", "solid-state", source=ipdb
            )

        resolve_model(pm_single)
        pm_single.refresh_from_db()

        resolve_all()
        pm_bulk.refresh_from_db()

        assert pm_bulk.name == pm_single.name
        assert pm_bulk.year == pm_single.year
        assert pm_bulk.title_id == pm_single.title_id
        assert pm_bulk.technology_generation_id == pm_single.technology_generation_id
        assert pm_bulk.extra_data == pm_single.extra_data

    def test_opdb_conflict(self):
        ipdb = Source.objects.create(
            name="IPDB", slug="ipdb", source_type="database", priority=10
        )
        pm_a = MachineModel.objects.create(name="Alpha", slug="alpha")
        pm_b = MachineModel.objects.create(name="Beta", slug="beta")

        Claim.objects.assert_claim(pm_a, "opdb_id", "GCONFLICT-M1", source=ipdb)
        Claim.objects.assert_claim(pm_b, "opdb_id", "GCONFLICT-M1", source=ipdb)

        resolve_all()
        pm_a.refresh_from_db()
        pm_b.refresh_from_db()

        assert pm_a.opdb_id == "GCONFLICT-M1"
        assert pm_b.opdb_id is None

    def test_stale_values_cleared(self):
        ipdb = Source.objects.create(
            name="IPDB", slug="ipdb", source_type="database", priority=10
        )
        pm = MachineModel.objects.create(name="P1", slug="p1")

        Claim.objects.assert_claim(pm, "year", 1997, source=ipdb)
        Claim.objects.assert_claim(pm, "player_count", 4, source=ipdb)
        resolve_all()
        pm.refresh_from_db()
        assert pm.year == 1997
        assert pm.player_count == 4

        pm.claims.filter(is_active=True).update(is_active=False)
        resolve_all()
        pm.refresh_from_db()
        assert pm.year is None
        assert pm.player_count is None
        assert pm.extra_data == {}

    def test_query_count(self, django_assert_max_num_queries):
        ipdb = Source.objects.create(
            name="IPDB", slug="ipdb", source_type="database", priority=10
        )
        for i in range(5):
            pm = MachineModel.objects.create(name=f"Model {i}", slug=f"model-{i}")
            Claim.objects.assert_claim(pm, "name", f"Resolved {i}", source=ipdb)
            Claim.objects.assert_claim(pm, "year", 2000 + i, source=ipdb)

        with django_assert_max_num_queries(62):
            resolve_all()


@pytest.mark.django_db
class TestResolveThemes:
    def test_basic_theme_resolution(self):
        ipdb = Source.objects.create(
            name="IPDB", slug="ipdb", source_type="database", priority=10
        )
        pm = MachineModel.objects.create(name="P1", slug="p1")
        Theme.objects.create(name="Horror", slug="horror")
        Theme.objects.create(name="Licensed", slug="licensed")

        for slug in ("horror", "licensed"):
            claim_key, value = build_relationship_claim("theme", {"theme_slug": slug})
            Claim.objects.assert_claim(
                pm, "theme", value, source=ipdb, claim_key=claim_key
            )

        resolve_themes(pm)
        assert set(pm.themes.values_list("slug", flat=True)) == {
            "horror",
            "licensed",
        }

    def test_theme_exists_false_dispute(self):
        ipdb = Source.objects.create(
            name="IPDB", slug="ipdb", source_type="database", priority=10
        )
        editorial = Source.objects.create(
            name="Editorial", source_type="editorial", priority=100
        )
        pm = MachineModel.objects.create(name="P1", slug="p1")
        Theme.objects.create(name="Horror", slug="horror")

        # IPDB says horror, editorial disputes it.
        claim_key, value = build_relationship_claim("theme", {"theme_slug": "horror"})
        Claim.objects.assert_claim(pm, "theme", value, source=ipdb, claim_key=claim_key)
        _, dispute_value = build_relationship_claim(
            "theme", {"theme_slug": "horror"}, exists=False
        )
        Claim.objects.assert_claim(
            pm, "theme", dispute_value, source=editorial, claim_key=claim_key
        )

        resolve_themes(pm)
        assert pm.themes.count() == 0

    def test_stale_themes_cleared(self):
        ipdb = Source.objects.create(
            name="IPDB", slug="ipdb", source_type="database", priority=10
        )
        pm = MachineModel.objects.create(name="P1", slug="p1")
        Theme.objects.create(name="Horror", slug="horror")

        claim_key, value = build_relationship_claim("theme", {"theme_slug": "horror"})
        Claim.objects.assert_claim(pm, "theme", value, source=ipdb, claim_key=claim_key)
        resolve_themes(pm)
        assert pm.themes.count() == 1

        # Deactivate claim, re-resolve — themes should be empty.
        pm.claims.filter(is_active=True).update(is_active=False)
        resolve_themes(pm)
        assert pm.themes.count() == 0

    def test_bulk_theme_resolution(self):
        ipdb = Source.objects.create(
            name="IPDB", slug="ipdb", source_type="database", priority=10
        )
        pm1 = MachineModel.objects.create(name="P1", slug="p1")
        pm2 = MachineModel.objects.create(name="P2", slug="p2")
        Theme.objects.create(name="Sports", slug="sports")
        Theme.objects.create(name="Baseball", slug="baseball")

        for pm, slugs in [(pm1, ["sports", "baseball"]), (pm2, ["sports"])]:
            for slug in slugs:
                claim_key, value = build_relationship_claim(
                    "theme", {"theme_slug": slug}
                )
                Claim.objects.assert_claim(
                    pm, "theme", value, source=ipdb, claim_key=claim_key
                )

        resolve_all()
        assert set(pm1.themes.values_list("slug", flat=True)) == {
            "sports",
            "baseball",
        }
        assert set(pm2.themes.values_list("slug", flat=True)) == {"sports"}


@pytest.mark.django_db
class TestResolveSystem:
    def test_system_claim_sets_fk(self):
        ipdb = Source.objects.create(
            name="IPDB", slug="ipdb", source_type="database", priority=10
        )
        system = System.objects.create(name="Williams WPC-95", slug="wpc-95")
        pm = MachineModel.objects.create(
            name="Medieval Madness", slug="medieval-madness"
        )
        Claim.objects.assert_claim(pm, "system", "wpc-95", source=ipdb)

        resolve_model(pm)
        pm.refresh_from_db()
        assert pm.system == system

    def test_unknown_system_slug_logs_warning_no_fk(self):
        ipdb = Source.objects.create(
            name="IPDB", slug="ipdb", source_type="database", priority=10
        )
        pm = MachineModel.objects.create(name="Mystery Machine", slug="mystery-machine")
        Claim.objects.assert_claim(pm, "system", "nonexistent-slug", source=ipdb)

        resolve_model(pm)
        pm.refresh_from_db()
        assert pm.system is None

    def test_stale_system_cleared(self):
        system = System.objects.create(name="Williams WPC-95", slug="wpc-95")
        pm = MachineModel.objects.create(
            name="Medieval Madness", slug="medieval-madness", system=system
        )
        # No system claim — system should be cleared after resolve.
        resolve_model(pm)
        pm.refresh_from_db()
        assert pm.system is None
