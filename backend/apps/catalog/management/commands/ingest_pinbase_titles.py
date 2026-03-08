"""Set Title franchise FK and Series memberships from data/titles.json.

Runs after:
  - ingest_pinbase_taxonomy (for Franchise records)
  - ingest_opdb (for Title records)
  - ingest_pinbase_series (for Series records)
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.catalog.models import Franchise, Series, Title

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).parents[5] / "data" / "titles.json"


class Command(BaseCommand):
    help = "Set Title franchise FK and Series memberships from data/titles.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(DEFAULT_PATH),
            help="Path to titles.json.",
        )

    def handle(self, *args, **options):
        path = options["path"]
        with open(path) as f:
            entries = json.load(f)

        # Build lookups.
        titles_by_opdb_id = {t.opdb_id: t for t in Title.objects.all()}
        franchises_by_slug = {f.slug: f for f in Franchise.objects.all()}
        series_by_slug = {s.slug: s for s in Series.objects.all()}

        franchise_set = membership_set = name_set = slug_set = skipped = 0
        franchise_changed: list[Title] = []
        name_changed: list[Title] = []
        pending_slugs: dict[int, str] = {}  # title.pk → desired slug
        series_memberships: dict[Series, list[Title]] = defaultdict(list)

        for entry in entries:
            opdb_group_id = entry["opdb_group_id"]

            title = titles_by_opdb_id.get(opdb_group_id)
            if title is None:
                logger.warning(
                    "Title with opdb_id %r not found — skipping", opdb_group_id
                )
                skipped += 1
                continue

            # Override slug if provided.
            slug = entry.get("slug")
            if slug and title.slug != slug:
                pending_slugs[title.pk] = slug

            # Override name if provided.
            name = entry.get("name")
            if name and title.name != name:
                title.name = name
                name_changed.append(title)
                name_set += 1

            # Set franchise FK.
            franchise_slug = entry.get("franchise_slug")
            if franchise_slug:
                franchise = franchises_by_slug.get(franchise_slug)
                if franchise is None:
                    logger.warning(
                        "Franchise slug %r not found — skipping", franchise_slug
                    )
                else:
                    if title.franchise_id != franchise.pk:
                        title.franchise = franchise
                        franchise_changed.append(title)
                    franchise_set += 1

            # Collect series membership.
            series_slug = entry.get("series_slug")
            if series_slug:
                series = series_by_slug.get(series_slug)
                if series is None:
                    logger.warning("Series slug %r not found — skipping", series_slug)
                else:
                    series_memberships[series].append(title)
                    membership_set += 1

        # Bulk update franchise FK changes.
        if franchise_changed:
            now = timezone.now()
            for t in franchise_changed:
                t.updated_at = now
            Title.objects.bulk_update(franchise_changed, ["franchise", "updated_at"])

        # Update slugs in two passes to handle swaps (e.g. A→B and B→C).
        # Filter out slugs that would conflict with titles not being renamed.
        if pending_slugs:
            pks_being_renamed = set(pending_slugs.keys())
            desired_slugs = set(pending_slugs.values())
            conflicting = set(
                Title.objects.filter(slug__in=desired_slugs)
                .exclude(pk__in=pks_being_renamed)
                .values_list("slug", flat=True)
            )
            safe_slugs = {
                pk: slug
                for pk, slug in pending_slugs.items()
                if slug not in conflicting
            }
            for slug in conflicting:
                logger.warning("Slug %r already taken — skipping rename", slug)

            if safe_slugs:
                now = timezone.now()
                # Pass 1: move to temporary slugs.
                for pk, slug in safe_slugs.items():
                    Title.objects.filter(pk=pk).update(
                        slug=f"_tmp_{pk}", updated_at=now
                    )
                # Pass 2: move to final slugs.
                for pk, slug in safe_slugs.items():
                    Title.objects.filter(pk=pk).update(slug=slug)
                slug_set = len(safe_slugs)

        # Bulk update name changes.
        if name_changed:
            now = timezone.now()
            for t in name_changed:
                t.updated_at = now
            Title.objects.bulk_update(name_changed, ["name", "updated_at"])

        # Batch M2M adds per series.
        for series, titles in series_memberships.items():
            series.titles.add(*titles)

        self.stdout.write(
            f"  Titles: {franchise_set} franchise links, "
            f"{membership_set} series memberships, "
            f"{name_set} name overrides, {slug_set} slug overrides, "
            f"{skipped} skipped"
        )
        self.stdout.write(self.style.SUCCESS("Titles seed ingestion complete."))
