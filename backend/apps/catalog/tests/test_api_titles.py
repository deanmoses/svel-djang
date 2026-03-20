import pytest
from django.core.cache import cache

from apps.catalog.models import (
    Credit,
    CreditRole,
    DisplayType,
    Franchise,
    MachineModel,
    Person,
    Series,
    System,
    Theme,
    Title,
)

from .conftest import SAMPLE_IMAGES


class TestTitlesAPI:
    @pytest.fixture
    def title(self, db):
        return Title.objects.create(name="Medieval Madness", opdb_id="G5pe4")

    @pytest.fixture
    def title_with_machines(self, title, williams_entity):
        MachineModel.objects.create(
            name="Medieval Madness",
            corporate_entity=williams_entity,
            year=1997,
            title=title,
            extra_data={"opdb.images": SAMPLE_IMAGES},
        )
        MachineModel.objects.create(
            name="Medieval Madness (Remake)",
            corporate_entity=williams_entity,
            year=2015,
            title=title,
        )
        return title

    def test_list_titles(self, client, title_with_machines):
        resp = client.get("/api/titles/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        item = data["items"][0]
        assert item["name"] == "Medieval Madness"
        assert item["abbreviations"] == []
        assert item["machine_count"] == 2

    def test_list_titles_thumbnail(self, client, title_with_machines):
        resp = client.get("/api/titles/")
        data = resp.json()
        assert data["items"][0]["thumbnail_url"] == "https://img.opdb.org/md.jpg"

    def test_list_titles_empty_title(self, client, title):
        resp = client.get("/api/titles/")
        data = resp.json()
        assert data["items"][0]["machine_count"] == 0
        assert data["items"][0]["thumbnail_url"] is None

    def test_get_title_detail(self, client, title_with_machines):
        resp = client.get(f"/api/titles/{title_with_machines.slug}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Medieval Madness"
        assert len(data["machines"]) == 2

    def test_get_title_detail_excludes_variants(self, client, title_with_machines):
        parent = MachineModel.objects.get(name="Medieval Madness")
        MachineModel.objects.create(
            name="Medieval Madness (LE)",
            title=title_with_machines,
            variant_of=parent,
        )
        resp = client.get(f"/api/titles/{title_with_machines.slug}")
        data = resp.json()
        assert len(data["machines"]) == 2
        names = [m["name"] for m in data["machines"]]
        assert "Medieval Madness (LE)" not in names

    def test_machine_count_excludes_variants(self, client, title_with_machines):
        parent = MachineModel.objects.get(name="Medieval Madness")
        MachineModel.objects.create(
            name="Medieval Madness (LE)",
            title=title_with_machines,
            variant_of=parent,
        )
        resp = client.get("/api/titles/")
        data = resp.json()
        assert data["items"][0]["machine_count"] == 2

    def test_get_title_404(self, client, db):
        resp = client.get("/api/titles/nonexistent")
        assert resp.status_code == 404


class TestTitlesAllFacets:
    """Test that /api/titles/all/ returns enriched facet data."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        cache.clear()
        yield
        cache.clear()

    @pytest.fixture
    def faceted_title(self, db, williams_entity, solid_state, credit_roles):
        title = Title.objects.create(name="Medieval Madness", opdb_id="G5pe4")
        franchise = Franchise.objects.create(name="Castle Games")
        title.franchise = franchise
        title.save()
        series = Series.objects.create(name="Castle Series")
        series.titles.add(title)

        dmd = DisplayType.objects.create(name="DMD", slug="dmd")
        wpc = System.objects.create(name="WPC-95", slug="wpc-95")
        person = Person.objects.create(name="Pat Lawlor")
        theme = Theme.objects.create(name="Medieval", slug="medieval")
        role = CreditRole.objects.get(slug="design")

        m1 = MachineModel.objects.create(
            name="Medieval Madness",
            corporate_entity=williams_entity,
            year=1997,
            title=title,
            technology_generation=solid_state,
            display_type=dmd,
            system=wpc,
            player_count=4,
            ipdb_rating=8.5,
        )
        m1.themes.add(theme)
        Credit.objects.create(model=m1, person=person, role=role)

        # Second model with different year to test year_min/year_max
        MachineModel.objects.create(
            name="Medieval Madness (Remake)",
            corporate_entity=williams_entity,
            year=2015,
            title=title,
            technology_generation=solid_state,
            player_count=4,
        )
        return title

    def test_all_titles_returns_facet_fields(self, client, faceted_title):
        resp = client.get("/api/titles/all/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        item = data[0]

        # Basic fields
        assert item["name"] == "Medieval Madness"
        assert item["manufacturer_slug"] == "williams"

        # Tech generations
        assert len(item["tech_generations"]) == 1
        assert item["tech_generations"][0]["slug"] == "solid-state"

        # Display types
        assert len(item["display_types"]) == 1
        assert item["display_types"][0]["slug"] == "dmd"

        # Player counts
        assert item["player_counts"] == [4]

        # Systems
        assert len(item["systems"]) == 1
        assert item["systems"][0]["slug"] == "wpc-95"

        # Themes
        assert len(item["themes"]) == 1
        assert item["themes"][0]["slug"] == "medieval"

        # Persons
        assert len(item["persons"]) == 1
        assert item["persons"][0]["slug"] == "pat-lawlor"

        # Franchise
        assert item["franchise"]["slug"] == "castle-games"

        # Series
        assert len(item["series"]) == 1
        assert item["series"][0]["slug"] == "castle-series"

        # Year range from two models (1997 and 2015)
        assert item["year_min"] == 1997
        assert item["year_max"] == 2015

        # Rating
        assert item["ipdb_rating_max"] == 8.5

    def test_all_titles_deduplicates_tech_generations(self, client, faceted_title):
        """Two models with the same tech gen should yield one entry."""
        resp = client.get("/api/titles/all/")
        data = resp.json()
        # Both models are solid-state, but should be deduped to 1
        assert len(data[0]["tech_generations"]) == 1

    def test_all_titles_excludes_variant_models(self, client, faceted_title):
        """Variant models should not contribute facet data."""
        parent = MachineModel.objects.get(name="Medieval Madness")
        lcd = DisplayType.objects.create(name="LCD", slug="lcd")
        MachineModel.objects.create(
            name="Medieval Madness (LE)",
            title=faceted_title,
            variant_of=parent,
            display_type=lcd,
        )
        resp = client.get("/api/titles/all/")
        data = resp.json()
        display_slugs = [d["slug"] for d in data[0]["display_types"]]
        assert "lcd" not in display_slugs

    def test_all_titles_empty_title(self, client, db):
        """Title with no models returns empty facet arrays."""
        Title.objects.create(name="Empty", opdb_id="EMPTY")
        resp = client.get("/api/titles/all/")
        data = resp.json()
        item = data[0]
        assert item["tech_generations"] == []
        assert item["display_types"] == []
        assert item["player_counts"] == []
        assert item["themes"] == []
        assert item["persons"] == []
        assert item["franchise"] is None
        assert item["series"] == []
        assert item["year_min"] is None
        assert item["year_max"] is None
        assert item["ipdb_rating_max"] is None
