import pytest
from django.test import Client

from apps.catalog.models import (
    CorporateEntity,
    CorporateEntityLocation,
    CreditRole,
    GameplayFeature,
    Location,
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


_IPDB_NARRATIVE_FEATURE_SLUGS = [
    "multiball",
    "kickback",
    "magna-save",
    "ball-save",
    "skill-shot",
    "multi-level-playfield",
    "head-to-head",
]


@pytest.fixture
def ipdb_locations(db):
    """Create Location records and pinbase-curated CE+CEL rows for the IPDB fixture.

    IPDB validation requires CEs to already have pinbase-curated locations.
    The fixture covers the three manufacturers in ipdb_sample.json:
    Gottlieb (93) and Williams (351) in Chicago, Bally/Midway (349) in Franklin Park.
    """
    usa = Location.objects.create(
        location_path="usa", slug="usa", name="USA", location_type="country"
    )
    il = Location.objects.create(
        location_path="usa/il",
        slug="il",
        name="Illinois",
        location_type="state",
        parent=usa,
    )
    chicago = Location.objects.create(
        location_path="usa/il/chicago",
        slug="chicago",
        name="Chicago",
        location_type="city",
        parent=il,
    )
    franklin_park = Location.objects.create(
        location_path="usa/il/franklin-park",
        slug="franklin-park",
        name="Franklin Park",
        location_type="city",
        parent=il,
    )

    def _make_ce(name, slug, ipdb_id, location):
        mfr = Manufacturer.objects.create(name=name, slug=slug)
        ce = CorporateEntity.objects.create(
            name=name,
            slug=slug,
            manufacturer=mfr,
            ipdb_manufacturer_id=ipdb_id,
        )
        CorporateEntityLocation.objects.create(corporate_entity=ce, location=location)
        return ce

    _make_ce("D. Gottlieb & Company", "d-gottlieb-co", 93, chicago)
    _make_ce("Midway Manufacturing Company", "midway-manufacturing", 349, franklin_park)
    _make_ce("Williams Electronic Games", "williams-electronic-games", 351, chicago)


@pytest.fixture
def ipdb_narrative_features(db):
    """Create GameplayFeature records for IPDB narrative pattern slugs.

    Required by ingest_ipdb, which validates these slugs exist at startup.
    """
    return GameplayFeature.objects.bulk_create(
        [GameplayFeature(slug=s, name=s) for s in _IPDB_NARRATIVE_FEATURE_SLUGS],
        update_conflicts=True,
        unique_fields=["slug"],
        update_fields=["name"],
    )


@pytest.fixture
def another_model(db, stern_entity, solid_state):
    return MachineModel.objects.create(
        name="The Mandalorian",
        corporate_entity=stern_entity,
        year=2021,
        technology_generation=solid_state,
    )
