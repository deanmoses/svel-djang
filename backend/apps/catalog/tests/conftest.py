import pytest
from django.test import Client

from apps.catalog.models import (
    CorporateEntity,
    CreditRole,
    MachineModel,
    Manufacturer,
    Person,
    TechnologyGeneration,
    Theme,
)
from apps.provenance.models import Source

SAMPLE_IMAGES = [
    {
        "primary": True,
        "type": "backglass",
        "urls": {
            "small": "https://img.opdb.org/sm.jpg",
            "medium": "https://img.opdb.org/md.jpg",
            "large": "https://img.opdb.org/lg.jpg",
        },
    }
]


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def source(db):
    return Source.objects.create(name="IPDB", source_type="database", priority=10)


@pytest.fixture
def manufacturer(db):
    return Manufacturer.objects.create(name="Williams")


@pytest.fixture
def stern(db):
    return Manufacturer.objects.create(name="Stern")


_CREDIT_ROLES = [
    {"slug": "animation", "name": "Dots/Animation", "display_order": 40},
    {"slug": "art", "name": "Art", "display_order": 30},
    {"slug": "concept", "name": "Concept", "display_order": 20},
    {"slug": "design", "name": "Design", "display_order": 10},
    {"slug": "mechanics", "name": "Mechanics", "display_order": 50},
    {"slug": "music", "name": "Music", "display_order": 60},
    {"slug": "other", "name": "Other", "display_order": 100},
    {"slug": "software", "name": "Software", "display_order": 90},
    {"slug": "sound", "name": "Sound", "display_order": 70},
    {"slug": "voice", "name": "Voice", "display_order": 80},
]


@pytest.fixture
def credit_roles(db):
    """Seed all credit roles for tests that need them."""
    return CreditRole.objects.bulk_create(
        [CreditRole(**entry) for entry in _CREDIT_ROLES],
        update_conflicts=True,
        unique_fields=["slug"],
        update_fields=["name", "display_order"],
    )


@pytest.fixture
def person(db):
    return Person.objects.create(name="Pat Lawlor")


@pytest.fixture
def solid_state(db):
    return TechnologyGeneration.objects.create(name="Solid State", slug="solid-state")


@pytest.fixture
def williams_entity(db, manufacturer):
    return CorporateEntity.objects.create(
        name="Williams Electronics",
        slug="williams-electronics",
        manufacturer=manufacturer,
    )


@pytest.fixture
def stern_entity(db, stern):
    return CorporateEntity.objects.create(
        name="Stern Pinball, Inc.",
        slug="stern-pinball-inc",
        manufacturer=stern,
    )


@pytest.fixture
def machine_model(db, williams_entity, solid_state):
    pm = MachineModel.objects.create(
        name="Medieval Madness",
        corporate_entity=williams_entity,
        year=1997,
        technology_generation=solid_state,
    )
    t = Theme.objects.create(name="Medieval", slug="medieval")
    pm.themes.add(t)
    return pm


@pytest.fixture
def another_model(db, stern_entity, solid_state):
    return MachineModel.objects.create(
        name="The Mandalorian",
        corporate_entity=stern_entity,
        year=2021,
        technology_generation=solid_state,
    )
