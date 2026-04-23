"""Ingest pinball person data from Wikidata via SPARQL.

Fetches (or loads from a local dump) Wikidata persons associated with
pinball machines, matches them to existing Person records by name, asserts
biographical claims, sets wikidata_id, and resolves claims into model fields.

Usage::

    # Live fetch (also saves a dump for inspection):
    python manage.py ingest_wikidata --dump /tmp/wikidata_raw.json

    # Re-run from an existing dump (skips network call):
    python manage.py ingest_wikidata --from-dump /tmp/wikidata_raw.json
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from apps.catalog.claims import build_relationship_claim, make_authoritative_scope
from apps.catalog.ingestion.person_lookup import build_person_lookup
from apps.catalog.ingestion.wikidata_sparql import (
    WikidataPerson,
    fetch_sparql,
    parse_sparql_results,
    parse_wikidata_date,
)
from apps.catalog.models import CreditRole, MachineModel, Person
from apps.catalog.resolve import (
    resolve_all_credits,
    resolve_all_entities,
)
from apps.provenance.models import Claim, Source

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Ingest pinball person data from Wikidata via SPARQL."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--dump",
            default="",
            metavar="PATH",
            help="Save the raw SPARQL JSON response to this file.",
        )
        parser.add_argument(
            "--from-dump",
            default="",
            dest="from_dump",
            metavar="PATH",
            help="Load SPARQL JSON from this file instead of fetching live.",
        )

    def handle(
        self,
        *args: object,
        **options: Any,  # noqa: ANN401 - argparse-driven Django command kwargs
    ) -> None:
        dump_path = options["dump"]
        from_dump = options["from_dump"]

        # 1. Fetch or load SPARQL data.
        if from_dump:
            self.stdout.write(f"Loading SPARQL data from {from_dump}...")
            with open(from_dump) as f:
                raw_data = json.load(f)
        else:
            self.stdout.write("Fetching data from Wikidata SPARQL endpoint...")
            raw_data = fetch_sparql()

        # 2. Optionally save dump.
        if dump_path:
            with open(dump_path, "w") as f:
                json.dump(raw_data, f, indent=2)
            self.stdout.write(f"  Saved raw dump to {dump_path}")

        # 3. Parse into WikidataPerson list.
        wikidata_persons = parse_sparql_results(raw_data)
        self.stdout.write(f"  Found {len(wikidata_persons)} persons in Wikidata")

        # 4. Upsert Wikidata source.
        source, _ = Source.objects.update_or_create(
            slug="wikidata",
            defaults={
                "name": "Wikidata",
                "source_type": "database",
                "priority": 75,
                "url": "https://www.wikidata.org",
            },
        )

        # 5. Load existing Person records and a set of person PKs that have credits.
        from apps.catalog.models import Credit

        existing_persons = build_person_lookup()
        persons_with_credits: set[int] = set(
            Credit.objects.values_list("person_id", flat=True).distinct()
        )

        ct_id = ContentType.objects.get_for_model(Person).pk

        # 6 + 7. Match, score, report, collect claims.
        self.stdout.write("\nWikidata match report:")
        pending_claims: list[Claim] = []
        matched_pairs: list[tuple[WikidataPerson, Person]] = []
        matched_count = 0
        unmatched_count = 0

        for wp in wikidata_persons:
            person = existing_persons.get(wp.name.lower())
            if person is None:
                unmatched_count += 1
                self.stdout.write(f"  [NO MATCH]   {wp.name} ({wp.qid})")
                continue

            confidence, reason = _calculate_confidence(wp, person, persons_with_credits)
            self.stdout.write(
                f"  [MATCH {confidence:.2f}] {wp.name} ({wp.qid}) — {reason}"
            )

            pending_claims.extend(_collect_person_claims(wp, person, ct_id))
            matched_pairs.append((wp, person))
            matched_count += 1

        # 8. Bulk-assert all claims.
        if pending_claims:
            stats = Claim.objects.bulk_assert_claims(source, pending_claims)
            self.stdout.write(
                f"\n  Claims: {stats['unchanged']} unchanged, "
                f"{stats['created']} created, "
                f"{stats['superseded']} superseded, "
                f"{stats['duplicates_removed']} duplicates removed"
            )
        else:
            self.stdout.write("\n  Claims: 0 (no matches)")

        # 9. Set wikidata_id on matched persons.
        for wp, person in matched_pairs:
            if person.wikidata_id != wp.qid:
                person.wikidata_id = wp.qid
                person.save(update_fields=["wikidata_id", "updated_at"])

        # Bulk-resolve claims into Person fields.
        matched_person_ids = {person.pk for _wp, person in matched_pairs}
        resolve_all_entities(
            Person,
            object_ids=matched_person_ids,
        )

        # 10. Assert credit relationship claims for matched (machine, person) pairs.
        existing_machines: dict[str, MachineModel] = {
            m.name.lower(): m for m in MachineModel.objects.all()
        }
        ct_machine = ContentType.objects.get_for_model(MachineModel).pk
        role_slug_to_pk: dict[str, int] = dict(
            CreditRole.objects.values_list("slug", "pk")
        )
        credit_claims: list[Claim] = []
        unmatched_machines: set[str] = set()
        matched_machine_ids: set[int] = set()

        for wp, person in matched_pairs:
            for credit in wp.credits:
                machine = existing_machines.get(credit.work_label.lower())
                if machine is None:
                    unmatched_machines.add(credit.work_label)
                    continue
                matched_machine_ids.add(machine.pk)
                role_slug = credit.role.strip().lower()
                role_pk = role_slug_to_pk.get(role_slug)
                if role_pk is None:
                    logger.warning(
                        "Unknown CreditRole slug %r for %s on %s — skipping",
                        role_slug,
                        person.name,
                        machine.name,
                    )
                    continue
                claim_key, value = build_relationship_claim(
                    "credit",
                    {"person": person.pk, "role": role_pk},
                )
                credit_claims.append(
                    Claim(
                        content_type_id=ct_machine,
                        object_id=machine.pk,
                        field_name="credit",
                        claim_key=claim_key,
                        value=value,
                    )
                )

        if credit_claims:
            auth_scope = make_authoritative_scope(MachineModel, matched_machine_ids)
            credit_stats = Claim.objects.bulk_assert_claims(
                source,
                credit_claims,
                sweep_field="credit",
                authoritative_scope=auth_scope,
            )
            self.stdout.write(
                f"  Credit claims: {credit_stats['unchanged']} unchanged, "
                f"{credit_stats['created']} created, "
                f"{credit_stats['superseded']} superseded, "
                f"{credit_stats['swept']} swept"
            )
            # Resolve credit claims into materialized Credit rows.
            resolve_all_credits(model_ids=matched_machine_ids)
        else:
            self.stdout.write("  Credit claims: 0 (no matches)")
        if unmatched_machines:
            self.stdout.write(f"  Unmatched machines: {sorted(unmatched_machines)}")

        # 11. Summary.
        self.stdout.write(f"\n  Matched: {matched_count}, Unmatched: {unmatched_count}")
        self.stdout.write(self.style.SUCCESS("Wikidata ingestion complete."))


def _calculate_confidence(
    wp: WikidataPerson,
    person: Person,
    persons_with_credits: set[int],
) -> tuple[float, str]:
    """Return (confidence, reason) for a name-matched Wikidata person.

    Wikidata persons are already pinball-specific (they were found by
    querying for credits on pinball machines), so a name match against
    our DB is meaningful.  We boost confidence when the person already
    has credits in our DB, confirming they're active in the pinball world.
    """
    if person.pk in persons_with_credits:
        return 0.95, "name match; person has credits in DB"
    return 0.85, "name match; person has no credits in DB to verify"


def _collect_person_claims(
    wp: WikidataPerson,
    person: Person,
    ct_id: int,
) -> list[Claim]:
    """Build unsaved Claim objects for all non-empty Wikidata fields."""
    claims: list[Claim] = []
    citation = wp.citation_url

    def add(
        field_name: str,
        value: Any,  # noqa: ANN401 - claim value is arbitrary JSON
    ) -> None:
        if value is not None and value != "":
            claims.append(
                Claim(
                    content_type_id=ct_id,
                    object_id=person.pk,
                    field_name=field_name,
                    value=value,
                    citation=citation,
                )
            )

    add("wikidata_id", wp.qid)
    add("name", wp.name)

    if wp.description:
        add("wikidata.description", wp.description)

    birth_year, birth_month, birth_day = parse_wikidata_date(
        wp.birth_date, wp.birth_precision
    )
    add("birth_year", birth_year)
    add("birth_month", birth_month)
    add("birth_day", birth_day)

    death_year, death_month, death_day = parse_wikidata_date(
        wp.death_date, wp.death_precision
    )
    add("death_year", death_year)
    add("death_month", death_month)
    add("death_day", death_day)

    add("birth_place", wp.birth_place)
    add("nationality", wp.nationality)
    add("photo_url", wp.photo_url)

    return claims
