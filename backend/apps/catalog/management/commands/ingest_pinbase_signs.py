"""Ingest museum sign copy from machine_sign_copy.csv.

Asserts Claims for editorial fields on MachineModel (name, year, month,
manufacturer, manufacturer address, production quantity) and description
on Title (hoisted from educational text).

Creates Credit records from the Heading/Info columns.

Matches MachineModels by IPDB ID. Rows without an IPDB ID are skipped.
"""

from __future__ import annotations

import csv
import logging

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.ingestion.bulk_utils import generate_unique_slug
from apps.catalog.ingestion.parsers import parse_credit_string
from apps.catalog.ingestion.person_lookup import build_person_lookup
from apps.catalog.models import Credit, CreditRole, MachineModel, Person, Title
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
    """Map a heading string to a Credit role, or None if unrecognized."""
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

        from apps.catalog.models import Franchise
        from apps.catalog.resolve import TITLE_DIRECT_FIELDS, _resolve_bulk

        model_ct_id = ContentType.objects.get_for_model(MachineModel).pk
        title_ct_id = ContentType.objects.get_for_model(Title).pk

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

        # Build model PK → Title lookup from active group claims.
        # The title FK may not be populated yet (resolve_claims runs later),
        # so we resolve the mapping from group claim values → Title opdb_ids.
        titles_by_opdb_id = {t.opdb_id: t for t in Title.objects.all()}
        model_title: dict[int, Title] = {}
        group_claims = Claim.objects.filter(
            content_type_id=model_ct_id,
            field_name="title",
            is_active=True,
        ).values_list("object_id", "value")
        for obj_id, group_value in group_claims:
            if group_value:
                title = titles_by_opdb_id.get(str(group_value))
                if title:
                    model_title[obj_id] = title

        model_claims: list[Claim] = []
        title_claims: list[Claim] = []
        credit_queue: list[tuple[int, str, str]] = []
        touched_title_ids: set[int] = set()
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
            self._collect_claims(
                pm,
                row,
                model_ct_id,
                title_ct_id,
                model_title,
                model_claims,
                title_claims,
                touched_title_ids,
                credit_queue,
            )

        self.stdout.write(f"  Matched: {matched}, Skipped: {skipped}")

        # Assert model-level claims.
        claim_stats = Claim.objects.bulk_assert_claims(source, model_claims)
        self.stdout.write(
            f"  Model claims: {claim_stats['unchanged']} unchanged, "
            f"{claim_stats['created']} created, "
            f"{claim_stats['superseded']} superseded, "
            f"{claim_stats['duplicates_removed']} duplicates removed"
        )

        # Assert title-level claims (description).
        if title_claims:
            title_claim_stats = Claim.objects.bulk_assert_claims(source, title_claims)
            self.stdout.write(
                f"  Title claims: {title_claim_stats['created']} created, "
                f"{title_claim_stats['unchanged']} unchanged"
            )

            # Resolve touched titles.
            franchise_lookup = {f.slug: f for f in Franchise.objects.all()}
            _resolve_bulk(
                Title,
                TITLE_DIRECT_FIELDS,
                fk_handlers={"franchise": ("franchise", franchise_lookup)},
                object_ids=touched_title_ids,
            )

        self._bulk_create_persons_and_credits(credit_queue)

        self.stdout.write(self.style.SUCCESS("Sign copy ingestion complete."))

    def _collect_claims(
        self,
        pm: MachineModel,
        row: dict,
        model_ct_id: int,
        title_ct_id: int,
        model_title: dict[int, Title],
        model_claims: list[Claim],
        title_claims: list[Claim],
        touched_title_ids: set[int],
        credit_queue: list[tuple[int, str, str]],
    ) -> None:
        def _add_model(field_name: str, value) -> None:
            model_claims.append(
                Claim(
                    content_type_id=model_ct_id,
                    object_id=pm.pk,
                    field_name=field_name,
                    value=value,
                )
            )

        title = row.get("Title", "").strip()
        if title:
            _add_model("name", title)

        year_str = row.get("Year", "").strip()
        if year_str:
            try:
                _add_model("year", int(year_str))
            except ValueError:
                logger.warning("Invalid year %r for IPDB %s", year_str, pm.ipdb_id)

        month = _parse_month(row.get("Month"))
        if month is not None:
            _add_model("month", month)

        manufacturer = row.get("Manufacturer", "").strip()
        if manufacturer:
            _add_model("manufacturer", manufacturer)

        address = row.get("Address", "").strip()
        if address:
            _add_model("manufacturer_address", address)

        produced = row.get("Produced", "").strip()
        if produced:
            _add_model("production_quantity", produced)

        # MainText → Title.description claim (hoisted from model to title).
        main_text = row.get("MainText", "").strip()
        sources = row.get("Sources/Notes", "").strip()
        title = model_title.get(pm.pk)
        if main_text and title:
            touched_title_ids.add(title.pk)
            title_claims.append(
                Claim(
                    content_type_id=title_ct_id,
                    object_id=title.pk,
                    field_name="description",
                    value=main_text,
                    citation=sources,
                )
            )
        elif main_text:
            logger.warning(
                "IPDB %s has MainText but no title — cannot hoist description",
                pm.ipdb_id,
            )

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

        existing_persons = build_person_lookup()
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
            existing_persons = build_person_lookup()

        self.stdout.write(
            f"  Persons: {len(existing_persons) - persons_created} existing, "
            f"{persons_created} created"
        )

        role_lookup = {r.slug: r for r in CreditRole.objects.all()}
        if not role_lookup:
            raise CommandError(
                "CreditRole table is empty — run ingest_pinbase_taxonomy first."
            )

        existing_credits: set[tuple[int, int, int]] = set(
            Credit.objects.values_list("model_id", "person_id", "role_id")
        )

        new_credits: list[Credit] = []
        for pm_pk, name, role_slug in credit_queue:
            person = existing_persons.get(name.lower())
            if not person:
                logger.warning("Person %r not found after bulk_create", name)
                continue
            role_obj = role_lookup.get(role_slug)
            if not role_obj:
                logger.warning("Unknown credit role %r — skipping", role_slug)
                continue
            credit_key = (pm_pk, person.pk, role_obj.pk)
            if credit_key not in existing_credits:
                new_credits.append(
                    Credit(model_id=pm_pk, person_id=person.pk, role=role_obj)
                )
                existing_credits.add(credit_key)

        credits_created = len(new_credits)
        if new_credits:
            Credit.objects.bulk_create(new_credits)

        self.stdout.write(
            f"  Design credits: "
            f"{len(existing_credits) - credits_created} existing, "
            f"{credits_created} created"
        )
