"""Tests for the wikilink autocomplete API endpoints."""

import pytest
from django.test import Client


@pytest.fixture
def api():
    return Client()


@pytest.fixture
def manufacturer(db):
    from apps.catalog.models import Manufacturer

    return Manufacturer.objects.create(
        name="Williams", slug="williams", status="active"
    )


@pytest.fixture
def deleted_manufacturer(db):
    from apps.catalog.models import Manufacturer

    return Manufacturer.objects.create(
        name="Defunct Co", slug="defunct-co", status="deleted"
    )


@pytest.mark.django_db
class TestListLinkTypes:
    def test_returns_all_autocomplete_types(self, api):
        resp = api.get("/api/link-types/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Each type has required fields
        first = data[0]
        assert "name" in first
        assert "label" in first
        assert "description" in first

    def test_primary_types_sorted_first(self, api):
        resp = api.get("/api/link-types/")
        names = [t["name"] for t in resp.json()]
        # Title, MachineModel, Manufacturer, Person should appear before taxonomy types
        assert names.index("title") < names.index("tag")
        assert names.index("manufacturer") < names.index("cabinet")

    def test_cite_type_in_picker_with_custom_flow(self, api):
        resp = api.get("/api/link-types/")
        types_by_name = {t["name"]: t for t in resp.json()}
        assert "cite" in types_by_name
        assert types_by_name["cite"]["flow"] == "custom"
        assert types_by_name["cite"]["label"] == "Citation"

    def test_all_types_include_flow_field(self, api):
        resp = api.get("/api/link-types/")
        for t in resp.json():
            assert "flow" in t, f"Missing 'flow' field on link type {t['name']}"


@pytest.mark.django_db
class TestSearchLinkTargets:
    def test_search_returns_matching_results(self, api, manufacturer):
        resp = api.get("/api/link-types/targets/", {"type": "manufacturer", "q": "wil"})
        assert resp.status_code == 200
        refs = [r["ref"] for r in resp.json()["results"]]
        assert "williams" in refs

    def test_search_returns_label(self, api, manufacturer):
        resp = api.get("/api/link-types/targets/", {"type": "manufacturer", "q": "wil"})
        result = resp.json()["results"][0]
        assert result["label"] == "Williams"
        assert result["ref"] == "williams"

    def test_empty_query_returns_results(self, api, manufacturer):
        resp = api.get("/api/link-types/targets/", {"type": "manufacturer", "q": ""})
        assert resp.status_code == 200
        assert len(resp.json()["results"]) >= 1

    def test_no_match_returns_empty(self, api, manufacturer):
        resp = api.get(
            "/api/link-types/targets/", {"type": "manufacturer", "q": "zzzznotfound"}
        )
        assert resp.status_code == 200
        assert resp.json()["results"] == []

    def test_invalid_type_returns_400(self, api):
        resp = api.get("/api/link-types/targets/", {"type": "nonexistent", "q": ""})
        assert resp.status_code == 400

    def test_excludes_deleted_entities(self, api, manufacturer, deleted_manufacturer):
        resp = api.get("/api/link-types/targets/", {"type": "manufacturer", "q": ""})
        refs = [r["ref"] for r in resp.json()["results"]]
        assert "williams" in refs
        assert "defunct-co" not in refs
