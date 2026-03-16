"""Seed Series records from data/series.json or data/pinbase/series/.

Creates or updates Series records with names and descriptions. Person records
must exist before credits can be created (run ingest_pinbase_people first).
Creates Credit(series=...) records from credits.json (JSON mode) or from
credit_refs embedded in series Markdown files (Markdown mode).

Series-Title M2M memberships are handled by ingest_pinbase_titles.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError

from apps.catalog.ingestion.pinbase_loader import load_series_as_dicts
from apps.catalog.models import Credit, CreditRole, Person, Series
from apps.provenance.models import Claim, Source

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
        parser.add_argument(
            "--format",
            choices=["json", "markdown"],
            default="json",
            help="Data source format: json (data/*.json) or markdown (data/pinbase/)",
        )

    def handle(self, *args, **options):
        if options["format"] == "markdown":
            series_entries, credit_entries = load_series_as_dicts()
        else:
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
        ct_id = ContentType.objects.get_for_model(Series).pk

        pending_claims: list[Claim] = []
        for obj, entry in zip(objs, series_entries):
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

        # Seed series-level design credits.
        if options["format"] != "markdown":
            with open(credits_path) as f:
                credit_entries = json.load(f)

        people_by_slug = {p.slug: p for p in Person.objects.all()}
        role_lookup = {r.slug: r for r in CreditRole.objects.all()}
        if not role_lookup:
            raise CommandError(
                "CreditRole table is empty — run ingest_pinbase_taxonomy first."
            )

        credits_to_create = []
        credits_skipped = 0

        for entry in credit_entries:
            series_slug = entry["series_slug"]
            person_slug = entry["person_slug"]
            role_slug = entry["role"].lower()

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
                    "Person slug %r not found (run ingest_pinbase_people first) — skipping",
                    person_slug,
                )
                credits_skipped += 1
                continue

            role_obj = role_lookup.get(role_slug)
            if role_obj is None:
                logger.warning("Unknown credit role %r — skipping", role_slug)
                credits_skipped += 1
                continue

            credits_to_create.append(
                Credit(series=series_obj, person=person_obj, role=role_obj)
            )

        # Bulk create, skipping duplicates via the conditional unique constraint.
        if credits_to_create:
            created = Credit.objects.bulk_create(
                credits_to_create, ignore_conflicts=True
            )
            credits_created = len(created)
        else:
            credits_created = 0

        self.stdout.write(
            f"  Credits: {credits_created} created, {credits_skipped} skipped"
        )
        self.stdout.write(self.style.SUCCESS("Series seed ingestion complete."))
