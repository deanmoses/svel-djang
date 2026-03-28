"""Coverage for newer PATCH claims endpoints added after the initial edit work."""

from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model

from apps.catalog.models import (
    Cabinet,
    Credit,
    CreditRole,
    DisplaySubtype,
    DisplayType,
    Franchise,
    GameFormat,
    MachineModel,
    Person,
    RewardType,
    Series,
    System,
    Tag,
    TechnologyGeneration,
    TechnologySubgeneration,
    Title,
)
from apps.provenance.models import ChangeSet, Claim, Source

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="editor", password="testpass")  # pragma: allowlist secret  # fmt: skip


def _patch(client, path: str, body: dict):
    return client.patch(
        path,
        data=json.dumps(body),
        content_type="application/json",
    )


def _create_franchise():
    return Franchise.objects.create(name="Star Trek")


def _create_series():
    return Series.objects.create(name="Eight Ball")


def _create_system():
    return System.objects.create(name="WPC-95")


def _create_technology_generation():
    return TechnologyGeneration.objects.create(name="Solid State")


def _create_technology_subgeneration():
    gen = TechnologyGeneration.objects.create(name="Electromechanical")
    return TechnologySubgeneration.objects.create(
        name="Late EM",
        technology_generation=gen,
    )


def _create_display_type():
    return DisplayType.objects.create(name="DMD")


def _create_display_subtype():
    display_type = DisplayType.objects.create(name="LCD")
    return DisplaySubtype.objects.create(
        name="HD LCD",
        display_type=display_type,
    )


def _create_cabinet():
    return Cabinet.objects.create(name="Widebody")


def _create_game_format():
    return GameFormat.objects.create(name="Pinball")


def _create_reward_type():
    return RewardType.objects.create(name="Replay")


def _create_tag():
    return Tag.objects.create(name="Prototype")


PATCH_CASES = [
    pytest.param(
        "/api/franchises/{slug}/claims/",
        _create_franchise,
        "description",
        "Updated franchise copy",
        "franchises",
        id="franchise",
    ),
    pytest.param(
        "/api/series/{slug}/claims/",
        _create_series,
        "description",
        "Updated series copy",
        "series",
        id="series",
    ),
    pytest.param(
        "/api/systems/{slug}/claims/",
        _create_system,
        "description",
        "Updated system copy",
        "systems",
        id="system",
    ),
    pytest.param(
        "/api/technology-generations/{slug}/claims/",
        _create_technology_generation,
        "description",
        "Updated technology generation copy",
        "technology-generations",
        id="technology-generation",
    ),
    pytest.param(
        "/api/technology-subgenerations/{slug}/claims/",
        _create_technology_subgeneration,
        "description",
        "Updated technology subgeneration copy",
        "technology-subgenerations",
        id="technology-subgeneration",
    ),
    pytest.param(
        "/api/display-types/{slug}/claims/",
        _create_display_type,
        "description",
        "Updated display type copy",
        "display-types",
        id="display-type",
    ),
    pytest.param(
        "/api/display-subtypes/{slug}/claims/",
        _create_display_subtype,
        "description",
        "Updated display subtype copy",
        "display-subtypes",
        id="display-subtype",
    ),
    pytest.param(
        "/api/cabinets/{slug}/claims/",
        _create_cabinet,
        "description",
        "Updated cabinet copy",
        "cabinets",
        id="cabinet",
    ),
    pytest.param(
        "/api/game-formats/{slug}/claims/",
        _create_game_format,
        "description",
        "Updated game format copy",
        "game-formats",
        id="game-format",
    ),
    pytest.param(
        "/api/reward-types/{slug}/claims/",
        _create_reward_type,
        "description",
        "Updated reward type copy",
        "reward-types",
        id="reward-type",
    ),
    pytest.param(
        "/api/tags/{slug}/claims/",
        _create_tag,
        "description",
        "Updated tag copy",
        "tags",
        id="tag",
    ),
]


