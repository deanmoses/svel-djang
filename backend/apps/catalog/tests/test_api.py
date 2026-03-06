import pytest
from django.core.cache import cache
from django.test import Client

from apps.catalog.cache import MODELS_ALL_KEY
from apps.catalog.models import (
    CorporateEntity,
    DesignCredit,
    DisplayType,
    Franchise,
    MachineModel,
    Manufacturer,
    Person,
    Series,
    System,
    TechnologyGeneration,
    Theme,
    Title,
)
from apps.provenance.models import Claim, Source

SAMPLE_IMAGES = [
    {
        "primary": True,
        "type": "backglass",
        "urls": {
            "small": "https://img.opdb.org/sm.jpg",
            "medium": "https://img.opdb.org/md.jpg",
            "large": "https://img.opdb.org/lg.jpg",
        },
    }
]


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def source(db):
    return Source.objects.create(name="IPDB", source_type="database", priority=10)


@pytest.fixture
def manufacturer(db):
    return Manufacturer.objects.create(name="Williams", trade_name="Williams")


@pytest.fixture
def stern(db):
    return Manufacturer.objects.create(name="Stern", trade_name="Stern")


@pytest.fixture
def person(db):
    return Person.objects.create(name="Pat Lawlor")


@pytest.fixture
def solid_state(db):
    return TechnologyGeneration.objects.create(name="Solid State", slug="solid-state")


@pytest.fixture
def machine_model(db, manufacturer, solid_state):
    pm = MachineModel.objects.create(
        name="Medieval Madness",
        manufacturer=manufacturer,
        year=1997,
        technology_generation=solid_state,
    )
    t = Theme.objects.create(name="Medieval", slug="medieval")
    pm.themes.add(t)
    return pm


@pytest.fixture
def another_model(db, stern, solid_state):
    return MachineModel.objects.create(
        name="The Mandalorian",
        manufacturer=stern,
        year=2021,
        technology_generation=solid_state,
    )


