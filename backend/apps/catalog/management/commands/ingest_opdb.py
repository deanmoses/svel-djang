"""Ingest pinball machines from an OPDB JSON dump.

Matches existing MachineModels by opdb_id, then creates new records.
Asserts scalar claims only — relationship-shaping claims (title, variant_of)
are owned by Pinbase-authored Markdown files.

Claims are collected during the main loop and written in bulk afterward.
"""

from __future__ import annotations

import json
from apps.catalog.ingestion.constants import DEFAULT_OPDB_PATH
import logging

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.claims import build_relationship_claim
from apps.catalog.ingestion.bulk_utils import (
    format_names,
    generate_unique_slug,
)
from apps.catalog.ingestion.opdb.records import OpdbRecord
from apps.catalog.ingestion.parsers import (
    map_opdb_display,
    map_opdb_type,
    parse_opdb_date,
)
from apps.catalog.models import MachineModel
from apps.provenance.models import Claim, Source

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Ingest pinball machines from an OPDB JSON dump."

    def add_arguments(self, parser):
        parser.add_argument(
            "--opdb",
            default=DEFAULT_OPDB_PATH,
            help="Path to OPDB JSON dump.",
        )
        parser.add_argument(
            "--changelog",
            default="",
            help="Path to OPDB changelog JSON dump.",
        )

    def handle(self, *args, **options):
        opdb_path = options["opdb"]
        changelog_path = options["changelog"]

        from django.contrib.contenttypes.models import ContentType

        ct_id = ContentType.objects.get_for_model(MachineModel).pk

        source, _ = Source.objects.update_or_create(
            slug="opdb",
            defaults={
                "name": "OPDB",
                "source_type": "database",
                "priority": 200,
                "url": "https://opdb.org",
            },
        )

        # --- Changelog pre-processing ---
        if changelog_path:
            self._process_changelog(changelog_path)

        # --- Load and parse machine data into typed records ---
        with open(opdb_path) as f:
            raw_data = json.load(f)

        records: list[OpdbRecord] = []
        parse_errors = 0
        for raw in raw_data:
            if "opdb_id" not in raw:
                parse_errors += 1
                logger.warning(
                    "OPDB record missing opdb_id (name=%r)",
                    raw.get("name", "<unknown>"),
                )
                continue
            try:
                records.append(OpdbRecord.from_raw(raw))
            except (KeyError, ValueError, TypeError) as e:
                parse_errors += 1
                logger.warning(
                    "Unparseable OPDB record (id=%s): %s",
                    raw.get("opdb_id", "?"),
                    e,
                )
        if parse_errors:
            raise CommandError(
                f"{parse_errors} OPDB record(s) failed to parse — aborting to prevent partial import. "
                f"Check warnings above for details."
            )

        # Physical machines + aliases — all treated as flat records.
        machines = [r for r in records if r.is_machine and r.physical_machine != 0]
        aliases = [r for r in records if r.is_alias]
        non_physical_count = sum(
            1 for r in records if r.is_machine and r.physical_machine == 0
        )
        self.stdout.write(
            f"Processing {len(machines)} OPDB machines "
            f"({non_physical_count} non-physical skipped) "
            f"+ {len(aliases)} aliases..."
        )

        # --- Pre-fetch all MachineModels into lookup dicts ---
        by_ipdb_id: dict[int, MachineModel] = {
            pm.ipdb_id: pm for pm in MachineModel.objects.filter(ipdb_id__isnull=False)
        }
        by_opdb_id: dict[str, MachineModel] = {
            pm.opdb_id: pm for pm in MachineModel.objects.filter(opdb_id__isnull=False)
        }
        existing_slugs: set[str] = set(
            MachineModel.objects.values_list("slug", flat=True)
        )

        # --- Match/create machines ---
        new_models: list[MachineModel] = []
        models_needing_opdb_update: list[MachineModel] = []
        machine_models: list[tuple[MachineModel, OpdbRecord]] = []
        matched = 0
        created = 0

        for rec in machines:
            pm = by_opdb_id.get(rec.opdb_id)

            # Fallback: match by ipdb_id (IPDB may have created the record first).
            if not pm and rec.ipdb_id:
                pm = by_ipdb_id.get(rec.ipdb_id)

            if pm:
                matched += 1
                # Set opdb_id if not already set (cross-reference backfill).
                if pm.opdb_id is None and rec.opdb_id:
                    if rec.opdb_id not in by_opdb_id:
                        pm.opdb_id = rec.opdb_id
                        by_opdb_id[rec.opdb_id] = pm
                        models_needing_opdb_update.append(pm)
                    else:
                        logger.warning(
                            "Cannot set opdb_id=%s on %r (ipdb_id=%s): "
                            "already owned by %r",
                            rec.opdb_id,
                            pm.name,
                            rec.ipdb_id,
                            by_opdb_id[rec.opdb_id].name,
                        )
                elif pm.opdb_id and pm.opdb_id != rec.opdb_id:
                    logger.warning(
                        "MachineModel %r already has opdb_id=%s, skipping %s",
                        pm.name,
                        pm.opdb_id,
                        rec.opdb_id,
                    )
            else:
                created += 1
                slug = generate_unique_slug(rec.name, existing_slugs)
                pm = MachineModel(name=rec.name, opdb_id=rec.opdb_id, slug=slug)
                new_models.append(pm)
                by_opdb_id[rec.opdb_id] = pm
                if rec.ipdb_id:
                    by_ipdb_id[rec.ipdb_id] = pm

            machine_models.append((pm, rec))

        if new_models:
            MachineModel.objects.bulk_create(new_models)
        if models_needing_opdb_update:
            MachineModel.objects.bulk_update(models_needing_opdb_update, ["opdb_id"])

        self.stdout.write(f"  Machines — Matched: {matched}, Created: {created}")
        if new_models:
            self.stdout.write(
                f"    New: {format_names([pm.name for pm in new_models])}"
            )

        # --- Match/create aliases (flat — no variant_of classification) ---
        new_alias_models: list[MachineModel] = []
        alias_linked = 0
        alias_created = 0
        alias_skipped = 0

        for rec in aliases:
            # Require parent to exist — skip orphan aliases.
            parent = by_opdb_id.get(rec.parent_opdb_id)
            if not parent:
                logger.warning(
                    "Alias %s (%s): parent %s not found, skipping",
                    rec.opdb_id,
                    rec.name,
                    rec.parent_opdb_id,
                )
                alias_skipped += 1
                continue

            pm = by_opdb_id.get(rec.opdb_id)

            if pm:
                alias_linked += 1
            else:
                alias_created += 1
                slug = generate_unique_slug(rec.name, existing_slugs)
                pm = MachineModel(name=rec.name, opdb_id=rec.opdb_id, slug=slug)
                new_alias_models.append(pm)
                by_opdb_id[rec.opdb_id] = pm

            machine_models.append((pm, rec))

        if new_alias_models:
            MachineModel.objects.bulk_create(new_alias_models)

        self.stdout.write(
            f"  Aliases — Linked: {alias_linked}, Created: {alias_created}, "
            f"Skipped: {alias_skipped}"
        )
        if new_alias_models:
            self.stdout.write(
                f"    New: {format_names([pm.name for pm in new_alias_models])}"
            )

        # --- Collect and assert scalar claims ---
        pending_claims: list[Claim] = []

        for pm, rec in machine_models:
            self._collect_claims(pm, rec, ct_id, pending_claims)

        claim_stats = Claim.objects.bulk_assert_claims(source, pending_claims)
        self.stdout.write(
            f"  Claims: {claim_stats['unchanged']} unchanged, "
            f"{claim_stats['created']} created, "
            f"{claim_stats['superseded']} superseded, "
            f"{claim_stats['duplicates_removed']} duplicates removed"
        )

        # --- Deactivate stale claims from prior OPDB runs ---
        # OPDB no longer asserts variant_of, title, or manufacturer claims.
        # Any active claims from previous runs must be cleaned up.
        stale_count = Claim.objects.filter(
            source=source,
            field_name__in=["variant_of", "title", "manufacturer"],
            is_active=True,
        ).update(is_active=False)
        if stale_count:
            self.stdout.write(
                f"  Deactivated {stale_count} stale claims "
                f"(variant_of/title/manufacturer)"
            )

        # Log OPDB manufacturers not represented in pinbase.
        from apps.catalog.models import Manufacturer

        pinbase_opdb_mfr_ids = set(
            Manufacturer.objects.filter(opdb_manufacturer_id__isnull=False).values_list(
                "opdb_manufacturer_id", flat=True
            )
        )
        opdb_mfr_ids = {
            rec.manufacturer_id for rec in machines if rec.manufacturer_id is not None
        }
        missing_mfr_count = len(opdb_mfr_ids - pinbase_opdb_mfr_ids)
        if missing_mfr_count:
            self.stdout.write(
                f"  {missing_mfr_count} OPDB manufacturer(s) not in pinbase"
            )

        self.stdout.write(self.style.SUCCESS("OPDB ingestion complete."))

    # ------------------------------------------------------------------
    # Changelog
    # ------------------------------------------------------------------

    def _process_changelog(self, path: str) -> None:
        """Apply changelog: update stale opdb_ids for 'move' actions."""
        with open(path) as f:
            entries = json.load(f)

        moves = 0
        deletes = 0
        for entry in entries:
            action = entry.get("action")
            deleted_id = entry.get("opdb_id_deleted")
            replacement_id = entry.get("opdb_id_replacement")

            if action == "move" and deleted_id and replacement_id:
                updated = MachineModel.objects.filter(opdb_id=deleted_id)
                # Only update if the replacement isn't already taken.
                if not MachineModel.objects.filter(opdb_id=replacement_id).exists():
                    count = updated.update(opdb_id=replacement_id)
                    if count:
                        self.stdout.write(
                            f"  Changelog: moved {deleted_id} → {replacement_id}"
                        )
                        moves += 1
                elif updated.exists():
                    logger.warning(
                        "Changelog move %s → %s: replacement already exists",
                        deleted_id,
                        replacement_id,
                    )
            elif action == "delete" and deleted_id:
                if MachineModel.objects.filter(opdb_id=deleted_id).exists():
                    logger.info(
                        "Changelog delete %s: model exists but not deleting",
                        deleted_id,
                    )
                deletes += 1

        self.stdout.write(
            f"  Changelog: {moves} moves applied, {deletes} deletes logged"
        )

    # ------------------------------------------------------------------
    # Claim collection
    # ------------------------------------------------------------------

    def _collect_claims(
        self,
        pm: MachineModel,
        rec: OpdbRecord,
        ct_id: int,
        pending_claims: list[Claim],
    ) -> None:
        """Collect scalar claim objects for a machine or alias record."""

        def _add(field_name: str, value) -> None:
            pending_claims.append(
                Claim(
                    content_type_id=ct_id,
                    object_id=pm.pk,
                    field_name=field_name,
                    value=value,
                )
            )

        if rec.name:
            _add("name", rec.name)
        if rec.opdb_id:
            _add("opdb_id", rec.opdb_id)

        # Date.
        if rec.manufacture_date:
            year, month = parse_opdb_date(rec.manufacture_date)
            if year is not None:
                _add("year", year)
            if month is not None:
                _add("month", month)

        # Player count.
        if rec.player_count is not None:
            _add("player_count", rec.player_count)

        # Technology generation (slug-based, resolved to FK).
        technology_generation = map_opdb_type(rec.type)
        if technology_generation:
            _add("technology_generation", technology_generation)

        # Display type (slug-based, resolved to FK).
        display_type = map_opdb_display(rec.display)
        if display_type:
            _add("display_type", display_type)

        # Cabinet (from OPDB features).
        if rec.features and "Cocktail table" in rec.features:
            _add("cabinet", "cocktail")

        # Extra data fields.
        # OPDB 'features' are variant labels (LE, SE, shaker motor etc.) — stored
        # as 'variant_features' to avoid future confusion with gameplay features.
        if rec.features:
            _add("opdb.variant_features", rec.features)

        for attr, claim_field in (
            ("keywords", "opdb.keywords"),
            ("description", "opdb.description"),
            ("common_name", "opdb.common_name"),
            ("images", "opdb.images"),
        ):
            value = getattr(rec, attr)
            if value:
                _add(claim_field, value)

        # Shortname becomes a relationship claim for abbreviations.
        if rec.shortname:
            claim_key, abbr_value = build_relationship_claim(
                "abbreviation", {"value": rec.shortname}
            )
            pending_claims.append(
                Claim(
                    content_type_id=ct_id,
                    object_id=pm.pk,
                    field_name="abbreviation",
                    claim_key=claim_key,
                    value=abbr_value,
                )
            )
