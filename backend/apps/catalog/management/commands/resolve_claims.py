"""Re-resolve all catalog entities from their claims."""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

from apps.catalog.resolve import resolve_all


class Command(BaseCommand):
    help = "Re-resolve all catalog entities from their active claims."

    def handle(self, *args, **options):
        # Silence per-query SQL logging — bulk_update generates huge CASE WHEN
        # statements that produce tens of MB of debug output.
        logging.getLogger("django.db.backends").setLevel(logging.WARNING)

        self.stdout.write("Resolving machine model claims...")
        model_count = resolve_all(stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS(f"Resolved {model_count} models."))

        from apps.catalog.cache import invalidate_all

        invalidate_all()
