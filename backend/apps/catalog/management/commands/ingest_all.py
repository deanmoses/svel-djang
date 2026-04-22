"""Orchestrate the full ingestion pipeline.

Pinbase curated data is ingested first so it bootstraps the entities that
external sources (IPDB, OPDB) will match against and enrich:

Runs: ingest_pinbase → ingest_ipdb → ingest_opdb →
      resolve_claims → validate_catalog.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.ingestion.constants import (
    DEFAULT_EXPORT_DIR,
    DEFAULT_IPDB_PATH,
    DEFAULT_OPDB_PATH,
)
from apps.catalog.management.commands.ingest_pinbase import (
    validate_cross_entity_wikilinks,
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

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
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

    def handle(self, *args: object, **options: Any) -> None:
        write = options["write"]
        ipdb_path = options["ipdb"]
        opdb_path = options["opdb"]
        export_dir = options["export_dir"]

        from apps.catalog.cache import invalidate_all

        if not write:
            self.stdout.write(
                self.style.WARNING(
                    "[DRY RUN] No changes will be saved. Pass --write to commit."
                )
            )

        pipeline_start = time.monotonic()

        try:
            with transaction.atomic():
                # Ensure canonical license records exist (idempotent).
                from apps.core.licensing import ensure_licenses

                created = ensure_licenses()
                if created:
                    self.stdout.write(f"  Seeded {created} license(s).")

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
                    elif step == "ingest_opdb":
                        kwargs["opdb"] = opdb_path
                    step_start = time.monotonic()
                    call_command(step, stdout=self.stdout, stderr=self.stderr, **kwargs)
                    elapsed = time.monotonic() - step_start
                    self.stdout.write(f"  ({elapsed:.0f}s)")

                # Post-pipeline: validate cross-entity wikilinks now that all
                # manufacturers, titles, and systems have been ingested.
                validate_cross_entity_wikilinks(
                    Path(export_dir), self.stdout, self.stderr
                )

                if not write:
                    transaction.set_rollback(True)
        finally:
            invalidate_all()

        total = time.monotonic() - pipeline_start
        if not write:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry run complete — no data was modified. ({total:.0f}s)"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Full ingestion pipeline complete. ({total:.0f}s)")
            )
