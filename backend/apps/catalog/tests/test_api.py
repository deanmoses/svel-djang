import pytest

from apps.catalog.models import MachineModel, System, Title


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
    def system_with_machines(self, system):
        t1 = Title.objects.create(name="Medieval Madness", opdb_id="G5pe4-s")
        t2 = Title.objects.create(name="No Good Gofers", opdb_id="T-ngg")
        MachineModel.objects.create(
            name="Medieval Madness",
            year=1997,
            system=system,
            title=t1,
        )
        MachineModel.objects.create(
            name="No Good Gofers",
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
        self, client, system_with_machines
    ):
        t3 = Title.objects.create(name="Old Title", opdb_id="T-old-s")
        MachineModel.objects.create(
            name="Old Game",
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