class TestModelsAPI:
    def test_list_models(self, client, machine_model):
        resp = client.get("/api/models/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["name"] == "Medieval Madness"

    def test_list_models_filter_manufacturer(
        self, client, machine_model, another_model
    ):
        resp = client.get("/api/models/?manufacturer=williams")
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["name"] == "Medieval Madness"

    def test_list_models_filter_type(self, client, machine_model):
        resp = client.get("/api/models/?type=solid-state")
        data = resp.json()
        assert data["count"] == 1

        resp = client.get("/api/models/?type=electromechanical")
        data = resp.json()
        assert data["count"] == 0

    def test_list_models_filter_year_range(self, client, machine_model, another_model):
        resp = client.get("/api/models/?year_min=2000&year_max=2025")
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["name"] == "The Mandalorian"

    def test_list_models_filter_person(self, client, machine_model, person):
        DesignCredit.objects.create(model=machine_model, person=person, role="design")
        resp = client.get("/api/models/?person=pat-lawlor")
        data = resp.json()
        assert data["count"] == 1

    def test_list_models_ordering(self, client, machine_model, another_model):
        resp = client.get("/api/models/?ordering=-year")
        data = resp.json()
        assert data["items"][0]["name"] == "The Mandalorian"

    def test_list_models_ordering_nulls_last(self, client, machine_model, db):
        """Models with no year sort after models with a year."""
        MachineModel.objects.create(name="Unknown Year Game")
        resp = client.get("/api/models/?ordering=-year")
        data = resp.json()
        names = [m["name"] for m in data["items"]]
        assert names[-1] == "Unknown Year Game"

    def test_list_models_ordering_stable(self, client, manufacturer, db):
        """Models with the same year are sorted by name for stability."""
        MachineModel.objects.create(name="Zeta", manufacturer=manufacturer, year=2000)
        MachineModel.objects.create(name="Alpha", manufacturer=manufacturer, year=2000)
        resp = client.get("/api/models/?ordering=-year")
        data = resp.json()
        names = [m["name"] for m in data["items"]]
        assert names == ["Alpha", "Zeta"]

    def test_list_models_excludes_aliases(self, client, machine_model):
        MachineModel.objects.create(
            name="Medieval Madness (LE)",
            alias_of=machine_model,
        )
        resp = client.get("/api/models/")
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["name"] == "Medieval Madness"

    def test_list_models_thumbnail(self, client, manufacturer, db):
        MachineModel.objects.create(
            name="With Image",
            manufacturer=manufacturer,
            extra_data={"images": SAMPLE_IMAGES},
        )
        resp = client.get("/api/models/")
        data = resp.json()
        assert data["items"][0]["thumbnail_url"] == "https://img.opdb.org/md.jpg"

    def test_get_model_detail(self, client, machine_model, person, source):
        DesignCredit.objects.create(model=machine_model, person=person, role="design")
        Claim.objects.assert_claim(
            machine_model, "year", 1997, "IPDB entry", source=source
        )

        resp = client.get(f"/api/models/{machine_model.slug}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Medieval Madness"
        assert len(data["credits"]) == 1
        assert data["credits"][0]["person_name"] == "Pat Lawlor"
        year_claims = [c for c in data["activity"] if c["field_name"] == "year"]
        assert len(year_claims) == 1
        assert year_claims[0]["source_name"] == "IPDB"
        assert year_claims[0]["is_winner"] is True

    def test_get_model_detail_images(self, client, manufacturer, db):
        pm = MachineModel.objects.create(
            name="With Image",
            manufacturer=manufacturer,
            extra_data={"images": SAMPLE_IMAGES},
        )
        resp = client.get(f"/api/models/{pm.slug}")
        data = resp.json()
        assert data["thumbnail_url"] == "https://img.opdb.org/md.jpg"
        assert data["hero_image_url"] == "https://img.opdb.org/lg.jpg"

    def test_get_model_detail_no_images(self, client, machine_model):
        resp = client.get(f"/api/models/{machine_model.slug}")
        data = resp.json()
        assert data["thumbnail_url"] is None
        assert data["hero_image_url"] is None

    def test_get_model_detail_variant_features(self, client, manufacturer, db):
        pm = MachineModel.objects.create(
            name="With Features",
            manufacturer=manufacturer,
            extra_data={"variant_features": ["Castle attack", "Gold trim"]},
        )
        resp = client.get(f"/api/models/{pm.slug}")
        data = resp.json()
        assert data["variant_features"] == ["Castle attack", "Gold trim"]

    def test_get_model_detail_aliases(self, client, machine_model):
        MachineModel.objects.create(
            name="Medieval Madness (LE)",
            alias_of=machine_model,
            extra_data={"variant_features": ["Gold trim"]},
        )
        resp = client.get(f"/api/models/{machine_model.slug}")
        data = resp.json()
        assert len(data["aliases"]) == 1
        assert data["aliases"][0]["name"] == "Medieval Madness (LE)"
        assert data["aliases"][0]["variant_features"] == ["Gold trim"]

    def test_get_model_detail_title(self, client, machine_model, db):
        title = Title.objects.create(
            name="Medieval Madness", opdb_id="G5pe4", short_name="MM"
        )
        machine_model.title = title
        machine_model.save()
        resp = client.get(f"/api/models/{machine_model.slug}")
        data = resp.json()
        assert data["title_name"] == "Medieval Madness"
        assert data["title_slug"] == title.slug

    def test_get_model_detail_no_title(self, client, machine_model):
        resp = client.get(f"/api/models/{machine_model.slug}")
        data = resp.json()
        assert data["title_name"] is None
        assert data["title_slug"] is None

    def test_get_model_404(self, client, db):
        resp = client.get("/api/models/nonexistent")
        assert resp.status_code == 404


class TestTitlesAPI:
    @pytest.fixture
    def title(self, db):
        return Title.objects.create(
            name="Medieval Madness", opdb_id="G5pe4", short_name="MM"
        )

    @pytest.fixture
    def title_with_machines(self, title, manufacturer):
        MachineModel.objects.create(
            name="Medieval Madness",
            manufacturer=manufacturer,
            year=1997,
            title=title,
            extra_data={"images": SAMPLE_IMAGES},
        )
        MachineModel.objects.create(
            name="Medieval Madness (Remake)",
            manufacturer=manufacturer,
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
        assert item["short_name"] == "MM"
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

    def test_get_title_detail_excludes_aliases(self, client, title_with_machines):
        parent = MachineModel.objects.get(name="Medieval Madness")
        MachineModel.objects.create(
            name="Medieval Madness (LE)",
            title=title_with_machines,
            alias_of=parent,
        )
        resp = client.get(f"/api/titles/{title_with_machines.slug}")
        data = resp.json()
        assert len(data["machines"]) == 2
        names = [m["name"] for m in data["machines"]]
        assert "Medieval Madness (LE)" not in names

    def test_machine_count_excludes_aliases(self, client, title_with_machines):
        parent = MachineModel.objects.get(name="Medieval Madness")
        MachineModel.objects.create(
            name="Medieval Madness (LE)",
            title=title_with_machines,
            alias_of=parent,
        )
        resp = client.get("/api/titles/")
        data = resp.json()
        assert data["items"][0]["machine_count"] == 2

    def test_get_title_404(self, client, db):
        resp = client.get("/api/titles/nonexistent")
        assert resp.status_code == 404


class TestManufacturersAPI:
    def test_list_manufacturers(self, client, manufacturer, machine_model):
        resp = client.get("/api/manufacturers/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["name"] == "Williams"
        assert data["items"][0]["model_count"] == 1

    def test_get_manufacturer_detail(self, client, manufacturer, machine_model):
        title = Title.objects.create(
            name="Medieval Madness", opdb_id="G5pe4", short_name="MM"
        )
        machine_model.title = title
        machine_model.save()
        CorporateEntity.objects.create(
            manufacturer=manufacturer,
            name="Williams Manufacturing Company",
            years_active="1943-1985",
        )
        resp = client.get(f"/api/manufacturers/{manufacturer.slug}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Williams"
        assert len(data["entities"]) == 1
        assert data["entities"][0]["name"] == "Williams Manufacturing Company"
        assert len(data["titles"]) == 1
        assert data["titles"][0]["name"] == "Medieval Madness"

    def test_get_manufacturer_entities_ordered_by_years(self, client, manufacturer):
        CorporateEntity.objects.create(
            manufacturer=manufacturer,
            name="Williams Latest",
            years_active="1999-2010",
        )
        CorporateEntity.objects.create(
            manufacturer=manufacturer,
            name="Williams Early",
            years_active="1943-1985",
        )
        CorporateEntity.objects.create(
            manufacturer=manufacturer,
            name="Williams Middle",
            years_active="1985-1999",
        )
        resp = client.get(f"/api/manufacturers/{manufacturer.slug}")
        entities = resp.json()["entities"]
        assert [e["name"] for e in entities] == [
            "Williams Early",
            "Williams Middle",
            "Williams Latest",
        ]

    def test_list_all_manufacturers_thumbnail_prefers_year(
        self, client, manufacturer, db
    ):
        MachineModel.objects.create(
            name="No Year Game",
            manufacturer=manufacturer,
            extra_data={"images": SAMPLE_IMAGES},
        )
        MachineModel.objects.create(
            name="Has Year Game",
            manufacturer=manufacturer,
            year=2020,
            extra_data={
                "images": [
                    {
                        "primary": True,
                        "type": "backglass",
                        "urls": {
                            "small": "https://img.opdb.org/year-sm.jpg",
                            "medium": "https://img.opdb.org/year-md.jpg",
                            "large": "https://img.opdb.org/year-lg.jpg",
                        },
                    }
                ]
            },
        )
        resp = client.get("/api/manufacturers/all/")
        data = resp.json()
        assert data[0]["thumbnail_url"] == "https://img.opdb.org/year-md.jpg"

    def test_get_manufacturer_detail_nulls_last(self, client, manufacturer, db):
        t1 = Title.objects.create(
            name="No Year Title", opdb_id="T-noyear", short_name="NYT"
        )
        t2 = Title.objects.create(
            name="Has Year Title", opdb_id="T-hasyear", short_name="HYT"
        )
        MachineModel.objects.create(
            name="No Year Game",
            manufacturer=manufacturer,
            title=t1,
        )
        MachineModel.objects.create(
            name="Has Year Game",
            manufacturer=manufacturer,
            year=2020,
            title=t2,
        )
        resp = client.get(f"/api/manufacturers/{manufacturer.slug}")
        data = resp.json()
        names = [t["name"] for t in data["titles"]]
        assert names[-1] == "No Year Title"


class TestPeopleAPI:
    def test_list_people(self, client, person, machine_model):
        DesignCredit.objects.create(model=machine_model, person=person, role="design")
        resp = client.get("/api/people/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["name"] == "Pat Lawlor"
        assert data["items"][0]["credit_count"] == 1

    def test_get_person_detail(self, client, person, machine_model):
        title = Title.objects.create(
            name="Medieval Madness", opdb_id="G5pe4-p", short_name="MM"
        )
        machine_model.title = title
        machine_model.save()
        DesignCredit.objects.create(model=machine_model, person=person, role="design")
        resp = client.get(f"/api/people/{person.slug}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Pat Lawlor"
        assert len(data["titles"]) == 1
        assert data["titles"][0]["name"] == "Medieval Madness"
        assert data["titles"][0]["roles"] == ["Design"]
        assert data["titles"][0]["year"] == 1997

    def test_get_person_detail_year_desc_nulls_last(
        self, client, person, manufacturer, db
    ):
        t1 = Title.objects.create(name="Old Title", opdb_id="T-old")
        t2 = Title.objects.create(name="New Title", opdb_id="T-new")
        t3 = Title.objects.create(name="No Year Title", opdb_id="T-noyear-p")
        old = MachineModel.objects.create(
            name="Old Game", manufacturer=manufacturer, year=1990, title=t1
        )
        new = MachineModel.objects.create(
            name="New Game", manufacturer=manufacturer, year=2020, title=t2
        )
        no_year = MachineModel.objects.create(
            name="No Year Game", manufacturer=manufacturer, title=t3
        )
        for m in (old, new, no_year):
            DesignCredit.objects.create(model=m, person=person, role="design")
        resp = client.get(f"/api/people/{person.slug}")
        names = [t["name"] for t in resp.json()["titles"]]
        assert names == ["New Title", "Old Title", "No Year Title"]


class TestAllEndpointCache:
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        cache.clear()
        yield
        cache.clear()

    def test_models_all_caches_on_second_request(self, client, machine_model):
        resp1 = client.get("/api/models/all/")
        assert resp1.status_code == 200
        assert cache.get(MODELS_ALL_KEY) is not None

        resp2 = client.get("/api/models/all/")
        assert resp2.json() == resp1.json()

    def test_model_save_invalidates_cache(self, client, machine_model):
        client.get("/api/models/all/")
        assert cache.get(MODELS_ALL_KEY) is not None

        machine_model.name = "Medieval Madness LE"
        machine_model.save()
        assert cache.get(MODELS_ALL_KEY) is None

    def test_new_model_appears_after_invalidation(self, client, machine_model, stern):
        resp1 = client.get("/api/models/all/")
        count_before = len(resp1.json())

        MachineModel.objects.create(name="Godzilla", manufacturer=stern, year=2021)
        resp2 = client.get("/api/models/all/")
        assert len(resp2.json()) == count_before + 1


class TestSourcesAPI:
    def test_list_sources(self, client, source):
        resp = client.get("/api/sources/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "IPDB"


class TestSystemsAPI:
    @pytest.fixture
    def system(self, db, manufacturer):
        return System.objects.create(
            name="Williams WPC-95",
            slug="wpc-95",
            manufacturer=manufacturer,
        )

    @pytest.fixture
    def system_with_machines(self, system, manufacturer):
        t1 = Title.objects.create(
            name="Medieval Madness", opdb_id="G5pe4-s", short_name="MM"
        )
        t2 = Title.objects.create(
            name="No Good Gofers", opdb_id="T-ngg", short_name="NGG"
        )
        MachineModel.objects.create(
            name="Medieval Madness",
            manufacturer=manufacturer,
            year=1997,
            system=system,
            title=t1,
        )
        MachineModel.objects.create(
            name="No Good Gofers",
            manufacturer=manufacturer,
            year=1997,
            system=system,
            title=t2,
        )
        return system

    def test_get_system_detail(self, client, system_with_machines):
        resp = client.get("/api/systems/wpc-95")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Williams WPC-95"
        assert data["slug"] == "wpc-95"
        assert data["manufacturer_name"] == "Williams"
        assert len(data["titles"]) == 2

    def test_get_system_detail_titles_sorted_year_desc(
        self, client, system_with_machines, manufacturer
    ):
        t3 = Title.objects.create(name="Old Title", opdb_id="T-old-s")
        MachineModel.objects.create(
            name="Old Game",
            manufacturer=manufacturer,
            year=1990,
            system=system_with_machines,
            title=t3,
        )
        resp = client.get("/api/systems/wpc-95")
        data = resp.json()
        years = [t["year"] for t in data["titles"] if t["year"]]
        assert years == sorted(years, reverse=True)

    def test_get_system_404(self, client, db):
        resp = client.get("/api/systems/nonexistent")
        assert resp.status_code == 404


class TestTitlesAllFacets:
    """Test that /api/titles/all/ returns enriched facet data."""

    @pytest.fixture
    def faceted_title(self, db, manufacturer, solid_state):
        title = Title.objects.create(
            name="Medieval Madness", opdb_id="G5pe4", short_name="MM"
        )
        franchise = Franchise.objects.create(name="Castle Games")
        title.franchise = franchise
        title.save()
        series = Series.objects.create(name="Castle Series")
        series.titles.add(title)

        dmd = DisplayType.objects.create(name="DMD", slug="dmd")
        wpc = System.objects.create(name="WPC-95", slug="wpc-95")
        person = Person.objects.create(name="Pat Lawlor")
        theme = Theme.objects.create(name="Medieval", slug="medieval")

        m1 = MachineModel.objects.create(
            name="Medieval Madness",
            manufacturer=manufacturer,
            year=1997,
            title=title,
            technology_generation=solid_state,
            display_type=dmd,
            system=wpc,
            player_count=4,
            ipdb_rating=8.5,
        )
        m1.themes.add(theme)
        DesignCredit.objects.create(model=m1, person=person, role="design")

        # Second model with different year to test year_min/year_max
        MachineModel.objects.create(
            name="Medieval Madness (Remake)",
            manufacturer=manufacturer,
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

    def test_all_titles_excludes_alias_models(self, client, faceted_title):
        """Alias models should not contribute facet data."""
        parent = MachineModel.objects.get(name="Medieval Madness")
        lcd = DisplayType.objects.create(name="LCD", slug="lcd")
        MachineModel.objects.create(
            name="Medieval Madness (LE)",
            title=faceted_title,
            alias_of=parent,
            display_type=lcd,
        )
        resp = client.get("/api/titles/all/")
        data = resp.json()
        display_slugs = [d["slug"] for d in data[0]["display_types"]]
        assert "lcd" not in display_slugs

    def test_all_titles_empty_title(self, client, db):
        """Title with no models returns empty facet arrays."""
        Title.objects.create(name="Empty", opdb_id="EMPTY", short_name="E")
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
