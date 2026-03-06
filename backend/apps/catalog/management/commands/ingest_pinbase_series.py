"""Seed Series records from data/series.json and design credits from data/credits.json.

Creates or updates Series records with names and descriptions. After OPDB/IPDB
ingest creates Person records, creates DesignCredit(series=...) records from
credits.json.

Series-Title M2M memberships are handled by ingest_pinbase_titles.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.catalog.models import DesignCredit, Person, Series

logger = logging.getLogger(__name__)

DEFAULT_SERIES_PATH = Path(__file__).parents[5] / "data" / "series.json"
DEFAULT_CREDITS_PATH = Path(__file__).parents[5] / "data" / "credits.json"


class Command(BaseCommand):
    help = "Seed Series records and series-level design credits."

    def add_arguments(self, parser):
        parser.add_argument(
            "--series",
            default=str(DEFAULT_SERIES_PATH),
            help="Path to series.json seed file.",
        )
        parser.add_argument(
            "--credits",
            default=str(DEFAULT_CREDITS_PATH),
            help="Path to credits.json seed file.",
        )

    def handle(self, *args, **options):
        series_path = options["series"]
        credits_path = options["credits"]

        with open(series_path) as f:
            series_entries = json.load(f)

        # Pre-fetch existing slugs for counts.
        existing_slugs = set(Series.objects.values_list("slug", flat=True))

        # Build Series instances from JSON.
        objs = [
            Series(
                slug=e["slug"],
                name=e["name"],
                description=e.get("description", ""),
            )
            for e in series_entries
        ]

        # Bulk upsert: single INSERT ... ON CONFLICT DO UPDATE.
        objs = Series.objects.bulk_create(
            objs,
            update_conflicts=True,
            unique_fields=["slug"],
            update_fields=["name", "description"],
        )

        series_created = sum(1 for o in objs if o.slug not in existing_slugs)
        series_updated = len(objs) - series_created
        series_by_slug = {o.slug: o for o in objs}

        self.stdout.write(
            f"  Series: {series_created} created, {series_updated} updated"
        )

        # Seed series-level design credits.
        with open(credits_path) as f:
            credit_entries = json.load(f)

        people_by_slug = {p.slug: p for p in Person.objects.all()}

        credits_to_create = []
        credits_skipped = 0

        for entry in credit_entries:
            series_slug = entry["series_slug"]
            person_slug = entry["person_slug"]
            role = entry["role"].lower()

            series_obj = series_by_slug.get(series_slug)
            if series_obj is None:
                logger.warning(
                    "Series slug %r not found — skipping credit", series_slug
                )
                credits_skipped += 1
                continue

            person_obj = people_by_slug.get(person_slug)
            if person_obj is None:
                logger.warning(
                    "Person slug %r not found (run ingest_ipdb/opdb first) — skipping",
                    person_slug,
                )
                credits_skipped += 1
                continue

            credits_to_create.append(
                DesignCredit(series=series_obj, person=person_obj, role=role)
            )

        # Bulk create, skipping duplicates via the conditional unique constraint.
        if credits_to_create:
            created = DesignCredit.objects.bulk_create(
                credits_to_create, ignore_conflicts=True
            )
            credits_created = len(created)
        else:
            credits_created = 0

        self.stdout.write(
            f"  Credits: {credits_created} created, {credits_skipped} skipped"
        )
        self.stdout.write(self.style.SUCCESS("Series seed ingestion complete."))
