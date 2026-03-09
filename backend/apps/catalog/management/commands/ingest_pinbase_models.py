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

        self.stdout.write(self.style.SUCCESS("Models seed ingestion complete."))
