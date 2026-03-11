"""Tests for the ingest_pinbase_signs command."""

import csv
import tempfile

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command

from apps.catalog.models import MachineModel, Title
from apps.provenance.models import Claim, Source


def _write_csv(rows: list[dict]) -> str:
    """Write rows to a temp CSV and return the path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="")
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    f.close()
    return f.name


@pytest.mark.django_db
class TestSignsTitleLookup:
    def test_description_hoisted_to_title_via_slug_claim(self, db):
        """Title description is hoisted when model→title claim uses slug."""
        title = Title.objects.create(
            name="Alien Poker", slug="alien-poker", opdb_id="ipdb:20"
        )
        mm = MachineModel.objects.create(
            name="Alien Poker", slug="alien-poker-model", ipdb_id=20
        )

        # Create a slug-based title claim (as all sources now emit).
        ct = ContentType.objects.get_for_model(MachineModel)
        source, _ = Source.objects.update_or_create(
            slug="ipdb",
            defaults={
                "name": "IPDB",
                "source_type": "database",
                "priority": 100,
            },
        )
        Claim.objects.bulk_assert_claims(
            source,
            [
                Claim(
                    content_type_id=ct.pk,
                    object_id=mm.pk,
                    field_name="title",
                    claim_key="title",
                    value="alien-poker",
                )
            ],
        )

        csv_path = _write_csv(
            [
                {
                    "IPDBid": "20",
                    "Title": "Alien Poker",
                    "Year": "",
                    "Month": "",
                    "Manufacturer": "",
                    "Address": "",
                    "Produced": "",
                    "MainText": "A classic 1980 solid-state pinball machine.",
                    "Sources/Notes": "",
                    "Heading1": "",
                    "Info1": "",
                    "Heading2": "",
                    "Info2": "",
                    "Heading3": "",
                    "Info3": "",
                }
            ]
        )

        call_command("ingest_pinbase_signs", csv=csv_path)

        # The MainText should be hoisted as a description claim on the Title.
        title_ct = ContentType.objects.get_for_model(Title)
        desc_claim = Claim.objects.get(
            content_type_id=title_ct.pk,
            object_id=title.pk,
            field_name="description",
            is_active=True,
        )
        assert desc_claim.value == "A classic 1980 solid-state pinball machine."
