"""Tests for series-title membership via claims in ingest_pinbase."""

import json
import os
import tempfile

import pytest
from django.core.management import call_command

from apps.catalog.models import Series, Title
from apps.provenance.models import Claim


def _write_json(export_dir, filename, entries):
    with open(os.path.join(export_dir, filename), "w") as f:
        json.dump(entries, f)


def _export_dir(series_entries, title_entries):
    d = tempfile.mkdtemp()
    _write_json(d, "series.json", series_entries)
    _write_json(d, "title.json", title_entries)
    return d


@pytest.mark.django_db
@pytest.mark.usefixtures("credit_roles")
class TestSeriesTitleClaims:
    def test_series_membership_creates_claim(self):
        """A title with series_slug should produce a series_title claim on the Series."""
        export_dir = _export_dir(
            series_entries=[{"slug": "eight-ball", "name": "Eight Ball"}],
            title_entries=[
                {
                    "opdb_group_id": "Gabc",
                    "slug": "eight-ball",
                    "name": "Eight Ball",
                    "series_slug": "eight-ball",
                }
            ],
        )

        call_command("ingest_pinbase", export_dir=export_dir)

        series = Series.objects.get(slug="eight-ball")
        title = Title.objects.get(slug="eight-ball")

        # Claim exists on the series.
        assert Claim.objects.filter(
            content_type__model="series",
            object_id=series.pk,
            field_name="series_title",
            is_active=True,
        ).exists()

        # Resolution materialized the M2M row.
        assert title in series.titles.all()

    def test_series_membership_is_idempotent(self):
        """Running ingest twice should not duplicate claims or M2M rows."""
        export_dir = _export_dir(
            series_entries=[{"slug": "eight-ball", "name": "Eight Ball"}],
            title_entries=[
                {
                    "opdb_group_id": "Gabc",
                    "slug": "eight-ball",
                    "name": "Eight Ball",
                    "series_slug": "eight-ball",
                }
            ],
        )

        call_command("ingest_pinbase", export_dir=export_dir)
        call_command("ingest_pinbase", export_dir=export_dir)

        series = Series.objects.get(slug="eight-ball")
        assert series.titles.count() == 1
        assert (
            Claim.objects.filter(
                content_type__model="series",
                object_id=series.pk,
                field_name="series_title",
                is_active=True,
            ).count()
            == 1
        )

    def test_title_removed_from_series_retracts_claim(self):
        """If a title's series_slug is removed in a subsequent ingest, the claim is retracted."""
        export_dir_with = _export_dir(
            series_entries=[{"slug": "eight-ball", "name": "Eight Ball"}],
            title_entries=[
                {
                    "opdb_group_id": "Gabc",
                    "slug": "eight-ball",
                    "name": "Eight Ball",
                    "series_slug": "eight-ball",
                }
            ],
        )
        export_dir_without = _export_dir(
            series_entries=[{"slug": "eight-ball", "name": "Eight Ball"}],
            title_entries=[
                {
                    "opdb_group_id": "Gabc",
                    "slug": "eight-ball",
                    "name": "Eight Ball",
                    # no series_slug
                }
            ],
        )

        call_command("ingest_pinbase", export_dir=export_dir_with)
        series = Series.objects.get(slug="eight-ball")
        assert series.titles.count() == 1

        call_command("ingest_pinbase", export_dir=export_dir_without)
        series.refresh_from_db()
        assert series.titles.count() == 0
        assert not Claim.objects.filter(
            content_type__model="series",
            object_id=series.pk,
            field_name="series_title",
            is_active=True,
        ).exists()

    def test_series_membership_survives_slug_rename(self):
        """A title that is renamed in the same run it joins a series must still be a member.

        If the series_title claim is built with the pre-rename slug, the resolver
        can't find the title after the slug update and silently drops the membership.
        """
        # First ingest: create the title without a curated slug or series membership.
        export_dir_initial = _export_dir(
            series_entries=[{"slug": "eight-ball", "name": "Eight Ball"}],
            title_entries=[
                {
                    "opdb_group_id": "Gabc",
                    "name": "Eight Ball",
                    # no slug — gets a generated one
                }
            ],
        )
        call_command("ingest_pinbase", export_dir=export_dir_initial)
        title = Title.objects.get(opdb_id="Gabc")
        generated_slug = title.slug  # e.g. "eight-ball" or "eight-ball-1"

        # Second ingest: provide the curated slug (triggering rename) and series membership
        # in the same run.
        export_dir_rename_and_join = _export_dir(
            series_entries=[{"slug": "eight-ball", "name": "Eight Ball"}],
            title_entries=[
                {
                    "opdb_group_id": "Gabc",
                    "slug": "eight-ball-title",  # curated slug — renames from generated_slug
                    "name": "Eight Ball",
                    "series_slug": "eight-ball",
                }
            ],
        )
        call_command("ingest_pinbase", export_dir=export_dir_rename_and_join)

        title.refresh_from_db()
        assert title.slug == "eight-ball-title", "slug rename did not apply"

        series = Series.objects.get(slug="eight-ball")
        assert title in series.titles.all(), (
            f"title with renamed slug {title.slug!r} (was {generated_slug!r}) "
            "is not in the series — claim was built with the stale pre-rename slug"
        )
