"""Create and enrich Title records from data/titles.json.

Creates Title records that don't yet exist (with opdb_id, name, slug),
then asserts name and franchise claims and resolves them.  Slug overrides
and Series M2M memberships are applied directly (not claim-controlled).

Runs after:
  - ingest_pinbase_taxonomy (for Franchise records)
  - ingest_pinbase_series (for Series records)
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.catalog.claims import build_relationship_claim
from apps.catalog.ingestion.bulk_utils import generate_unique_slug
from apps.catalog.models import Franchise, Series, Title
from apps.provenance.models import Claim, Source

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
        from django.contrib.contenttypes.models import ContentType

        from apps.catalog.resolve import TITLE_DIRECT_FIELDS, _resolve_bulk

        path = options["path"]
        with open(path) as f:
            entries = json.load(f)

        source, _ = Source.objects.update_or_create(
            slug="pinbase-titles",
            defaults={
                "name": "Pinbase Titles Seed",
                "source_type": "editorial",
                "priority": 300,
                "url": "",
            },
        )

        ct_id = ContentType.objects.get_for_model(Title).pk

        # Build lookups.
        titles_by_opdb_id = {t.opdb_id: t for t in Title.objects.all()}
        titles_by_slug = {t.slug: t for t in Title.objects.all()}
        existing_slugs: set[str] = set(Title.objects.values_list("slug", flat=True))
        franchises_by_slug = {f.slug: f for f in Franchise.objects.all()}
        series_by_slug = {s.slug: s for s in Series.objects.all()}

        # Pass 1: create Titles that don't exist yet.
        new_titles: list[Title] = []
        for entry in entries:
            opdb_group_id = entry.get("opdb_group_id")
            slug = entry.get("slug")

            # Match by opdb_group_id first, then by slug.
            if opdb_group_id and opdb_group_id in titles_by_opdb_id:
                continue
            if slug and slug in titles_by_slug:
                continue

            slug = slug or generate_unique_slug(entry.get("name", ""), existing_slugs)
            # Use opdb_group_id if provided, otherwise a synthetic ID.
            opdb_id = opdb_group_id or f"pinbase:{slug}"
            new_titles.append(
                Title(
                    opdb_id=opdb_id,
                    name=entry.get("name", ""),
                    slug=slug,
                )
            )
            existing_slugs.add(slug)

        titles_created = len(new_titles)
        if new_titles:
            Title.objects.bulk_create(new_titles)

        # Re-fetch lookups after potential creation.
        titles_by_opdb_id = {t.opdb_id: t for t in Title.objects.all()}
        titles_by_slug = {t.slug: t for t in Title.objects.all()}

        membership_set = slug_set = skipped = 0
        pending_claims: list[Claim] = []
        pending_slugs: dict[int, str] = {}  # title.pk → desired slug
        series_memberships: dict[Series, list[Title]] = defaultdict(list)
        touched_ids: set[int] = set()

        for entry in entries:
            opdb_group_id = entry.get("opdb_group_id")
            slug = entry.get("slug")

            # Look up by opdb_group_id first, then by slug.
            title = None
            if opdb_group_id:
                title = titles_by_opdb_id.get(opdb_group_id)
            if title is None and slug:
                title = titles_by_slug.get(slug)
            if title is None:
                logger.warning(
                    "Title %r not found — skipping",
                    opdb_group_id or slug,
                )
                skipped += 1
                continue

            # Override slug if provided (direct write, not claim-controlled).
            slug = entry.get("slug")
            if slug and title.slug != slug:
                pending_slugs[title.pk] = slug

            # Assert name claim if override provided.
            name = entry.get("name")
            if name:
                touched_ids.add(title.pk)
                pending_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=title.pk,
                        field_name="name",
                        value=name,
                    )
                )

            # Assert franchise claim.
            franchise_slug = entry.get("franchise_slug")
            if franchise_slug:
                franchise = franchises_by_slug.get(franchise_slug)
                if franchise is None:
                    logger.warning(
                        "Franchise slug %r not found — skipping", franchise_slug
                    )
                else:
                    touched_ids.add(title.pk)
                    pending_claims.append(
                        Claim(
                            content_type_id=ct_id,
                            object_id=title.pk,
                            field_name="franchise",
                            value=franchise_slug,
                        )
                    )

            # Assert abbreviation claims.
            for abbr in entry.get("abbreviations", []):
                claim_key, value = build_relationship_claim(
                    "abbreviation", {"value": abbr}
                )
                touched_ids.add(title.pk)
                pending_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=title.pk,
                        field_name="abbreviation",
                        claim_key=claim_key,
                        value=value,
                    )
                )

            # Collect series membership (M2M, not claim-controlled).
            series_slug = entry.get("series_slug")
            if series_slug:
                series = series_by_slug.get(series_slug)
                if series is None:
                    logger.warning("Series slug %r not found — skipping", series_slug)
                else:
                    series_memberships[series].append(title)
                    membership_set += 1

        # Assert all collected claims in bulk.
        claim_stats: dict = {}
        if pending_claims:
            claim_stats = Claim.objects.bulk_assert_claims(source, pending_claims)

        # Resolve touched titles so fields reflect winning claims.
        if touched_ids:
            from apps.catalog.resolve import resolve_all_title_abbreviations

            franchise_lookup = {f.slug: f for f in Franchise.objects.all()}
            _resolve_bulk(
                Title,
                TITLE_DIRECT_FIELDS,
                fk_handlers={"franchise": ("franchise", franchise_lookup)},
                object_ids=touched_ids,
            )
            resolve_all_title_abbreviations(
                list(Title.objects.all()), title_ids=touched_ids
            )

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
                from django.utils import timezone

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

        # Batch M2M adds per series.
        for series, titles in series_memberships.items():
            series.titles.add(*titles)

        self.stdout.write(
            f"  Titles: {titles_created} created, {membership_set} series memberships, "
            f"{slug_set} slug overrides, {skipped} skipped"
        )
        if claim_stats:
            self.stdout.write(
                f"  Claims: {claim_stats.get('created', 0)} created, "
                f"{claim_stats.get('unchanged', 0)} unchanged"
            )
        self.stdout.write(self.style.SUCCESS("Titles seed ingestion complete."))
