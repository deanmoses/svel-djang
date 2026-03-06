"""Seed CorporateEntity + Address records from data/corporate_entities.json.

Creates or updates CorporateEntity records linked to their parent
Manufacturer, then asserts editorial claims for name and years_active.
Also creates Address records from optional headquarters fields.

Runs after ingest_pinbase_manufacturers (for Manufacturer records).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from apps.catalog.models import Address, CorporateEntity, Manufacturer
from apps.catalog.resolve import resolve_corporate_entity
from apps.provenance.models import Claim, Source

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).parents[5] / "data" / "corporate_entities.json"


class Command(BaseCommand):
    help = "Seed CorporateEntity records from data/corporate_entities.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(DEFAULT_PATH),
            help="Path to corporate_entities.json seed file.",
        )

    def handle(self, *args, **options):
        path = options["path"]
        with open(path) as f:
            entries = json.load(f)

        # Pre-fetch manufacturer lookup by slug.
        mfr_by_slug: dict[str, Manufacturer] = {
            m.slug: m for m in Manufacturer.objects.all()
        }

        source, _ = Source.objects.update_or_create(
            slug="editorial",
            defaults={
                "name": "Editorial",
                "source_type": Source.SourceType.EDITORIAL,
                "priority": 300,
            },
        )
        ct_id = ContentType.objects.get_for_model(CorporateEntity).pk

        # Pre-fetch existing (manufacturer_id, name) pairs for counts.
        existing_keys = set(
            CorporateEntity.objects.values_list("manufacturer_id", "name")
        )

        # Build instances from JSON, tracking which entries have addresses.
        objs = []
        valid_entries = []
        missing_mfr: list[str] = []

        for entry in entries:
            mfr_slug = entry["manufacturer_slug"]
            mfr = mfr_by_slug.get(mfr_slug)
            if mfr is None:
                missing_mfr.append(mfr_slug)
                logger.warning(
                    "Manufacturer slug %r not found for CE %r",
                    mfr_slug,
                    entry["name"],
                )
                continue

            name = entry["name"]
            year_start = entry.get("year_start")
            year_end = entry.get("year_end")
            if year_start and year_end:
                years_active = f"{year_start}-{year_end}"
            elif year_start:
                years_active = f"{year_start}-present"
            else:
                years_active = ""

            objs.append(
                CorporateEntity(manufacturer=mfr, name=name, years_active=years_active)
            )
            valid_entries.append(entry)

        # Bulk upsert: single INSERT ... ON CONFLICT DO UPDATE.
        objs = CorporateEntity.objects.bulk_create(
            objs,
            update_conflicts=True,
            unique_fields=["manufacturer", "name"],
            update_fields=["years_active"],
        )

        created = sum(
            1 for o in objs if (o.manufacturer_id, o.name) not in existing_keys
        )
        updated = len(objs) - created

        self.stdout.write(
            f"  Corporate entities seed: {created} created, {updated} updated"
        )

        # Create Address records (conditional, small count — stays row-by-row).
        addresses_created = 0
        for obj, entry in zip(objs, valid_entries):
            city = entry.get("headquarters_city", "")
            state = entry.get("headquarters_state", "")
            country = entry.get("headquarters_country", "")
            if city or state or country:
                _, addr_created = Address.objects.get_or_create(
                    corporate_entity=obj,
                    city=city,
                    state=state,
                    country=country,
                )
                if addr_created:
                    addresses_created += 1

        if addresses_created:
            self.stdout.write(f"  Addresses: {addresses_created} created")
        if missing_mfr:
            self.stderr.write(
                f"  Warning: {len(missing_mfr)} missing manufacturer slug(s): "
                + ", ".join(sorted(set(missing_mfr)))
            )

        # Assert claims and resolve.
        pending_claims: list[Claim] = []
        for obj in objs:
            pending_claims.append(
                Claim(
                    content_type_id=ct_id,
                    object_id=obj.pk,
                    field_name="name",
                    value=obj.name,
                )
            )
            if obj.years_active:
                pending_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=obj.pk,
                        field_name="years_active",
                        value=obj.years_active,
                    )
                )

        if pending_claims:
            stats = Claim.objects.bulk_assert_claims(source, pending_claims)
            self.stdout.write(
                f"  Claims: {stats['unchanged']} unchanged, "
                f"{stats['created']} created, {stats['superseded']} superseded"
            )
            for ce in objs:
                resolve_corporate_entity(ce)

        self.stdout.write(
            self.style.SUCCESS("Corporate entity seed ingestion complete.")
        )
