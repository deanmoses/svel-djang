from apps.catalog.models import (
    CorporateEntity,
    CorporateEntityAlias,
    MachineModel,
    Title,
)

from .conftest import SAMPLE_IMAGES


class TestManufacturersAPI:
    def test_list_manufacturers(self, client, manufacturer, machine_model):
        resp = client.get("/api/manufacturers/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["name"] == "Williams"
        assert data["items"][0]["model_count"] == 1

    def test_get_manufacturer_detail(
        self, client, manufacturer, williams_entity, machine_model
    ):
        title = Title.objects.create(name="Medieval Madness", opdb_id="G5pe4")
        machine_model.title = title
        machine_model.save()
        resp = client.get(f"/api/manufacturers/{manufacturer.slug}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Williams"
        assert len(data["entities"]) == 1
        assert data["entities"][0]["name"] == "Williams Electronics"
        assert len(data["titles"]) == 1
        assert data["titles"][0]["name"] == "Medieval Madness"

    def test_get_manufacturer_entities_ordered_by_years(self, client, manufacturer):
        CorporateEntity.objects.create(
            manufacturer=manufacturer,
            name="Williams Latest",
            slug="williams-latest",
            year_start=1999,
            year_end=2010,
        )
        CorporateEntity.objects.create(
            manufacturer=manufacturer,
            name="Williams Early",
            slug="williams-mfg",
            year_start=1943,
            year_end=1985,
        )
        CorporateEntity.objects.create(
            manufacturer=manufacturer,
            name="Williams Middle",
            slug="williams-middle",
            year_start=1985,
            year_end=1999,
        )
        resp = client.get(f"/api/manufacturers/{manufacturer.slug}")
        entities = resp.json()["entities"]
        assert [e["name"] for e in entities] == [
            "Williams Early",
            "Williams Middle",
            "Williams Latest",
        ]

    def test_list_all_manufacturers_thumbnail_prefers_year(
        self, client, williams_entity, db
    ):
        MachineModel.objects.create(
            name="No Year Game",
            corporate_entity=williams_entity,
            extra_data={"opdb.images": SAMPLE_IMAGES},
        )
        MachineModel.objects.create(
            name="Has Year Game",
            corporate_entity=williams_entity,
            year=2020,
            extra_data={
                "opdb.images": [
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

    def test_get_manufacturer_detail_titles_sorted_year_desc(
        self, client, manufacturer, williams_entity, db
    ):
        """Titles should be sorted newest-first, even across multiple entities."""
        entity2 = CorporateEntity.objects.create(
            manufacturer=manufacturer,
            name="Williams Early",
            slug="williams-early",
            year_start=1943,
            year_end=1985,
        )
        t_old = Title.objects.create(name="Old Game", opdb_id="T-old")
        t_mid = Title.objects.create(name="Mid Game", opdb_id="T-mid")
        t_new = Title.objects.create(name="New Game", opdb_id="T-new")
        MachineModel.objects.create(
            name="Old", corporate_entity=entity2, title=t_old, year=1960
        )
        MachineModel.objects.create(
            name="Mid", corporate_entity=williams_entity, title=t_mid, year=1995
        )
        MachineModel.objects.create(
            name="New", corporate_entity=williams_entity, title=t_new, year=2020
        )
        resp = client.get(f"/api/manufacturers/{manufacturer.slug}")
        years = [t["year"] for t in resp.json()["titles"]]
        assert years == [2020, 1995, 1960]

    def test_list_all_manufacturers_search_text_includes_ce_aliases(
        self, client, williams_entity, db
    ):
        """CE aliases should appear in search_text so the frontend can match them."""
        CorporateEntityAlias.objects.create(
            corporate_entity=williams_entity, value="Williams Elektronik"
        )
        MachineModel.objects.create(name="Test Game", corporate_entity=williams_entity)
        resp = client.get("/api/manufacturers/all/")
        data = resp.json()
        mfr = data[0]
        assert "Williams Elektronik" in mfr["search_text"]

    def test_get_manufacturer_detail_nulls_last(
        self, client, manufacturer, williams_entity, db
    ):
        t1 = Title.objects.create(name="No Year Title", opdb_id="T-noyear")
        t2 = Title.objects.create(name="Has Year Title", opdb_id="T-hasyear")
        MachineModel.objects.create(
            name="No Year Game",
            corporate_entity=williams_entity,
            title=t1,
        )
        MachineModel.objects.create(
            name="Has Year Game",
            corporate_entity=williams_entity,
            year=2020,
            title=t2,
        )
        resp = client.get(f"/api/manufacturers/{manufacturer.slug}")
        data = resp.json()
        names = [t["name"] for t in data["titles"]]
        assert names[-1] == "No Year Title"
