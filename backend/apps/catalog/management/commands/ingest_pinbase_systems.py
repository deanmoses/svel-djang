"""Seed System records from data/systems.json.

Creates or updates System records with editorial slugs, names, and
manufacturer FKs. Runs after ingest_pinbase_manufacturers so manufacturer
lookups by slug are reliable.

The mpu_strings field is used only for IPDB ingestion mapping and is
not stored on the System model.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from apps.catalog.models import Manufacturer, System
from apps.provenance.models import Claim, Source

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).parents[5] / "data" / "systems.json"


class Command(BaseCommand):
    help = "Seed System records from data/systems.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(DEFAULT_PATH),
            help="Path to systems.json seed file.",
        )

    def handle(self, *args, **options):
        path = options["path"]
        with open(path) as f:
            entries = json.load(f)

        # Pre-fetch manufacturer lookup by slug.
        mfr_by_slug: dict[str, Manufacturer] = {
            m.slug: m for m in Manufacturer.objects.all()
        }

        # Pre-fetch existing slugs for counts.
        existing_slugs = set(System.objects.values_list("slug", flat=True))

        missing_mfr: list[str] = []

        # Build instances from JSON.
        objs = []
        for entry in entries:
            slug = entry["slug"]
            name = entry["name"]
            description = entry.get("description", "")
            mfr_slug = entry.get("manufacturer")

            mfr = None
            if mfr_slug:
                mfr = mfr_by_slug.get(mfr_slug)
                if mfr is None:
                    missing_mfr.append(mfr_slug)
                    logger.warning(
                        "Manufacturer slug %r not found for system %r", mfr_slug, slug
                    )

            objs.append(
                System(slug=slug, name=name, description=description, manufacturer=mfr)
            )

        # Bulk upsert: single INSERT ... ON CONFLICT DO UPDATE.
        objs = System.objects.bulk_create(
            objs,
            update_conflicts=True,
            unique_fields=["slug"],
            update_fields=["name", "description", "manufacturer"],
        )

        created = sum(1 for o in objs if o.slug not in existing_slugs)
        updated = len(objs) - created

        self.stdout.write(f"  Systems seed: {created} created, {updated} updated")
        if missing_mfr:
            self.stderr.write(
                f"  Warning: {len(missing_mfr)} missing manufacturer slug(s): "
                + ", ".join(sorted(set(missing_mfr)))
            )

        # Assert claims for name and description.
        source, _ = Source.objects.get_or_create(
            slug="pinbase",
            defaults={
                "name": "Pinbase",
                "source_type": Source.SourceType.EDITORIAL,
                "priority": 300,
                "description": "Pinbase curated data.",
            },
        )
        ct_id = ContentType.objects.get_for_model(System).pk

        pending_claims: list[Claim] = []
        for obj, entry in zip(objs, entries):
            for field in ("name", "description"):
                value = entry.get(field, "")
                if value:
                    pending_claims.append(
                        Claim(
                            content_type_id=ct_id,
                            object_id=obj.pk,
                            field_name=field,
                            value=value,
                        )
                    )

        if pending_claims:
            claim_stats = Claim.objects.bulk_assert_claims(source, pending_claims)
            self.stdout.write(
                f"  Claims: {claim_stats['created']} created, "
                f"{claim_stats['unchanged']} unchanged"
            )

        self.stdout.write(self.style.SUCCESS("System seed ingestion complete."))
