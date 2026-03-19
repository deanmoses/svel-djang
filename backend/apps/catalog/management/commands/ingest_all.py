"""Orchestrate the full ingestion pipeline.

Pinbase curated data is ingested first so it bootstraps the entities that
external sources (IPDB, OPDB) will match against and enrich:

Runs: ingest_pinbase → ingest_ipdb → ingest_opdb →
      resolve_claims → validate_catalog.
"""

from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction


from apps.catalog.ingestion.constants import (
    DEFAULT_EXPORT_DIR,
    DEFAULT_IPDB_PATH,
    DEFAULT_OPDB_CHANGELOG_PATH,
    DEFAULT_OPDB_PATH,
)

STEPS = [
    # Phase 1: Pinbase curated data — bootstrap entities.
    "ingest_pinbase",
    # Phase 2: External sources — match existing records, assert claims.
    "ingest_ipdb",
    "ingest_opdb",
    # Phase 3: Resolution + validation.
    "resolve_claims",
    "validate_catalog",
]


class Command(BaseCommand):
    help = "Run the full ingestion pipeline: Pinbase, IPDB, OPDB, resolve."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ipdb",
            default=DEFAULT_IPDB_PATH,
            help="Path to IPDB JSON dump.",
        )
        parser.add_argument(
            "--opdb",
            default=DEFAULT_OPDB_PATH,
            help="Path to OPDB JSON dump.",
        )
        parser.add_argument(
            "--opdb-changelog",
            default=DEFAULT_OPDB_CHANGELOG_PATH,
            help="Path to OPDB changelog JSON dump.",
        )
        parser.add_argument(
            "--export-dir",
            default=DEFAULT_EXPORT_DIR,
            help="Path to exported Pinbase JSON directory.",
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
        opdb_changelog = options["opdb_changelog"]
        export_dir = options["export_dir"]

        from apps.catalog.cache import invalidate_all

        if not write:
            self.stdout.write(
                self.style.WARNING(
                    "[DRY RUN] No changes will be saved. Pass --write to commit."
                )
            )

        try:
            with transaction.atomic():
                for step in STEPS:
                    prefix = "[DRY RUN] " if not write else ""
                    self.stdout.write(
                        self.style.MIGRATE_HEADING(f"{prefix}Running {step}...")
                    )
                    kwargs = {}
                    if step == "ingest_pinbase":
                        kwargs["export_dir"] = export_dir
                    elif step == "ingest_ipdb":
                        kwargs["ipdb"] = ipdb_path
                        kwargs["export_dir"] = export_dir
                    elif step == "ingest_opdb":
                        kwargs.update(
                            {
                                "opdb": opdb_path,
                                "changelog": opdb_changelog,
                            }
                        )
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
