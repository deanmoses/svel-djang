"""Tests for Title.franchise FK via claims in ingest_pinbase."""

import json
import os
import tempfile

import pytest
from django.core.management import call_command

from apps.catalog.models import Franchise, Title
from apps.provenance.models import Claim


def _write_json(export_dir, filename, entries):
    with open(os.path.join(export_dir, filename), "w") as f:
        json.dump(entries, f)


def _export_dir(franchise_entries, title_entries):
    d = tempfile.mkdtemp()
    _write_json(d, "franchise.json", franchise_entries)
    _write_json(d, "title.json", title_entries)
    return d


@pytest.mark.django_db
@pytest.mark.usefixtures("credit_roles")
class TestTitleFranchiseClaims:
    def test_title_removed_from_franchise_retracts_claim(self):
        """If a title's franchise_slug is removed in a subsequent ingest, the claim is retracted."""
        export_dir_with = _export_dir(
            franchise_entries=[{"slug": "star-wars", "name": "Star Wars"}],
            title_entries=[
                {
                    "opdb_group_id": "Gabc",
                    "slug": "star-wars-ep1",
                    "name": "Star Wars Episode I",
                    "franchise_slug": "star-wars",
                }
            ],
        )
        export_dir_without = _export_dir(
            franchise_entries=[{"slug": "star-wars", "name": "Star Wars"}],
            title_entries=[
                {
                    "opdb_group_id": "Gabc",
                    "slug": "star-wars-ep1",
                    "name": "Star Wars Episode I",
                    # no franchise_slug
                }
            ],
        )

        call_command("ingest_pinbase", export_dir=export_dir_with)
        title = Title.objects.get(slug="star-wars-ep1")
        franchise = Franchise.objects.get(slug="star-wars")
        assert title.franchise_id == franchise.pk

        call_command("ingest_pinbase", export_dir=export_dir_without)
        title.refresh_from_db()
        assert title.franchise is None
        assert not Claim.objects.filter(
            content_type__model="title",
            object_id=title.pk,
            field_name="franchise",
            is_active=True,
        ).exists()
