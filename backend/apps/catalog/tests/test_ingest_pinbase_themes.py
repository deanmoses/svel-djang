"""Tests for _ingest_themes() and _ingest_gameplay_features() in ingest_pinbase."""

import json
import os
import tempfile

import pytest
from django.core.management import call_command

from apps.catalog.models import GameplayFeature, GameplayFeatureAlias, Theme, ThemeAlias


def _write_json(filename, entries):
    """Write entries to a temp export dir and return the dir path."""
    export_dir = tempfile.mkdtemp()
    with open(os.path.join(export_dir, filename), "w") as f:
        json.dump(entries, f)
    return export_dir


@pytest.mark.django_db
class TestIngestThemes:
    def test_creates_theme_with_claims(self):
        export_dir = _write_json(
            "theme.json",
            [{"slug": "horror", "name": "Horror", "description": "Scary stuff"}],
        )

        call_command("ingest_pinbase", export_dir=export_dir)

        theme = Theme.objects.get(slug="horror")
        assert theme.name == "Horror"
        assert theme.description == "Scary stuff"

        # Verify claims exist.
        assert theme.claims.filter(field_name="name", is_active=True).exists()
        assert theme.claims.filter(field_name="description", is_active=True).exists()

    def test_creates_parents(self):
        export_dir = _write_json(
            "theme.json",
            [
                {"slug": "horror", "name": "Horror", "parents": []},
                {"slug": "vampires", "name": "Vampires", "parents": ["Horror"]},
            ],
        )

        call_command("ingest_pinbase", export_dir=export_dir)

        vampires = Theme.objects.get(slug="vampires")
        assert list(vampires.parents.values_list("slug", flat=True)) == ["horror"]

    def test_creates_aliases(self):
        export_dir = _write_json(
            "theme.json",
            [{"slug": "horror", "name": "Horror", "aliases": ["Scary", "Spooky"]}],
        )

        call_command("ingest_pinbase", export_dir=export_dir)

        assert ThemeAlias.objects.filter(theme__slug="horror").count() == 2

    def test_idempotent(self):
        export_dir = _write_json(
            "theme.json",
            [{"slug": "horror", "name": "Horror"}],
        )

        call_command("ingest_pinbase", export_dir=export_dir)
        call_command("ingest_pinbase", export_dir=export_dir)

        assert Theme.objects.filter(slug="horror").count() == 1

    def test_updates_name(self):
        Theme.objects.create(slug="horror", name="Old Name")
        export_dir = _write_json(
            "theme.json",
            [{"slug": "horror", "name": "Horror"}],
        )

        call_command("ingest_pinbase", export_dir=export_dir)

        theme = Theme.objects.get(slug="horror")
        assert theme.name == "Horror"


@pytest.mark.django_db
class TestIngestGameplayFeatures:
    def test_creates_feature_with_claims(self):
        export_dir = _write_json(
            "gameplay_feature.json",
            [
                {
                    "slug": "multiball",
                    "name": "Multiball",
                    "description": "Multiple balls",
                }
            ],
        )

        call_command("ingest_pinbase", export_dir=export_dir)

        feature = GameplayFeature.objects.get(slug="multiball")
        assert feature.name == "Multiball"
        assert feature.description == "Multiple balls"
        assert feature.claims.filter(field_name="name", is_active=True).exists()

    def test_creates_parents(self):
        export_dir = _write_json(
            "gameplay_feature.json",
            [
                {"slug": "targets", "name": "Targets"},
                {
                    "slug": "drop-targets",
                    "name": "Drop Targets",
                    "is_type_of": ["targets"],
                },
            ],
        )

        call_command("ingest_pinbase", export_dir=export_dir)

        drop = GameplayFeature.objects.get(slug="drop-targets")
        assert list(drop.parents.values_list("slug", flat=True)) == ["targets"]

    def test_creates_aliases(self):
        export_dir = _write_json(
            "gameplay_feature.json",
            [{"slug": "multiball", "name": "Multiball", "aliases": ["Multi-Ball"]}],
        )

        call_command("ingest_pinbase", export_dir=export_dir)

        assert (
            GameplayFeatureAlias.objects.filter(feature__slug="multiball").count() == 1
        )

    def test_idempotent(self):
        export_dir = _write_json(
            "gameplay_feature.json",
            [{"slug": "multiball", "name": "Multiball"}],
        )

        call_command("ingest_pinbase", export_dir=export_dir)
        call_command("ingest_pinbase", export_dir=export_dir)

        assert GameplayFeature.objects.filter(slug="multiball").count() == 1
