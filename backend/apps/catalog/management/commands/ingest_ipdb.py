"""Ingest pinball machines from an IPDB JSON dump.

Thin command wrapper: parses args, calls build_ipdb_plan() → apply_plan(),
and prints a report.  All logic lives in the adapter module.
"""

from __future__ import annotations

import argparse
from typing import Any

from django.core.management.base import BaseCommand

from apps.catalog.ingestion.apply import apply_plan
from apps.catalog.ingestion.constants import DEFAULT_IPDB_PATH
from apps.catalog.ingestion.ipdb.adapter import (
    build_ipdb_plan,
    compute_fingerprint,
    get_or_create_source,
    parse_ipdb_records,
)


class Command(BaseCommand):
    help = "Ingest pinball machines from an IPDB JSON dump."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--ipdb",
            default=DEFAULT_IPDB_PATH,
            help="Path to IPDB JSON dump.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate plan without writing to the database.",
        )

    def handle(
        self,
        *args: object,
        **options: Any,  # noqa: ANN401 - argparse-driven Django command kwargs
    ) -> None:
        ipdb_path = options["ipdb"]

        records = parse_ipdb_records(ipdb_path)
        source = get_or_create_source()
        fingerprint = compute_fingerprint(ipdb_path)

        self.stdout.write(f"Processing {len(records)} IPDB records...")

        plan = build_ipdb_plan(records, source, fingerprint)

        if options["dry_run"]:
            self.stdout.write("  (dry-run mode — no writes)")

        report = apply_plan(plan, dry_run=options["dry_run"])

        # Print report.
        from apps.catalog.models import MachineModel

        new_mm = sum(1 for e in plan.entities if e.model_class is MachineModel)
        self.stdout.write(
            f"  Models — Created: {new_mm}, Matched: {plan.records_matched}"
        )
        if report.records_created > new_mm:
            self.stdout.write(
                f"  Other entities created: {report.records_created - new_mm}"
            )
        self.stdout.write(
            f"  Claims — Asserted: {report.asserted}, "
            f"Unchanged: {report.unchanged}, "
            f"Superseded: {report.superseded}"
        )
        if report.retracted:
            self.stdout.write(f"  Retracted: {report.retracted}")
        if report.rejected:
            self.stdout.write(self.style.WARNING(f"  Rejected: {report.rejected}"))
        for warning in report.warnings:
            self.stdout.write(self.style.WARNING(f"  {warning}"))
        for error in report.errors:
            self.stdout.write(self.style.ERROR(f"  {error}"))

        self.stdout.write(self.style.SUCCESS("IPDB ingestion complete."))
