"""Ingest museum sign copy from machine_sign_copy.csv.

Asserts Claims for editorial fields (name, year, month, manufacturer,
manufacturer address, production quantity, educational text, sources/notes)
and creates DesignCredit records from the Heading/Info columns.

Matches MachineModels by IPDB ID. Rows without an IPDB ID are skipped.
"""

from __future__ import annotations

import csv
import logging

from django.core.management.base import BaseCommand

from apps.catalog.ingestion.bulk_utils import generate_unique_slug
from apps.catalog.ingestion.parsers import parse_credit_string
from apps.catalog.models import DesignCredit, MachineModel, Person
from apps.provenance.models import Claim, Source

logger = logging.getLogger(__name__)

MONTH_NAMES = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

# Heading text (normalized: lowercased, trailing colon/space stripped) → role.
HEADING_ROLE_MAP = {
    "design by": "design",
    "concept and design by": "design",
    "art by": "art",
    "sound by": "sound",
}


def _parse_month(s: str | None) -> int | None:
    """Parse a month name to its integer (1–12), tolerating minor typos."""
    if not s:
        return None
    key = s.strip().lower()
    if key in MONTH_NAMES:
        return MONTH_NAMES[key]
    for month_name, num in MONTH_NAMES.items():
        if key.startswith(month_name):
            return num
    logger.warning("Unrecognized month: %r", s)
    return None


def _heading_to_role(heading: str) -> str | None:
    """Map a heading string to a DesignCredit role, or None if unrecognized."""
    normalized = heading.strip().lower().rstrip(": ")
    return HEADING_ROLE_MAP.get(normalized)


class Command(BaseCommand):
    help = "Ingest museum sign copy from machine_sign_copy.csv."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            default="../data/dump1/machine_sign_copy.csv",
            help="Path to machine_sign_copy.csv.",
        )

    def handle(self, *args, **options):
        csv_path = options["csv"]

        from django.contrib.contenttypes.models import ContentType

        ct_id = ContentType.objects.get_for_model(MachineModel).pk

        source, _ = Source.objects.update_or_create(
            slug="flip-signs",
            defaults={
                "name": "The Flip Signs",
                "source_type": "editorial",
                "priority": 50,
                "url": "",
            },
        )

        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        self.stdout.write(f"Processing {len(rows)} rows...")

        by_ipdb_id: dict[int, MachineModel] = {
            pm.ipdb_id: pm for pm in MachineModel.objects.filter(ipdb_id__isnull=False)
        }

        pending_claims: list[Claim] = []
        credit_queue: list[tuple[int, str, str]] = []
        matched = 0
        skipped = 0

        for row in rows:
            ipdb_id_str = row.get("IPDBid", "").strip()
            if not ipdb_id_str:
                skipped += 1
                continue
            try:
                ipdb_id = int(ipdb_id_str)
            except ValueError:
                logger.warning("Invalid IPDBid %r, skipping", ipdb_id_str)
                skipped += 1
                continue

            pm = by_ipdb_id.get(ipdb_id)
            if not pm:
                title = row.get("Title", "?")
                logger.warning(
                    "No MachineModel for IPDB id %s (%s), skipping", ipdb_id, title
                )
                skipped += 1
                continue

            matched += 1
            self._collect_claims(pm, row, ct_id, pending_claims, credit_queue)

        self.stdout.write(f"  Matched: {matched}, Skipped: {skipped}")

        claim_stats = Claim.objects.bulk_assert_claims(source, pending_claims)
        self.stdout.write(
            f"  Claims: {claim_stats['unchanged']} unchanged, "
            f"{claim_stats['created']} created, "
            f"{claim_stats['superseded']} superseded, "
            f"{claim_stats['duplicates_removed']} duplicates removed"
        )

        self._bulk_create_persons_and_credits(credit_queue)

        self.stdout.write(self.style.SUCCESS("Sign copy ingestion complete."))

    def _collect_claims(
        self,
        pm: MachineModel,
        row: dict,
        ct_id: int,
        pending_claims: list[Claim],
        credit_queue: list[tuple[int, str, str]],
    ) -> None:
        def _add(field_name: str, value) -> None:
            pending_claims.append(
                Claim(
                    content_type_id=ct_id,
                    object_id=pm.pk,
                    field_name=field_name,
                    value=value,
                )
            )

        title = row.get("Title", "").strip()
        if title:
            _add("name", title)

        year_str = row.get("Year", "").strip()
        if year_str:
            try:
                _add("year", int(year_str))
            except ValueError:
                logger.warning("Invalid year %r for IPDB %s", year_str, pm.ipdb_id)

        month = _parse_month(row.get("Month"))
        if month is not None:
            _add("month", month)

        manufacturer = row.get("Manufacturer", "").strip()
        if manufacturer:
            _add("manufacturer", manufacturer)

        address = row.get("Address", "").strip()
        if address:
            _add("manufacturer_address", address)

        produced = row.get("Produced", "").strip()
        if produced:
            _add("production_quantity", produced)

        main_text = row.get("MainText", "").strip()
        if main_text:
            _add("educational_text", main_text)

        sources = row.get("Sources/Notes", "").strip()
        if sources:
            _add("sources_notes", sources)

        for i in ("1", "2", "3"):
            heading = row.get(f"Heading{i}", "").strip()
            info = row.get(f"Info{i}", "").strip()
            if not heading or not info:
                continue
            role = _heading_to_role(heading)
            if not role:
                logger.warning(
                    "Unrecognized heading %r for IPDB %s", heading, pm.ipdb_id
                )
                continue
            for name in parse_credit_string(info):
                credit_queue.append((pm.pk, name, role))

    def _bulk_create_persons_and_credits(
        self, credit_queue: list[tuple[int, str, str]]
    ) -> None:
        if not credit_queue:
            return

        existing_persons: dict[str, Person] = {
            p.name.lower(): p for p in Person.objects.all()
        }
        existing_slugs: set[str] = set(Person.objects.values_list("slug", flat=True))

        new_persons: list[Person] = []
        seen_names: set[str] = set()
        for _, name, _ in credit_queue:
            key = name.lower()
            if key not in existing_persons and key not in seen_names:
                slug = generate_unique_slug(name, existing_slugs)
                new_persons.append(Person(name=name, slug=slug))
                seen_names.add(key)

        persons_created = len(new_persons)
        if new_persons:
            Person.objects.bulk_create(new_persons)
            existing_persons = {p.name.lower(): p for p in Person.objects.all()}

        self.stdout.write(
            f"  Persons: {len(existing_persons) - persons_created} existing, "
            f"{persons_created} created"
        )

        existing_credits: set[tuple[int, int, str]] = set(
            DesignCredit.objects.values_list("model_id", "person_id", "role")
        )

        new_credits: list[DesignCredit] = []
        for pm_pk, name, role in credit_queue:
            person = existing_persons.get(name.lower())
            if not person:
                logger.warning("Person %r not found after bulk_create", name)
                continue
            credit_key = (pm_pk, person.pk, role)
            if credit_key not in existing_credits:
                new_credits.append(
                    DesignCredit(model_id=pm_pk, person_id=person.pk, role=role)
                )
                existing_credits.add(credit_key)

        credits_created = len(new_credits)
        if new_credits:
            DesignCredit.objects.bulk_create(new_credits)

        self.stdout.write(
            f"  Design credits: "
            f"{len(existing_credits) - credits_created} existing, "
            f"{credits_created} created"
        )
