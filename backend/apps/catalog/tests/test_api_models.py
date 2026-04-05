from apps.catalog.models import (
    Credit,
    CreditRole,
    MachineModel,
    Title,
)
from apps.provenance.models import Claim

from .conftest import SAMPLE_IMAGES


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

    def test_list_models_filter_person(
        self, client, machine_model, person, credit_roles
    ):
        role = CreditRole.objects.get(slug="design")
        Credit.objects.create(model=machine_model, person=person, role=role)
        resp = client.get("/api/models/?person=pat-lawlor")
        data = resp.json()
        assert data["count"] == 1

    def test_list_models_ordering(self, client, machine_model, another_model):
        resp = client.get("/api/models/?ordering=-year")
        data = resp.json()
        assert data["items"][0]["name"] == "The Mandalorian"

    def test_list_models_ordering_nulls_last(self, client, machine_model, db):
        """Models with no year sort after models with a year."""
        MachineModel.objects.create(name="Unknown Year Game", slug="unknown-year-game")
        resp = client.get("/api/models/?ordering=-year")
        data = resp.json()
        names = [m["name"] for m in data["items"]]
        assert names[-1] == "Unknown Year Game"

    def test_list_models_ordering_stable(self, client, db):
        """Models with the same year are sorted by name for stability."""
        MachineModel.objects.create(name="Zeta", slug="zeta", year=2000)
        MachineModel.objects.create(name="Alpha", slug="alpha", year=2000)
        resp = client.get("/api/models/?ordering=-year")
        data = resp.json()
        names = [m["name"] for m in data["items"]]
        assert names == ["Alpha", "Zeta"]

    def test_list_models_excludes_variants(self, client, machine_model):
        MachineModel.objects.create(
            name="Medieval Madness (LE)",
            slug="medieval-madness-le",
            variant_of=machine_model,
        )
        resp = client.get("/api/models/")
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["name"] == "Medieval Madness"

    def test_all_models_includes_variants(self, client, machine_model):
        MachineModel.objects.create(
            name="Medieval Madness (LE)",
            slug="medieval-madness-le",
            variant_of=machine_model,
        )
        resp = client.get("/api/models/all/")
        names = [m["name"] for m in resp.json()]
        assert "Medieval Madness" in names
        assert "Medieval Madness (LE)" in names

    def test_list_models_thumbnail(self, client, db):
        MachineModel.objects.create(
            name="With Image",
            slug="with-image",
            extra_data={"opdb.images": SAMPLE_IMAGES},
        )
        resp = client.get("/api/models/")
        data = resp.json()
        assert data["items"][0]["thumbnail_url"] == "https://img.opdb.org/md.jpg"

    def test_get_model_detail(
        self, client, machine_model, person, source, credit_roles
    ):
        role = CreditRole.objects.get(slug="design")
        Credit.objects.create(model=machine_model, person=person, role=role)
        Claim.objects.assert_claim(
            machine_model, "year", 1997, "IPDB entry", source=source
        )

        resp = client.get(f"/api/pages/model/{machine_model.slug}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Medieval Madness"
        assert len(data["credits"]) == 1
        assert data["credits"][0]["person"]["name"] == "Pat Lawlor"
        year_claims = [c for c in data["sources"] if c["field_name"] == "year"]
        assert len(year_claims) == 1
        assert year_claims[0]["source_name"] == "IPDB"
        assert year_claims[0]["is_winner"] is True

    def test_get_model_detail_images(self, client, db):
        pm = MachineModel.objects.create(
            name="With Image",
            slug="with-image",
            extra_data={"opdb.images": SAMPLE_IMAGES},
        )
        resp = client.get(f"/api/pages/model/{pm.slug}")
        data = resp.json()
        assert data["thumbnail_url"] == "https://img.opdb.org/md.jpg"
        assert data["hero_image_url"] == "https://img.opdb.org/lg.jpg"

    def test_get_model_detail_no_images(self, client, machine_model):
        resp = client.get(f"/api/pages/model/{machine_model.slug}")
        data = resp.json()
        assert data["thumbnail_url"] is None
        assert data["hero_image_url"] is None

    def test_get_model_detail_variant_features(self, client, db):
        pm = MachineModel.objects.create(
            name="With Features",
            slug="with-features",
            extra_data={"opdb.variant_features": ["Castle attack", "Gold trim"]},
        )
        resp = client.get(f"/api/pages/model/{pm.slug}")
        data = resp.json()
        assert data["variant_features"] == ["Castle attack", "Gold trim"]

    def test_get_model_detail_variants(self, client, machine_model):
        MachineModel.objects.create(
            name="Medieval Madness (LE)",
            slug="medieval-madness-le",
            variant_of=machine_model,
            extra_data={"opdb.variant_features": ["Gold trim"]},
        )
        resp = client.get(f"/api/pages/model/{machine_model.slug}")
        data = resp.json()
        assert len(data["variants"]) == 1
        assert data["variants"][0]["name"] == "Medieval Madness (LE)"
        assert data["variants"][0]["variant_features"] == ["Gold trim"]

    def test_get_model_detail_title(self, client, machine_model, db):
        title = Title.objects.create(
            name="Medieval Madness", slug="medieval-madness", opdb_id="G5pe4"
        )
        machine_model.title = title
        machine_model.save()
        resp = client.get(f"/api/pages/model/{machine_model.slug}")
        data = resp.json()
        assert data["title"]["name"] == "Medieval Madness"
        assert data["title"]["slug"] == title.slug

    def test_get_model_detail_no_title(self, client, machine_model):
        resp = client.get(f"/api/pages/model/{machine_model.slug}")
        data = resp.json()
        assert data["title"] is None

    def test_detail_includes_conversion_fields(self, client, db):
        """Detail response includes conversion fields."""
        source = MachineModel.objects.create(
            name="Star Trek", slug="star-trek", year=1991
        )
        conv = MachineModel.objects.create(
            name="Dark Rider",
            slug="dark-rider",
            converted_from=source,
        )
        resp = client.get(f"/api/pages/model/{conv.slug}")
        data = resp.json()
        assert data["converted_from"]["name"] == "Star Trek"
        assert data["converted_from"]["slug"] == "star-trek"
        assert data["converted_from"]["year"] == 1991

    def test_detail_includes_conversions_list(self, client, db):
        """Source machine's detail includes conversions list."""
        source = MachineModel.objects.create(
            name="Star Trek", slug="star-trek", year=1991
        )
        MachineModel.objects.create(
            name="Dark Rider",
            slug="dark-rider",
            converted_from=source,
        )
        resp = client.get(f"/api/pages/model/{source.slug}")
        data = resp.json()
        assert len(data["conversions"]) == 1
        assert data["conversions"][0]["name"] == "Dark Rider"
        assert data["conversions"][0]["slug"] == "dark-rider"

    def test_conversions_appear_in_list(self, client, db):
        """Conversions are NOT filtered from the list endpoint (unlike variants)."""
        source = MachineModel.objects.create(
            name="Star Trek", slug="star-trek", year=1991
        )
        MachineModel.objects.create(
            name="Dark Rider",
            slug="dark-rider",
            converted_from=source,
        )
        resp = client.get("/api/models/")
        data = resp.json()
        names = [m["name"] for m in data["items"]]
        assert "Dark Rider" in names
        assert "Star Trek" in names

    def test_conversion_with_variant_of_appears_in_list(self, client, db):
        """A conversion that is also a variant of another conversion still appears."""
        source = MachineModel.objects.create(
            name="Star Trek", slug="star-trek", year=1991
        )
        conv_a = MachineModel.objects.create(
            name="Dark Rider",
            slug="dark-rider",
            converted_from=source,
        )
        MachineModel.objects.create(
            name="Dark Rider LE",
            slug="dark-rider-le",
            converted_from=source,
            variant_of=conv_a,
        )
        resp = client.get("/api/models/")
        data = resp.json()
        names = [m["name"] for m in data["items"]]
        assert "Dark Rider LE" in names
        assert "Dark Rider" in names
        assert "Star Trek" in names

    def test_get_model_404(self, client, db):
        resp = client.get("/api/pages/model/nonexistent")
        assert resp.status_code == 404
