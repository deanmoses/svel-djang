"""Create and enrich MachineModel records from data/models.json.

Creates MachineModel records that don't yet exist (with opdb_id, ipdb_id,
name, slug), then asserts editorial claims with the pinbase source
(priority 300) which outranks OPDB.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from apps.catalog.ingestion.bulk_utils import generate_unique_slug
from apps.catalog.models import MachineModel
from apps.provenance.models import Claim, Source

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).parents[5] / "data" / "models.json"

# Fields stored as claim values (claim field_name → JSON key).
CLAIM_FIELDS = {
    "name": "name",
    "display_type": "display_type",
    "description": "description",
    "is_conversion": "is_conversion",
    "converted_from": "converted_from",
    "variant_of": "variant_of",
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
        by_ipdb_id: dict[int, MachineModel] = {
            mm.ipdb_id: mm for mm in MachineModel.objects.filter(ipdb_id__isnull=False)
        }
        existing_slugs: set[str] = set(
            MachineModel.objects.values_list("slug", flat=True)
        )

        # Pass 1: create MachineModels that don't exist yet.
        new_models: list[MachineModel] = []
        models_needing_opdb_update: list[MachineModel] = []

        for entry in entries:
            opdb_id = entry.get("opdb_id")
            if not opdb_id:
                continue
            if opdb_id in by_opdb_id:
                continue
            # Check ipdb_id match (handles re-runs where IPDB created the record).
            ipdb_id = entry.get("ipdb_id")
            if ipdb_id and ipdb_id in by_ipdb_id:
                mm = by_ipdb_id[ipdb_id]
                if mm.opdb_id is None:
                    mm.opdb_id = opdb_id
                    models_needing_opdb_update.append(mm)
                by_opdb_id[opdb_id] = mm
                continue
            slug = entry.get("slug") or generate_unique_slug(
                entry.get("name", ""), existing_slugs
            )
            mm = MachineModel(opdb_id=opdb_id, name=entry.get("name", ""), slug=slug)
            if ipdb_id:
                mm.ipdb_id = ipdb_id
            new_models.append(mm)
            existing_slugs.add(slug)
            by_opdb_id[opdb_id] = mm

        models_created = len(new_models)
        if new_models:
            MachineModel.objects.bulk_create(new_models)
        if models_needing_opdb_update:
            MachineModel.objects.bulk_update(models_needing_opdb_update, ["opdb_id"])
        if new_models or models_needing_opdb_update:
            by_opdb_id = {
                mm.opdb_id: mm
                for mm in MachineModel.objects.filter(opdb_id__isnull=False)
            }

        # Pass 2: assert claims.
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

        self.stdout.write(
            f"  Models: {models_created} created, {matched} matched, {skipped} skipped"
        )

        claim_stats = Claim.objects.bulk_assert_claims(source, pending_claims)
        self.stdout.write(
            f"  Claims: {claim_stats['unchanged']} unchanged, "
            f"{claim_stats['created']} created, "
            f"{claim_stats['superseded']} superseded, "
            f"{claim_stats['duplicates_removed']} duplicates removed"
        )

        self.stdout.write(self.style.SUCCESS("Models seed ingestion complete."))
