"""Orchestrate the full ingestion pipeline.

Pinbase curated data is ingested first so it bootstraps the entities that
external sources (IPDB, OPDB) will match against and enrich:

Runs: ingest_pinbase_taxonomy → ingest_pinbase_manufacturers →
      ingest_pinbase_corporate_entities → ingest_pinbase_systems →
      ingest_pinbase_people → ingest_pinbase_series →
      ingest_pinbase_titles → ingest_pinbase_models →
      ingest_ipdb → ingest_opdb → ingest_ipdb_titles →
      ingest_pinbase_signs → resolve_claims.
"""

from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction


STEPS = [
    # Phase 1: Pinbase curated data — bootstrap entities.
    "ingest_pinbase_taxonomy",
    "ingest_pinbase_manufacturers",
    "ingest_pinbase_corporate_entities",
    "ingest_pinbase_systems",
    "ingest_pinbase_people",
    "ingest_pinbase_series",
    "ingest_pinbase_titles",
    "ingest_pinbase_models",
    # Phase 2: External sources — match existing records, create new ones.
    "ingest_ipdb",
    "ingest_opdb",
    "ingest_ipdb_titles",
    # Phase 3: Enrichment + resolution.
    "ingest_pinbase_signs",
    "resolve_claims",
    # Phase 4: Validation.
    "validate_catalog",
]


class Command(BaseCommand):
    help = "Run the full ingestion pipeline: manufacturers, IPDB, OPDB, resolve."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ipdb",
            default="../data/dump1/ipdbdatabase.json",
            help="Path to IPDB JSON dump.",
        )
        parser.add_argument(
            "--opdb",
            default="../data/dump1/opdb_export_machines.json",
            help="Path to OPDB JSON dump.",
        )
        parser.add_argument(
            "--opdb-groups",
            default="../data/dump1/opdb_export_groups.json",
            help="Path to OPDB groups JSON dump.",
        )
        parser.add_argument(
            "--opdb-changelog",
            default="../data/dump1/opdb_changelog.json",
            help="Path to OPDB changelog JSON dump.",
        )
        parser.add_argument(
            "--csv",
            default="../data/dump1/machine_sign_copy.csv",
            help="Path to machine_sign_copy.csv for ingest_pinbase_signs.",
        )
        parser.add_argument(
            "--format",
            choices=["json", "markdown"],
            default="json",
            help="Data source format for Pinbase commands: json (data/*.json) or markdown (data/pinbase/)",
        )
        parser.add_argument(
            "--write",
            action="store_true",
            help="Commit changes to the database. Without this flag, the pipeline "
            "runs in dry-run mode and rolls back all changes.",
        )

    def handle(self, *args, **options):
        write = options["write"]
        ipdb_path = options["ipdb"]
        opdb_path = options["opdb"]
        opdb_groups = options["opdb_groups"]
        opdb_changelog = options["opdb_changelog"]
        csv_path = options["csv"]
        fmt = options["format"]

        from apps.catalog.cache import invalidate_all

        if not write:
            self.stdout.write(
                self.style.WARNING(
                    "[DRY RUN] No changes will be saved. Pass --write to commit."
                )
            )

        pinbase_steps = {
            "ingest_pinbase_taxonomy",
            "ingest_pinbase_manufacturers",
            "ingest_pinbase_corporate_entities",
            "ingest_pinbase_systems",
            "ingest_pinbase_people",
            "ingest_pinbase_series",
            "ingest_pinbase_titles",
            "ingest_pinbase_models",
        }

        try:
            with transaction.atomic():
                for step in STEPS:
                    prefix = "[DRY RUN] " if not write else ""
                    self.stdout.write(
                        self.style.MIGRATE_HEADING(f"{prefix}Running {step}...")
                    )
                    kwargs = {}
                    if step in pinbase_steps:
                        kwargs["format"] = fmt
                    elif step == "ingest_ipdb":
                        kwargs["ipdb"] = ipdb_path
                    elif step == "ingest_opdb":
                        kwargs.update(
                            {
                                "opdb": opdb_path,
                                "groups": opdb_groups,
                                "changelog": opdb_changelog,
                                "models": "../data/models.json",
                                "titles": "../data/titles.json",
                            }
                        )
                    elif step == "ingest_pinbase_signs":
                        kwargs["csv"] = csv_path
                    call_command(step, stdout=self.stdout, stderr=self.stderr, **kwargs)

                if not write:
                    transaction.set_rollback(True)
        finally:
            invalidate_all()

        if not write:
            self.stdout.write(
                self.style.SUCCESS("Dry run complete — no data was modified.")
            )
        else:
            self.stdout.write(self.style.SUCCESS("Full ingestion pipeline complete."))
