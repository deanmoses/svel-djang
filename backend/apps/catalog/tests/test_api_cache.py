import pytest
from django.core.cache import cache

from apps.catalog.cache import MODELS_ALL_KEY, TITLES_ALL_KEY
from apps.catalog.models import MachineModel, Title


class TestAllEndpointCache:
    @pytest.fixture(autouse=True)
    def _clear_cache(self):
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

    def test_new_model_appears_after_invalidation(self, client, machine_model):
        resp1 = client.get("/api/models/all/")
        count_before = len(resp1.json())

        MachineModel.objects.create(name="Godzilla", year=2021)
        resp2 = client.get("/api/models/all/")
        assert len(resp2.json()) == count_before + 1

    def test_titles_all_caches_on_second_request(self, client, machine_model):
        resp1 = client.get("/api/titles/all/")
        assert resp1.status_code == 200
        assert cache.get(TITLES_ALL_KEY) is not None

        resp2 = client.get("/api/titles/all/")
        assert resp2.json() == resp1.json()

    def test_title_save_invalidates_cache(self, client, db):
        title = Title.objects.create(name="Cactus Canyon", opdb_id="CC1")
        client.get("/api/titles/all/")
        assert cache.get(TITLES_ALL_KEY) is not None

        title.name = "Cactus Canyon Continued"
        title.save()
        assert cache.get(TITLES_ALL_KEY) is None

    def test_new_title_appears_after_invalidation(self, client, machine_model):
        resp1 = client.get("/api/titles/all/")
        count_before = len(resp1.json())

        Title.objects.create(name="Godzilla", opdb_id="GZ1")
        resp2 = client.get("/api/titles/all/")
        assert len(resp2.json()) == count_before + 1
