from apps.catalog.models import (
    Credit,
    CreditRole,
    MachineModel,
    Title,
)


class TestPeopleAPI:
    def test_list_people(self, client, person, machine_model, credit_roles):
        role = CreditRole.objects.get(slug="design")
        Credit.objects.create(model=machine_model, person=person, role=role)
        resp = client.get("/api/people/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["name"] == "Pat Lawlor"
        assert data["items"][0]["credit_count"] == 1

    def test_get_person_detail(self, client, person, machine_model, credit_roles):
        title = Title.objects.create(name="Medieval Madness", opdb_id="G5pe4-p")
        machine_model.title = title
        machine_model.save()
        role = CreditRole.objects.get(slug="design")
        Credit.objects.create(model=machine_model, person=person, role=role)
        resp = client.get(f"/api/people/{person.slug}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Pat Lawlor"
        assert len(data["titles"]) == 1
        assert data["titles"][0]["name"] == "Medieval Madness"
        assert data["titles"][0]["roles"] == ["Design"]
        assert data["titles"][0]["year"] == 1997

    def test_get_person_detail_year_desc_nulls_last(
        self, client, person, db, credit_roles
    ):
        role = CreditRole.objects.get(slug="design")
        t1 = Title.objects.create(name="Old Title", opdb_id="T-old")
        t2 = Title.objects.create(name="New Title", opdb_id="T-new")
        t3 = Title.objects.create(name="No Year Title", opdb_id="T-noyear-p")
        old = MachineModel.objects.create(name="Old Game", year=1990, title=t1)
        new = MachineModel.objects.create(name="New Game", year=2020, title=t2)
        no_year = MachineModel.objects.create(name="No Year Game", title=t3)
        for m in (old, new, no_year):
            Credit.objects.create(model=m, person=person, role=role)
        resp = client.get(f"/api/people/{person.slug}")
        names = [t["name"] for t in resp.json()["titles"]]
        assert names == ["New Title", "Old Title", "No Year Title"]