@pytest.mark.django_db
class TestAdditionalPatchClaimEndpoints:
    @pytest.mark.parametrize(
        ("path_template", "factory", "field_name", "field_value", "resource_name"),
        PATCH_CASES,
    )
    def test_anonymous_gets_401(
        self, client, path_template, factory, field_name, field_value, resource_name
    ):
        entity = factory()
        resp = _patch(
            client,
            path_template.format(slug=entity.slug),
            {"fields": {field_name: field_value}},
        )
        assert resp.status_code in (401, 403), resource_name

    def test_empty_fields_returns_422(self, client, user):
        entity = _create_franchise()
        client.force_login(user)
        resp = _patch(
            client,
            f"/api/franchises/{entity.slug}/claims/",
            {"fields": {}},
        )
        assert resp.status_code == 422

    def test_unknown_field_returns_422(self, client, user):
        entity = _create_reward_type()
        client.force_login(user)
        resp = _patch(
            client,
            f"/api/reward-types/{entity.slug}/claims/",
            {"fields": {"slug": "bad"}},
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize(
        ("path_template", "factory", "field_name", "field_value", "resource_name"),
        PATCH_CASES,
    )
    def test_creates_claim_changeset_and_activity(
        self,
        client,
        user,
        path_template,
        factory,
        field_name,
        field_value,
        resource_name,
    ):
        entity = factory()
        client.force_login(user)

        resp = _patch(
            client,
            path_template.format(slug=entity.slug),
            {"fields": {field_name: field_value}},
        )

        assert resp.status_code == 200, resource_name
        data = resp.json()
        assert data["description"]["text"] == field_value
        assert any(
            claim["field_name"] == field_name and claim["is_winner"]
            for claim in data["activity"]
        ), resource_name

        entity.refresh_from_db()
        assert entity.description == field_value

        claim = entity.claims.get(user=user, field_name=field_name, is_active=True)
        assert claim.value == field_value

        assert ChangeSet.objects.count() == 1
        changeset = ChangeSet.objects.get()
        assert changeset.user == user
        assert changeset.claims.count() == 1


@pytest.mark.django_db
class TestPatchSeriesResponseShape:
    def test_patch_preserves_titles_and_credits(
        self, client, user, williams_entity, credit_roles
    ):
        series = Series.objects.create(name="Eight Ball")
        title = Title.objects.create(name="Eight Ball Deluxe")
        series.titles.add(title)
        MachineModel.objects.create(
            name="Eight Ball Deluxe",
            title=title,
            corporate_entity=williams_entity,
            year=1981,
        )
        person = Person.objects.create(name="George Christian")
        role = CreditRole.objects.get(slug="design")
        Credit.objects.create(series=series, person=person, role=role)

        client.force_login(user)
        resp = _patch(
            client,
            f"/api/series/{series.slug}/claims/",
            {"fields": {"description": "Updated series copy"}},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["titles"] == [
            {
                "name": title.name,
                "slug": title.slug,
                "abbreviations": [],
                "machine_count": 1,
                "manufacturer_name": "Williams",
                "year": 1981,
                "thumbnail_url": None,
            }
        ]
        assert data["credits"] == [
            {
                "person": {"name": person.name, "slug": person.slug},
                "role": role.slug,
                "role_display": role.name,
                "role_sort_order": role.display_order,
            }
        ]


@pytest.mark.django_db
class TestPatchSystemResponseShape:
    def test_patch_preserves_manufacturer_titles_and_siblings(
        self, client, user, manufacturer, williams_entity, solid_state
    ):
        source = Source.objects.create(
            name="Test", slug="test", source_type="editorial", priority=100
        )
        system = System.objects.create(name="WPC-95", manufacturer=manufacturer)
        sibling = System.objects.create(name="System 11", manufacturer=manufacturer)
        # Manufacturer is now claim-controlled on System — assert claims so
        # resolution preserves the FK when description is PATCHed.
        Claim.objects.assert_claim(
            system, "manufacturer", manufacturer.slug, source=source
        )
        Claim.objects.assert_claim(
            sibling, "manufacturer", manufacturer.slug, source=source
        )
        title = Title.objects.create(name="Medieval Madness")
        MachineModel.objects.create(
            name="Medieval Madness",
            title=title,
            system=system,
            corporate_entity=williams_entity,
            technology_generation=solid_state,
            year=1997,
        )

        client.force_login(user)
        resp = _patch(
            client,
            f"/api/systems/{system.slug}/claims/",
            {"fields": {"description": "Updated system copy"}},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["manufacturer"] == {
            "name": manufacturer.name,
            "slug": manufacturer.slug,
        }
        assert data["titles"] == [
            {
                "name": title.name,
                "slug": title.slug,
                "year": 1997,
                "manufacturer_name": manufacturer.name,
                "thumbnail_url": None,
            }
        ]
        assert data["sibling_systems"] == [{"name": sibling.name, "slug": sibling.slug}]


@pytest.mark.django_db
class TestPatchRewardTypeResponseShape:
    def test_patch_preserves_machine_list(
        self, client, user, williams_entity, solid_state
    ):
        reward_type = RewardType.objects.create(name="Replay")
        title = Title.objects.create(name="Firepower")
        model = MachineModel.objects.create(
            name="Firepower",
            title=title,
            corporate_entity=williams_entity,
            technology_generation=solid_state,
            year=1980,
        )
        model.reward_types.add(reward_type)

        client.force_login(user)
        resp = _patch(
            client,
            f"/api/reward-types/{reward_type.slug}/claims/",
            {"fields": {"description": "Updated reward type copy"}},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["machines"] == [
            {
                "name": model.name,
                "slug": model.slug,
                "year": 1980,
                "manufacturer": {"name": "Williams", "slug": "williams"},
                "technology_generation_name": "Solid State",
                "thumbnail_url": None,
                "variants": [],
            }
        ]


UNIQUE_NAME_CASES = [
    pytest.param(
        "/api/franchises/{slug}/claims/",
        _create_franchise,
        "Indiana Jones",
        id="franchise",
    ),
    pytest.param(
        "/api/systems/{slug}/claims/",
        _create_system,
        "System 11",
        id="system",
    ),
    pytest.param(
        "/api/technology-generations/{slug}/claims/",
        _create_technology_generation,
        "Electromechanical",
        id="technology-generation",
    ),
    pytest.param(
        "/api/display-types/{slug}/claims/",
        _create_display_type,
        "LCD",
        id="display-type",
    ),
    pytest.param(
        "/api/cabinets/{slug}/claims/",
        _create_cabinet,
        "Standard",
        id="cabinet",
    ),
    pytest.param(
        "/api/game-formats/{slug}/claims/",
        _create_game_format,
        "Shuffle Alley",
        id="game-format",
    ),
    pytest.param(
        "/api/reward-types/{slug}/claims/",
        _create_reward_type,
        "Extra Ball",
        id="reward-type",
    ),
    pytest.param("/api/tags/{slug}/claims/", _create_tag, "Widebody", id="tag"),
]


@pytest.mark.django_db
class TestUniqueNameValidation:
    @pytest.mark.parametrize(
        ("path_template", "factory", "other_name"), UNIQUE_NAME_CASES
    )
    def test_duplicate_name_returns_422(
        self, client, user, path_template, factory, other_name
    ):
        entity = factory()
        entity.__class__.objects.create(name=other_name)

        client.force_login(user)
        resp = _patch(
            client,
            path_template.format(slug=entity.slug),
            {"fields": {"name": other_name}},
        )

        assert resp.status_code == 422
        assert "unique" in resp.json()["detail"].lower()
        assert ChangeSet.objects.count() == 0


DISPLAY_ORDER_CASES = [
    pytest.param(
        "/api/technology-generations/{slug}/claims/",
        _create_technology_generation,
        id="technology-generation",
    ),
    pytest.param(
        "/api/technology-subgenerations/{slug}/claims/",
        _create_technology_subgeneration,
        id="technology-subgeneration",
    ),
    pytest.param(
        "/api/display-types/{slug}/claims/",
        _create_display_type,
        id="display-type",
    ),
    pytest.param(
        "/api/display-subtypes/{slug}/claims/",
        _create_display_subtype,
        id="display-subtype",
    ),
    pytest.param("/api/cabinets/{slug}/claims/", _create_cabinet, id="cabinet"),
    pytest.param(
        "/api/game-formats/{slug}/claims/",
        _create_game_format,
        id="game-format",
    ),
    pytest.param(
        "/api/reward-types/{slug}/claims/",
        _create_reward_type,
        id="reward-type",
    ),
    pytest.param("/api/tags/{slug}/claims/", _create_tag, id="tag"),
]


@pytest.mark.django_db
class TestTaxonomyDisplayOrderEditing:
    @pytest.mark.parametrize(("path_template", "factory"), DISPLAY_ORDER_CASES)
    def test_display_order_edit_persists_and_returns_integer(
        self, client, user, path_template, factory
    ):
        entity = factory()

        client.force_login(user)
        resp = _patch(
            client,
            path_template.format(slug=entity.slug),
            {"fields": {"display_order": 7}},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["display_order"] == 7

        entity.refresh_from_db()
        assert entity.display_order == 7
        claim = entity.claims.get(user=user, field_name="display_order", is_active=True)
        assert claim.value == 7
