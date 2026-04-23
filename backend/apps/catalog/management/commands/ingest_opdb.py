"""Ingest pinball machines from an OPDB JSON dump.

Thin command: parse → build plan → apply plan.
All source-specific logic lives in the adapter module.
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.ingestion.apply import apply_plan
from apps.catalog.ingestion.constants import DEFAULT_OPDB_PATH
from apps.catalog.ingestion.opdb.adapter import (
    build_opdb_plan,
    compute_fingerprint,
    get_or_create_source,
    parse_opdb_records,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Ingest pinball machines from an OPDB JSON dump."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--opdb",
            default=DEFAULT_OPDB_PATH,
            help="Path to OPDB JSON dump.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and diff without writing to the database.",
        )

    def handle(
        self,
        *args: object,
        **options: Any,  # noqa: ANN401 - argparse-driven Django command kwargs
    ) -> None:
        opdb_path = options["opdb"]
        dry_run = options["dry_run"]

        # Parse.
        with open(opdb_path) as f:
            raw_data = json.load(f)

        try:
            records = parse_opdb_records(raw_data)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"Parsed {len(records)} OPDB records.")

        # Build plan.
        source = get_or_create_source()
        fingerprint = compute_fingerprint(opdb_path)
        plan = build_opdb_plan(records, source, fingerprint)

        self.stdout.write(
            f"Plan: {plan.records_matched} matched, "
            f"{len(plan.entities)} new entities, "
            f"{len(plan.assertions)} assertions"
        )

        # Apply.
        report = apply_plan(plan, dry_run=dry_run)

        # Report.
        prefix = "[DRY RUN] " if dry_run else ""
        self.stdout.write(
            f"{prefix}Created: {report.records_created}, "
            f"Asserted: {report.asserted}, "
            f"Unchanged: {report.unchanged}, "
            f"Superseded: {report.superseded}"
        )
        if report.retracted:
            self.stdout.write(f"{prefix}Retracted: {report.retracted}")
        if report.rejected:
            self.stdout.write(self.style.ERROR(f"{prefix}Rejected: {report.rejected}"))

        for warning in report.warnings:
            self.stdout.write(self.style.WARNING(f"  {warning}"))
        for error in report.errors:
            self.stdout.write(self.style.ERROR(f"  {error}"))

        self.stdout.write(self.style.SUCCESS(f"{prefix}OPDB ingestion complete."))
