"""Tests for MachineModel relationship editing via PATCH /api/models/{slug}/claims/."""

from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model

from apps.catalog.models import (
    GameplayFeature,
    MachineModel,
    Person,
    RewardType,
    Tag,
    Theme,
)
from apps.provenance.models import ChangeSet

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="editor", password="testpass")  # pragma: allowlist secret  # fmt: skip


@pytest.fixture
def pm(db):
    return MachineModel.objects.create(name="Medieval Madness", year=1997)


@pytest.fixture
def themes(db):
    return [
        Theme.objects.create(name="Medieval", slug="medieval"),
        Theme.objects.create(name="Fantasy", slug="fantasy"),
        Theme.objects.create(name="Horror", slug="horror"),
    ]


@pytest.fixture
def tags(db):
    return [
        Tag.objects.create(name="Classic", slug="classic"),
        Tag.objects.create(name="Widebody", slug="widebody"),
    ]


@pytest.fixture
def reward_types(db):
    return [
        RewardType.objects.create(name="Multiball", slug="multiball"),
        RewardType.objects.create(name="Wizard Mode", slug="wizard-mode"),
    ]


@pytest.fixture
def gameplay_features(db):
    return [
        GameplayFeature.objects.create(name="Ramps", slug="ramps"),
        GameplayFeature.objects.create(name="Pop Bumpers", slug="pop-bumpers"),
        GameplayFeature.objects.create(name="Loops", slug="loops"),
    ]


@pytest.fixture
def people(db):
    return [
        Person.objects.create(name="Pat Lawlor", slug="pat-lawlor"),
        Person.objects.create(name="John Youssi", slug="john-youssi"),
        Person.objects.create(name="Greg Freres", slug="greg-freres"),
    ]


def _patch(client, slug, body):
    return client.patch(
        f"/api/models/{slug}/claims/",
        data=json.dumps(body),
        content_type="application/json",
    )


# ---------------------------------------------------------------------------
# Simple M2M: themes, tags, reward_types
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestM2MThemes:
    def test_add_themes(self, client, user, pm, themes):
        client.force_login(user)
        resp = _patch(client, pm.slug, {"themes": ["medieval", "fantasy"]})
        assert resp.status_code == 200
        slugs = sorted(t["slug"] for t in resp.json()["themes"])
        assert slugs == ["fantasy", "medieval"]

    def test_remove_themes(self, client, user, pm, themes):
        client.force_login(user)
        _patch(client, pm.slug, {"themes": ["medieval"]})
        resp = _patch(client, pm.slug, {"themes": []})
        assert resp.status_code == 200
        assert resp.json()["themes"] == []

    def test_replace_themes(self, client, user, pm, themes):
        client.force_login(user)
        _patch(client, pm.slug, {"themes": ["medieval"]})
        resp = _patch(client, pm.slug, {"themes": ["fantasy", "horror"]})
        assert resp.status_code == 200
        slugs = sorted(t["slug"] for t in resp.json()["themes"])
        assert slugs == ["fantasy", "horror"]

    def test_invalid_slug_returns_422(self, client, user, pm):
        client.force_login(user)
        resp = _patch(client, pm.slug, {"themes": ["nonexistent"]})
        assert resp.status_code == 422

    def test_null_leaves_unchanged(self, client, user, pm, themes):
        client.force_login(user)
        _patch(client, pm.slug, {"themes": ["medieval"]})
        # PATCH with only a scalar field, themes=null (omitted)
        resp = _patch(client, pm.slug, {"fields": {"year": 1998}})
        assert resp.status_code == 200
        assert len(resp.json()["themes"]) == 1
        assert resp.json()["themes"][0]["slug"] == "medieval"


@pytest.mark.django_db
class TestM2MTags:
    def test_add_and_remove_tags(self, client, user, pm, tags):
        client.force_login(user)
        resp = _patch(client, pm.slug, {"tags": ["classic", "widebody"]})
        assert resp.status_code == 200

        pm.refresh_from_db()
        assert set(pm.tags.values_list("slug", flat=True)) == {
            "classic",
            "widebody",
        }

        resp = _patch(client, pm.slug, {"tags": ["classic"]})
        assert resp.status_code == 200
        pm.refresh_from_db()
        assert set(pm.tags.values_list("slug", flat=True)) == {"classic"}


@pytest.mark.django_db
class TestM2MRewardTypes:
    def test_add_and_remove_reward_types(self, client, user, pm, reward_types):
        client.force_login(user)
        resp = _patch(client, pm.slug, {"reward_types": ["multiball", "wizard-mode"]})
        assert resp.status_code == 200
        slugs = sorted(rt["slug"] for rt in resp.json()["reward_types"])
        assert slugs == ["multiball", "wizard-mode"]

        resp = _patch(client, pm.slug, {"reward_types": []})
        assert resp.status_code == 200
        assert resp.json()["reward_types"] == []


