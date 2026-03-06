"""Seed manufacturer records from data/manufacturers.json.

Creates or updates Manufacturer records with editorial slugs and names.
Asserts editorial description claims at priority 300 so they win over
OPDB (200), IPDB (100), and Wikidata (75) during resolve_claims.

Runs before IPDB/OPDB ingest so those ingesters can match against
stable slugs.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from apps.catalog.models import Manufacturer
from apps.catalog.resolve import resolve_manufacturer
from apps.provenance.models import Claim, Source

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).parents[5] / "data" / "manufacturers.json"


class Command(BaseCommand):
    help = "Seed Manufacturer records from data/manufacturers.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(DEFAULT_PATH),
            help="Path to manufacturers.json seed file.",
        )

    def handle(self, *args, **options):
        path = options["path"]
        with open(path) as f:
            entries = json.load(f)

        source, _ = Source.objects.update_or_create(
            slug="editorial",
            defaults={
                "name": "Editorial",
                "source_type": Source.SourceType.EDITORIAL,
                "priority": 300,
            },
        )
        ct_id = ContentType.objects.get_for_model(Manufacturer).pk

        # Pre-fetch existing slugs for created/updated counts.
        existing_slugs = set(Manufacturer.objects.values_list("slug", flat=True))

        # Build instances from JSON.
        objs = [Manufacturer(slug=e["slug"], name=e["name"]) for e in entries]

        # Bulk upsert: single INSERT ... ON CONFLICT DO UPDATE.
        objs = Manufacturer.objects.bulk_create(
            objs,
            update_conflicts=True,
            unique_fields=["slug"],
            update_fields=["name"],
        )

        created = sum(1 for o in objs if o.slug not in existing_slugs)
        updated = len(objs) - created

        self.stdout.write(f"  Manufacturers seed: {created} created, {updated} updated")

        # Assert claims.
        pending_claims: list[Claim] = []
        for obj, entry in zip(objs, entries):
            pending_claims.append(
                Claim(
                    content_type_id=ct_id,
                    object_id=obj.pk,
                    field_name="name",
                    value=obj.name,
                )
            )
            description = entry.get("description", "")
            if description:
                pending_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=obj.pk,
                        field_name="description",
                        value=description,
                    )
                )

        if pending_claims:
            stats = Claim.objects.bulk_assert_claims(source, pending_claims)
            self.stdout.write(
                f"  Claims: {stats['unchanged']} unchanged, "
                f"{stats['created']} created, {stats['superseded']} superseded"
            )
            for obj in objs:
                resolve_manufacturer(obj)

        self.stdout.write(self.style.SUCCESS("Manufacturer seed ingestion complete."))
