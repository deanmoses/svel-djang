"""Tests for _ingest_locations() in ingest_pinbase.

Written before implementation (TDD). Tests verify:
- Location rows are created with correct fields
- Parent links are wired correctly (slug-based hierarchy)
- Aliases are materialized from claims
- Re-running is idempotent (update_conflicts=True)
"""

import json

import pytest
from django.core.management import call_command

from apps.catalog.models import Location, LocationAlias
from apps.provenance.models import Source

PINBASE_SOURCE_SLUG = "pinbase"


@pytest.fixture
def pinbase_source(db):
    return Source.objects.create(
        slug=PINBASE_SOURCE_SLUG,
        name="Pinbase",
        source_type="editorial",
        priority=300,
    )


def _run_ingest(tmp_path, location_data, other_files=None):
    """Write location.json (and any other needed stubs) to a temp dir and run ingest."""
    (tmp_path / "location.json").write_text(json.dumps(location_data))

    # Stub out files the command tries to load but we don't need for location tests.
    stub_files = [
        "manufacturer.json",
        "corporate_entity.json",
        "machine_model.json",
        "theme.json",
        "gameplay_feature.json",
        "reward_type.json",
        "person.json",
        "credit_role.json",
        "tag.json",
        "technology_generation.json",
        "technology_subgeneration.json",
        "display_type.json",
        "display_subtype.json",
        "cabinet.json",
        "game_format.json",
        "series.json",
        "system.json",
        "franchise.json",
        "title.json",
    ]
    for fname in stub_files:
        if not (tmp_path / fname).exists():
            (tmp_path / fname).write_text("[]")

    if other_files:
        for name, data in other_files.items():
            (tmp_path / name).write_text(json.dumps(data))

    call_command("ingest_pinbase", export_dir=str(tmp_path), verbosity=0)


SAMPLE_LOCATIONS = [
    {
        "location_path": "usa",
        "slug": "usa",
        "name": "USA",
        "type": "country",
        "code": "US",
        "divisions": ["state", "city"],
        "aliases": ["United States", "United States of America"],
    },
    {
        "location_path": "usa/il",
        "slug": "il",
        "name": "Illinois",
        "type": "state",
        "code": "IL",
        "aliases": [],
    },
    {
        "location_path": "usa/il/chicago",
        "slug": "chicago",
        "name": "Chicago",
        "type": "city",
        "aliases": ["Chi-town"],
    },
]


class TestIngestLocationsCreation:
    def test_creates_location_rows(self, db, pinbase_source, tmp_path):
        _run_ingest(tmp_path, SAMPLE_LOCATIONS)
        assert Location.objects.count() == 3

    def test_location_fields(self, db, pinbase_source, tmp_path):
        _run_ingest(tmp_path, SAMPLE_LOCATIONS)
        usa = Location.objects.get(location_path="usa")
        assert usa.name == "USA"
        assert usa.location_type == "country"
        assert usa.code == "US"
        assert usa.slug == "usa"

    def test_country_divisions(self, db, pinbase_source, tmp_path):
        _run_ingest(tmp_path, SAMPLE_LOCATIONS)
        usa = Location.objects.get(location_path="usa")
        assert usa.divisions == ["state", "city"]

    def test_non_country_no_divisions(self, db, pinbase_source, tmp_path):
        _run_ingest(tmp_path, SAMPLE_LOCATIONS)
        il = Location.objects.get(location_path="usa/il")
        assert il.divisions is None


class TestIngestLocationsParentLinks:
    def test_parent_of_state_is_country(self, db, pinbase_source, tmp_path):
        _run_ingest(tmp_path, SAMPLE_LOCATIONS)
        il = Location.objects.select_related("parent").get(location_path="usa/il")
        assert il.parent is not None
        assert il.parent.location_path == "usa"

    def test_parent_of_city_is_state(self, db, pinbase_source, tmp_path):
        _run_ingest(tmp_path, SAMPLE_LOCATIONS)
        chicago = Location.objects.select_related("parent").get(
            location_path="usa/il/chicago"
        )
        assert chicago.parent is not None
        assert chicago.parent.location_path == "usa/il"

    def test_country_has_no_parent(self, db, pinbase_source, tmp_path):
        _run_ingest(tmp_path, SAMPLE_LOCATIONS)
        usa = Location.objects.get(location_path="usa")
        assert usa.parent is None


class TestIngestLocationsAliases:
    def test_aliases_created(self, db, pinbase_source, tmp_path):
        _run_ingest(tmp_path, SAMPLE_LOCATIONS)
        usa = Location.objects.get(location_path="usa")
        alias_values = set(
            LocationAlias.objects.filter(location=usa).values_list("value", flat=True)
        )
        # _resolve_aliases stores lowercase alias_value but original-case display
        assert any("united states" in v.lower() for v in alias_values)

    def test_city_alias_created(self, db, pinbase_source, tmp_path):
        _run_ingest(tmp_path, SAMPLE_LOCATIONS)
        chicago = Location.objects.get(location_path="usa/il/chicago")
        alias_values = {
            a.value.lower() for a in LocationAlias.objects.filter(location=chicago)
        }
        assert "chi-town" in alias_values


class TestIngestLocationsIdempotency:
    def test_rerun_does_not_duplicate(self, db, pinbase_source, tmp_path):
        _run_ingest(tmp_path, SAMPLE_LOCATIONS)
        _run_ingest(tmp_path, SAMPLE_LOCATIONS)
        assert Location.objects.count() == 3
        assert Location.objects.filter(location_path="usa").count() == 1

    def test_rerun_updates_name(self, db, pinbase_source, tmp_path):
        _run_ingest(tmp_path, SAMPLE_LOCATIONS)
        updated = [
            {**SAMPLE_LOCATIONS[0], "name": "United States"},
            *SAMPLE_LOCATIONS[1:],
        ]
        _run_ingest(tmp_path, updated)
        usa = Location.objects.get(location_path="usa")
        assert usa.name == "United States"
