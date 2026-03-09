"""Assert editorial claims for MachineModels from data/models.json.

Runs after ingest_opdb (so MachineModels exist). Matches by opdb_id and
asserts claims with the pinbase source (priority 300), which outranks OPDB.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from apps.catalog.models import MachineModel
from apps.provenance.models import Claim, Source

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).parents[5] / "data" / "models.json"

# Fields stored as claim values (claim field_name → JSON key).
CLAIM_FIELDS = {
    "name": "name",
    "display_type": "display_type_slug",
    "description": "description",
}


class Command(BaseCommand):
    help = "Assert editorial claims for MachineModels from data/models.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(DEFAULT_PATH),
            help="Path to models.json.",
        )

    def handle(self, *args, **options):
        path = options["path"]
        with open(path) as f:
            entries = json.load(f)

        ct_id = ContentType.objects.get_for_model(MachineModel).pk

        source, _ = Source.objects.get_or_create(
            slug="pinbase",
            defaults={
                "name": "Pinbase",
                "source_type": Source.SourceType.EDITORIAL,
                "priority": 300,
                "description": "Pinbase curated data.",
            },
        )

        by_opdb_id: dict[str, MachineModel] = {
            mm.opdb_id: mm for mm in MachineModel.objects.filter(opdb_id__isnull=False)
        }

        pending_claims: list[Claim] = []
        matched = 0
        skipped = 0

        for entry in entries:
            opdb_id = entry.get("opdb_id")
            if not opdb_id:
                # Entries without opdb_id (e.g. slug-only) are not yet
                # supported for claim assertion — skip silently.
                skipped += 1
                continue

            mm = by_opdb_id.get(opdb_id)
            if mm is None:
                logger.warning(
                    "No MachineModel for opdb_id %r (%s) — skipping",
                    opdb_id,
                    entry.get("name", "unknown"),
                )
                skipped += 1
                continue

            matched += 1
            for claim_field, json_key in CLAIM_FIELDS.items():
                value = entry.get(json_key)
                if value:
                    pending_claims.append(
                        Claim(
                            content_type_id=ct_id,
                            object_id=mm.pk,
                            field_name=claim_field,
                            value=value,
                        )
                    )

        self.stdout.write(f"  Matched: {matched}, Skipped: {skipped}")

        claim_stats = Claim.objects.bulk_assert_claims(source, pending_claims)
        self.stdout.write(
            f"  Claims: {claim_stats['unchanged']} unchanged, "
            f"{claim_stats['created']} created, "
            f"{claim_stats['superseded']} superseded, "
            f"{claim_stats['duplicates_removed']} duplicates removed"
        )

        # --- variant_of: set alias_of FK based on slug references ---
        # Build slug→MachineModel lookup from entries that have both slug and opdb_id.
        slug_to_mm: dict[str, MachineModel] = {}
        for entry in entries:
            slug = entry.get("slug")
            opdb_id = entry.get("opdb_id")
            if slug and opdb_id:
                mm = by_opdb_id.get(opdb_id)
                if mm:
                    slug_to_mm[slug] = mm

        # Collect parent slugs — entries that are referenced as variant_of targets.
        parent_slugs: set[str] = {
            entry["variant_of"] for entry in entries if entry.get("variant_of")
        }

        variant_updated: list[MachineModel] = []
        variant_set = 0

        # First pass: clear alias_of on parent models (fixes circular references
        # when models.json overrides an ingest_opdb heuristic).
        for slug in parent_slugs:
            parent = slug_to_mm.get(slug)
            if parent and parent.alias_of_id is not None:
                parent.alias_of = None
                variant_updated.append(parent)

        # Second pass: set alias_of on variant models.
        for entry in entries:
            variant_of_slug = entry.get("variant_of")
            if not variant_of_slug:
                continue

            opdb_id = entry.get("opdb_id")
            if not opdb_id:
                continue

            mm = by_opdb_id.get(opdb_id)
            parent = slug_to_mm.get(variant_of_slug)
            if not mm or not parent:
                if not parent:
                    logger.warning(
                        "variant_of slug %r not found for %s",
                        variant_of_slug,
                        entry.get("name", opdb_id),
                    )
                continue

            if mm.alias_of_id != parent.pk:
                mm.alias_of = parent
                if mm not in variant_updated:
                    variant_updated.append(mm)
            variant_set += 1

        if variant_updated:
            MachineModel.objects.bulk_update(variant_updated, ["alias_of_id"])

        if variant_set:
            self.stdout.write(
                f"  Variants: {variant_set} relationships, "
                f"{len(variant_updated)} updated"
            )

        self.stdout.write(self.style.SUCCESS("Models seed ingestion complete."))
