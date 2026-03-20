"""Pull ingest sources from R2 and run the full ingestion pipeline.

Convenience command for Railway production: one command to download
data and run ingest_all.

Usage (Railway SSH):
    .venv/bin/python manage.py pull_and_ingest

Usage (local):
    uv run python manage.py pull_and_ingest --dest ../data/ingest_sources
"""

from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Pull ingest sources from R2, then run ingest_all."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dest",
            default="/tmp/ingest_sources",
            help="Local directory to download into (default: /tmp/ingest_sources).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run ingest_all without --write (rolls back changes).",
        )

    def handle(self, **options):
        dest = options["dest"]
        write = not options["dry_run"]

        self.stdout.write(
            self.style.MIGRATE_HEADING("Pulling ingest sources from R2...")
        )
        call_command(
            "pull_ingest_sources",
            dest=dest,
            stdout=self.stdout,
            stderr=self.stderr,
        )

        self.stdout.write(self.style.MIGRATE_HEADING("Running ingest pipeline..."))
        kwargs = {
            "ipdb": f"{dest}/ipdb_xantari.json",
            "opdb": f"{dest}/opdb_export_machines.json",
            "opdb_changelog": f"{dest}/opdb_changelog.json",
            "export_dir": f"{dest}/pinbase/",
        }
        if write:
            kwargs["write"] = True

        call_command(
            "ingest_all",
            stdout=self.stdout,
            stderr=self.stderr,
            **kwargs,
        )

        self.stdout.write(self.style.SUCCESS("Done."))
