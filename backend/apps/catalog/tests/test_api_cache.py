import pytest
from constance.signals import config_updated
from django.core.cache import cache

from apps.catalog.cache import MODELS_ALL_KEY, TITLES_ALL_KEY
from apps.catalog.models import (
    Cabinet,
    CorporateEntity,
    CorporateEntityLocation,
    Credit,
    CreditRole,
    DisplaySubtype,
    DisplayType,
    Franchise,
    GameFormat,
    GameplayFeature,
    Location,
    MachineModel,
    Manufacturer,
    Person,
    RewardType,
    Series,
    System,
    Tag,
    TechnologyGeneration,
    TechnologySubgeneration,
    Theme,
    Title,
)
from apps.catalog.signals import _cache_invalidating_models
from apps.catalog.tests.conftest import make_machine_model


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

        make_machine_model(name="Godzilla", slug="godzilla", year=2021)
        resp2 = client.get("/api/models/all/")
        assert len(resp2.json()) == count_before + 1

    def test_titles_all_caches_on_second_request(self, client, machine_model):
        resp1 = client.get("/api/titles/all/")
        assert resp1.status_code == 200
        assert cache.get(TITLES_ALL_KEY) is not None

        resp2 = client.get("/api/titles/all/")
        assert resp2.json() == resp1.json()

    def test_title_save_invalidates_cache(self, client, db):
        title = Title.objects.create(
            name="Cactus Canyon", slug="cactus-canyon", opdb_id="CC1"
        )
        client.get("/api/titles/all/")
        assert cache.get(TITLES_ALL_KEY) is not None

        title.name = "Cactus Canyon Continued"
        title.save()
        assert cache.get(TITLES_ALL_KEY) is None

    def test_new_title_appears_after_invalidation(self, client, machine_model):
        resp1 = client.get("/api/titles/all/")
        count_before = len(resp1.json())

        Title.objects.create(name="Godzilla", slug="godzilla", opdb_id="GZ1")
        resp2 = client.get("/api/titles/all/")
        assert len(resp2.json()) == count_before + 1


class TestCacheInvalidatingModelsParity:
    """Derived signal-connection set must match the expected model landscape.

    If this fails, a new ``CatalogModel`` was added (or an existing one removed)
    — update the expected set here intentionally rather than silently drifting.
    """

    def test_derived_set_matches_expected(self):
        expected = {
            Cabinet,
            CorporateEntity,
            CorporateEntityLocation,
            Credit,
            CreditRole,
            DisplaySubtype,
            DisplayType,
            Franchise,
            GameFormat,
            GameplayFeature,
            Location,
            MachineModel,
            Manufacturer,
            Person,
            RewardType,
            Series,
            System,
            Tag,
            TechnologyGeneration,
            TechnologySubgeneration,
            Theme,
            Title,
        }
        assert set(_cache_invalidating_models()) == expected


class TestPolicyChangeInvalidation:
    """Changing CONTENT_DISPLAY_POLICY busts cached /all/ payloads, since the
    rendered content depends on the active display threshold."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        cache.clear()
        yield
        cache.clear()

    def test_policy_change_invalidates_cache(self, client, machine_model):
        client.get("/api/models/all/")
        assert cache.get(MODELS_ALL_KEY) is not None

        config_updated.send(
            sender=None,
            key="CONTENT_DISPLAY_POLICY",
            old_value="licensed-only",
            new_value="show-all",
        )
        assert cache.get(MODELS_ALL_KEY) is None

    def test_unrelated_key_change_does_not_invalidate(self, client, machine_model):
        client.get("/api/models/all/")
        assert cache.get(MODELS_ALL_KEY) is not None

        config_updated.send(
            sender=None,
            key="SOME_OTHER_KEY",
            old_value="a",
            new_value="b",
        )
        assert cache.get(MODELS_ALL_KEY) is not None


class TestConditionalGet:
    """Pre-computed ETags let ConditionalGetMiddleware return 304 without
    serialising or hashing the response body."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        cache.clear()
        yield
        cache.clear()

    @pytest.mark.parametrize("path", ["/api/models/all/", "/api/titles/all/"])
    def test_304_on_matching_etag(self, client, machine_model, path):
        resp = client.get(path)
        assert resp.status_code == 200
        etag = resp["ETag"]
        assert etag

        resp2 = client.get(path, headers={"If-None-Match": etag})
        assert resp2.status_code == 304

    @pytest.mark.parametrize("path", ["/api/models/all/", "/api/titles/all/"])
    def test_200_on_stale_etag(self, client, machine_model, path):
        client.get(path)  # populate cache

        resp = client.get(path, headers={"If-None-Match": '"stale"'})
        assert resp.status_code == 200
        assert resp["ETag"]

    @pytest.mark.parametrize(
        ("path", "cache_key"),
        [
            ("/api/models/all/", MODELS_ALL_KEY),
            ("/api/titles/all/", TITLES_ALL_KEY),
        ],
    )
    def test_cache_stores_bytes_and_etag(self, client, machine_model, path, cache_key):
        client.get(path)
        cached = cache.get(cache_key)
        assert cached is not None
        json_bytes, etag = cached
        assert isinstance(json_bytes, bytes)
        assert etag.startswith('"')
        assert etag.endswith('"')