# ---------------------------------------------------------------------------
# Gameplay features (with count)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGameplayFeatures:
    def test_add_with_count(self, client, user, pm, gameplay_features):
        client.force_login(user)
        resp = _patch(
            client,
            pm.slug,
            {"gameplay_features": [{"slug": "ramps", "count": 3}]},
        )
        assert resp.status_code == 200
        features = resp.json()["gameplay_features"]
        assert len(features) == 1
        assert features[0]["slug"] == "ramps"
        assert features[0]["count"] == 3

    def test_add_without_count(self, client, user, pm, gameplay_features):
        client.force_login(user)
        resp = _patch(
            client,
            pm.slug,
            {"gameplay_features": [{"slug": "loops"}]},
        )
        assert resp.status_code == 200
        features = resp.json()["gameplay_features"]
        assert len(features) == 1
        assert features[0]["slug"] == "loops"
        assert features[0]["count"] is None

    def test_update_count(self, client, user, pm, gameplay_features):
        client.force_login(user)
        _patch(
            client,
            pm.slug,
            {"gameplay_features": [{"slug": "pop-bumpers", "count": 2}]},
        )
        resp = _patch(
            client,
            pm.slug,
            {"gameplay_features": [{"slug": "pop-bumpers", "count": 3}]},
        )
        assert resp.status_code == 200
        features = resp.json()["gameplay_features"]
        assert features[0]["count"] == 3

    def test_remove_feature(self, client, user, pm, gameplay_features):
        client.force_login(user)
        _patch(
            client,
            pm.slug,
            {
                "gameplay_features": [
                    {"slug": "ramps", "count": 2},
                    {"slug": "loops"},
                ]
            },
        )
        resp = _patch(
            client,
            pm.slug,
            {"gameplay_features": [{"slug": "ramps", "count": 2}]},
        )
        assert resp.status_code == 200
        slugs = [f["slug"] for f in resp.json()["gameplay_features"]]
        assert slugs == ["ramps"]

    def test_invalid_slug_returns_422(self, client, user, pm):
        client.force_login(user)
        resp = _patch(
            client,
            pm.slug,
            {"gameplay_features": [{"slug": "nonexistent"}]},
        )
        assert resp.status_code == 422

    def test_duplicate_slugs_returns_422(self, client, user, pm, gameplay_features):
        client.force_login(user)
        resp = _patch(
            client,
            pm.slug,
            {
                "gameplay_features": [
                    {"slug": "ramps", "count": 1},
                    {"slug": "ramps", "count": 2},
                ]
            },
        )
        assert resp.status_code == 422

    def test_zero_count_returns_422(self, client, user, pm, gameplay_features):
        client.force_login(user)
        resp = _patch(
            client,
            pm.slug,
            {"gameplay_features": [{"slug": "ramps", "count": 0}]},
        )
        assert resp.status_code == 422

    def test_negative_count_returns_422(self, client, user, pm, gameplay_features):
        client.force_login(user)
        resp = _patch(
            client,
            pm.slug,
            {"gameplay_features": [{"slug": "ramps", "count": -1}]},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Abbreviations
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAbbreviations:
    def test_add_abbreviations(self, client, user, pm):
        client.force_login(user)
        resp = _patch(client, pm.slug, {"abbreviations": ["MM", "MMR"]})
        assert resp.status_code == 200
        assert sorted(resp.json()["abbreviations"]) == ["MM", "MMR"]

    def test_remove_abbreviations(self, client, user, pm):
        client.force_login(user)
        _patch(client, pm.slug, {"abbreviations": ["MM", "MMR"]})
        resp = _patch(client, pm.slug, {"abbreviations": ["MM"]})
        assert resp.status_code == 200
        assert resp.json()["abbreviations"] == ["MM"]

    def test_clear_abbreviations(self, client, user, pm):
        client.force_login(user)
        _patch(client, pm.slug, {"abbreviations": ["MM"]})
        resp = _patch(client, pm.slug, {"abbreviations": []})
        assert resp.status_code == 200
        assert resp.json()["abbreviations"] == []

    def test_deduplication(self, client, user, pm):
        client.force_login(user)
        resp = _patch(client, pm.slug, {"abbreviations": ["MM", "MM", "mm"]})
        assert resp.status_code == 200
        # "mm" is a different string (case-sensitive dedup)
        assert len(resp.json()["abbreviations"]) <= 2


# ---------------------------------------------------------------------------
# Combined edits
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCombinedEdits:
    def test_scalar_and_relationships_share_one_changeset(
        self, client, user, pm, themes, gameplay_features, people, credit_roles
    ):
        client.force_login(user)
        resp = _patch(
            client,
            pm.slug,
            {
                "fields": {"year": 1998},
                "themes": ["medieval"],
                "gameplay_features": [{"slug": "ramps", "count": 2}],
                "credits": [{"person_slug": "pat-lawlor", "role": "design"}],
                "abbreviations": ["MM"],
                "note": "Full edit",
            },
        )
        assert resp.status_code == 200

        assert ChangeSet.objects.count() == 1
        cs = ChangeSet.objects.first()
        assert cs.note == "Full edit"
        field_names = set(cs.claims.values_list("field_name", flat=True))
        assert "year" in field_names
        assert "theme" in field_names
        assert "gameplay_feature" in field_names
        assert "credit" in field_names
        assert "abbreviation" in field_names

    def test_no_changes_returns_422(self, client, user, pm):
        client.force_login(user)
        resp = _patch(client, pm.slug, {})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Credits
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCredits:
    def test_add_credits(self, client, user, pm, people, credit_roles):
        client.force_login(user)
        resp = _patch(
            client,
            pm.slug,
            {
                "credits": [
                    {"person_slug": "pat-lawlor", "role": "design"},
                    {"person_slug": "greg-freres", "role": "art"},
                ]
            },
        )
        assert resp.status_code == 200
        credits = resp.json()["credits"]
        assert len(credits) == 2
        persons = sorted(c["person"]["slug"] for c in credits)
        assert persons == ["greg-freres", "pat-lawlor"]

    def test_remove_credit(self, client, user, pm, people, credit_roles):
        client.force_login(user)
        _patch(
            client,
            pm.slug,
            {
                "credits": [
                    {"person_slug": "pat-lawlor", "role": "design"},
                    {"person_slug": "greg-freres", "role": "art"},
                ]
            },
        )
        resp = _patch(
            client,
            pm.slug,
            {"credits": [{"person_slug": "pat-lawlor", "role": "design"}]},
        )
        assert resp.status_code == 200
        assert len(resp.json()["credits"]) == 1

    def test_replace_credits(self, client, user, pm, people, credit_roles):
        client.force_login(user)
        _patch(
            client,
            pm.slug,
            {"credits": [{"person_slug": "pat-lawlor", "role": "design"}]},
        )
        resp = _patch(
            client,
            pm.slug,
            {"credits": [{"person_slug": "john-youssi", "role": "software"}]},
        )
        assert resp.status_code == 200
        credits = resp.json()["credits"]
        assert len(credits) == 1
        assert credits[0]["person"]["slug"] == "john-youssi"
        assert credits[0]["role"] == "software"

    def test_clear_credits(self, client, user, pm, people, credit_roles):
        client.force_login(user)
        _patch(
            client,
            pm.slug,
            {"credits": [{"person_slug": "pat-lawlor", "role": "design"}]},
        )
        resp = _patch(client, pm.slug, {"credits": []})
        assert resp.status_code == 200
        assert resp.json()["credits"] == []

    def test_duplicate_pair_returns_422(self, client, user, pm, people, credit_roles):
        client.force_login(user)
        resp = _patch(
            client,
            pm.slug,
            {
                "credits": [
                    {"person_slug": "pat-lawlor", "role": "design"},
                    {"person_slug": "pat-lawlor", "role": "design"},
                ]
            },
        )
        assert resp.status_code == 422

    def test_unknown_person_returns_422(self, client, user, pm, credit_roles):
        client.force_login(user)
        resp = _patch(
            client,
            pm.slug,
            {"credits": [{"person_slug": "nonexistent", "role": "design"}]},
        )
        assert resp.status_code == 422

    def test_unknown_role_returns_422(self, client, user, pm, people):
        client.force_login(user)
        resp = _patch(
            client,
            pm.slug,
            {"credits": [{"person_slug": "pat-lawlor", "role": "nonexistent"}]},
        )
        assert resp.status_code == 422

    def test_null_leaves_unchanged(self, client, user, pm, people, credit_roles):
        client.force_login(user)
        _patch(
            client,
            pm.slug,
            {"credits": [{"person_slug": "pat-lawlor", "role": "design"}]},
        )
        # PATCH with only a scalar field, credits=null (omitted)
        resp = _patch(client, pm.slug, {"fields": {"year": 1998}})
        assert resp.status_code == 200
        assert len(resp.json()["credits"]) == 1

    def test_same_person_different_roles_allowed(
        self, client, user, pm, people, credit_roles
    ):
        client.force_login(user)
        resp = _patch(
            client,
            pm.slug,
            {
                "credits": [
                    {"person_slug": "pat-lawlor", "role": "design"},
                    {"person_slug": "pat-lawlor", "role": "software"},
                ]
            },
        )
        assert resp.status_code == 200
        assert len(resp.json()["credits"]) == 2


# ---------------------------------------------------------------------------
# Edit options
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEditOptions:
    def test_includes_people_and_credit_roles(self, client, people, credit_roles):
        resp = client.get("/api/models/edit-options/")
        assert resp.status_code == 200
        data = resp.json()
        assert "people" in data
        assert "credit_roles" in data
        # Verify shape: each item has slug + label
        assert all("slug" in p and "label" in p for p in data["people"])
        assert all("slug" in r and "label" in r for r in data["credit_roles"])
        # Verify content
        people_slugs = {p["slug"] for p in data["people"]}
        assert "pat-lawlor" in people_slugs
        role_slugs = {r["slug"] for r in data["credit_roles"]}
        assert "design" in role_slugs
