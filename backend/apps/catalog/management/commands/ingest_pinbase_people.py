"""Seed Person records and aliases from data/people.json.

Creates or updates Person records with canonical names and slugs, then
syncs PersonAlias rows so external ingest commands can match variant
spellings to the correct person.

Runs before external sources (IPDB, OPDB) and before ingest_pinbase_series
(which creates credits referencing these people).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from apps.catalog.models import Person, PersonAlias
from apps.provenance.models import Claim, Source

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).parents[5] / "data" / "people.json"


class Command(BaseCommand):
    help = "Seed Person records and aliases from data/people.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(DEFAULT_PATH),
            help="Path to people.json.",
        )

    def handle(self, *args, **options):
        path = options["path"]
        with open(path) as f:
            entries = json.load(f)

        # --- Create/update Person records ---

        existing_slugs = set(Person.objects.values_list("slug", flat=True))

        objs = [Person(slug=e["slug"], name=e["name"]) for e in entries]

        objs = Person.objects.bulk_create(
            objs,
            update_conflicts=True,
            unique_fields=["slug"],
            update_fields=["name"],
        )

        persons_created = sum(1 for o in objs if o.slug not in existing_slugs)
        persons_updated = len(objs) - persons_created
        persons_by_slug = {o.slug: o for o in objs}

        self.stdout.write(
            f"  People: {persons_created} created, {persons_updated} updated"
        )

        # --- Assert name claims ---

        source, _ = Source.objects.get_or_create(
            slug="pinbase",
            defaults={
                "name": "Pinbase",
                "source_type": Source.SourceType.EDITORIAL,
                "priority": 300,
                "description": "Pinbase curated data.",
            },
        )

        ct_id = ContentType.objects.get_for_model(Person).pk

        pending_claims: list[Claim] = []
        for entry in entries:
            person = persons_by_slug.get(entry["slug"])
            if not person:
                continue
            for field in ("name", "description"):
                value = entry.get(field, "")
                if value:
                    pending_claims.append(
                        Claim(
                            content_type_id=ct_id,
                            object_id=person.pk,
                            field_name=field,
                            value=value,
                        )
                    )

        if pending_claims:
            claim_stats = Claim.objects.bulk_assert_claims(source, pending_claims)
            self.stdout.write(
                f"  Claims: {claim_stats['created']} created, "
                f"{claim_stats['unchanged']} unchanged"
            )

        # --- Sync PersonAlias rows ---

        # Build desired state from JSON.
        desired: dict[int, dict[str, str]] = {}  # person_pk → {lower_value: value}
        for entry in entries:
            person = persons_by_slug.get(entry["slug"])
            if not person:
                continue
            aliases = entry.get("aliases", [])
            if aliases:
                desired[person.pk] = {a.lower(): a for a in aliases}

        all_person_pks = {p.pk for p in objs}

        # Fetch existing aliases for these people.
        existing_aliases = list(
            PersonAlias.objects.filter(person_id__in=all_person_pks).values_list(
                "pk", "person_id", "value"
            )
        )

        existing_by_person: dict[
            int, dict[str, int]
        ] = {}  # person_pk → {lower_value: alias_pk}
        for pk, person_id, value in existing_aliases:
            existing_by_person.setdefault(person_id, {})[value.lower()] = pk

        # Diff: create new, delete stale.
        to_create: list[PersonAlias] = []
        stale_pks: list[int] = []

        for person_pk in all_person_pks:
            desired_map = desired.get(person_pk, {})
            existing_map = existing_by_person.get(person_pk, {})

            for lower_val, original_val in desired_map.items():
                if lower_val not in existing_map:
                    to_create.append(
                        PersonAlias(person_id=person_pk, value=original_val)
                    )

            for lower_val, alias_pk in existing_map.items():
                if lower_val not in desired_map:
                    stale_pks.append(alias_pk)

        aliases_created = len(to_create)
        aliases_deleted = len(stale_pks)

        if stale_pks:
            PersonAlias.objects.filter(pk__in=stale_pks).delete()
        if to_create:
            PersonAlias.objects.bulk_create(to_create)

        self.stdout.write(
            f"  Aliases: {aliases_created} created, {aliases_deleted} deleted"
        )
        self.stdout.write(self.style.SUCCESS("People seed ingestion complete."))
