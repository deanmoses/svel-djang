from apps.catalog.models import (
    CorporateEntity,
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

    def test_get_manufacturer_detail(self, client, manufacturer, machine_model):
        title = Title.objects.create(name="Medieval Madness", opdb_id="G5pe4")
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
        t1 = Title.objects.create(name="No Year Title", opdb_id="T-noyear")
        t2 = Title.objects.create(name="Has Year Title", opdb_id="T-hasyear")
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
