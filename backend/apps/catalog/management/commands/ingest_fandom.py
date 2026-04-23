"""Ingest pinball data from the Pinball Fandom wiki.

Fetches (or loads from local dumps) three categories of data:

- **Games** (Category:Machines) — parses ``{{Infobox Title}}`` designer fields
  and creates ``Credit`` rows for matched game+person pairs.
- **Persons** (Category:People) — creates missing ``Person`` records and asserts
  a ``bio`` claim from the page's prose stub.
- **Manufacturers** (Category:Manufacturers) — asserts structured claims
  (year_start, year_end, headquarters, website, description) for
  matched ``Manufacturer`` records.

Usage::

    # Live fetch (saves dumps for later re-use):
    python manage.py ingest_fandom \\
        --dump data/ingest_sources/fandom_games.json \\
        --dump-persons data/ingest_sources/fandom_persons.json \\
        --dump-manufacturers data/ingest_sources/fandom_manufacturers.json

    # Re-run from existing dumps (no network calls):
    python manage.py ingest_fandom \\
        --from-dump data/ingest_sources/fandom_games.json \\
        --from-dump-persons data/ingest_sources/fandom_persons.json \\
        --from-dump-manufacturers data/ingest_sources/fandom_manufacturers.json
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from apps.catalog.claims import build_relationship_claim, make_authoritative_scope
from apps.catalog.ingestion.bulk_utils import ManufacturerResolver, generate_unique_slug
from apps.catalog.ingestion.fandom_wiki import (
    FandomManufacturer,
    fetch_game_pages,
    fetch_manufacturer_pages,
    fetch_person_pages,
    parse_game_pages,
    parse_manufacturer_pages,
    parse_person_pages,
)
from apps.catalog.ingestion.person_lookup import build_person_lookup
from apps.catalog.models import CreditRole, MachineModel, Manufacturer, Person
from apps.catalog.resolve import (
    resolve_all_credits,
    resolve_all_entities,
)
from apps.core.validators import validate_no_mojibake
from apps.provenance.models import Claim, Source

logger = logging.getLogger(__name__)


def _last_name(name: str) -> str:
    """Return the last word of a full name, lowercased."""
    parts = name.strip().split()
    return parts[-1].lower() if parts else ""


class Command(BaseCommand):
    help = "Ingest pinball data from the Pinball Fandom wiki."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        # Games dump flags (existing).
        parser.add_argument(
            "--dump",
            default="",
            metavar="PATH",
            help="Save the raw games JSON to this file.",
        )
        parser.add_argument(
            "--from-dump",
            default="",
            dest="from_dump",
            metavar="PATH",
            help="Load games JSON from this file instead of fetching live.",
        )
        # Persons dump flags.
        parser.add_argument(
            "--dump-persons",
            default="",
            dest="dump_persons",
            metavar="PATH",
            help="Save the raw persons JSON to this file.",
        )
        parser.add_argument(
            "--from-dump-persons",
            default="",
            dest="from_dump_persons",
            metavar="PATH",
            help="Load persons JSON from this file instead of fetching live.",
        )
        # Manufacturers dump flags.
        parser.add_argument(
            "--dump-manufacturers",
            default="",
            dest="dump_manufacturers",
            metavar="PATH",
            help="Save the raw manufacturers JSON to this file.",
        )
        parser.add_argument(
            "--from-dump-manufacturers",
            default="",
            dest="from_dump_manufacturers",
            metavar="PATH",
            help="Load manufacturers JSON from this file instead of fetching live.",
        )

    def handle(
        self,
        *args: object,
        **options: Any,  # noqa: ANN401 - argparse-driven Django command kwargs
    ) -> None:
        verbosity = options["verbosity"]
        b, r = "\033[1m", "\033[0m"
        dim, undim = "\033[2m", "\033[22m"

        # ------------------------------------------------------------------
        # 1. Fetch or load games data.
        # ------------------------------------------------------------------
        from_dump = options["from_dump"]
        if from_dump:
            self.stdout.write(f"Loading Fandom games from {from_dump}...")
            with open(from_dump) as f:
                raw_games = json.load(f)
        else:
            self.stdout.write("Fetching game pages from Pinball Fandom wiki...")
            raw_games = fetch_game_pages()

        if options["dump"]:
            with open(options["dump"], "w") as f:
                json.dump(raw_games, f, indent=2)
            self.stdout.write(f"  Saved games dump to {options['dump']}")

        # ------------------------------------------------------------------
        # 2. Fetch or load persons data.
        # ------------------------------------------------------------------
        from_dump_persons = options["from_dump_persons"]
        if from_dump_persons:
            self.stdout.write(f"Loading Fandom persons from {from_dump_persons}...")
            with open(from_dump_persons) as f:
                raw_persons = json.load(f)
        else:
            self.stdout.write("Fetching person pages from Pinball Fandom wiki...")
            raw_persons = fetch_person_pages()

        if options["dump_persons"]:
            with open(options["dump_persons"], "w") as f:
                json.dump(raw_persons, f, indent=2)
            self.stdout.write(f"  Saved persons dump to {options['dump_persons']}")

        # ------------------------------------------------------------------
        # 3. Fetch or load manufacturers data.
        # ------------------------------------------------------------------
        from_dump_mfrs = options["from_dump_manufacturers"]
        if from_dump_mfrs:
            self.stdout.write(f"Loading Fandom manufacturers from {from_dump_mfrs}...")
            with open(from_dump_mfrs) as f:
                raw_mfrs = json.load(f)
        else:
            self.stdout.write("Fetching manufacturer pages from Pinball Fandom wiki...")
            raw_mfrs = fetch_manufacturer_pages()

        if options["dump_manufacturers"]:
            with open(options["dump_manufacturers"], "w") as f:
                json.dump(raw_mfrs, f, indent=2)
            self.stdout.write(
                f"  Saved manufacturers dump to {options['dump_manufacturers']}"
            )

        # ------------------------------------------------------------------
        # 4. Parse all three datasets.
        # ------------------------------------------------------------------
        games = parse_game_pages(raw_games)
        fandom_persons = parse_person_pages(raw_persons)
        fandom_mfrs = parse_manufacturer_pages(raw_mfrs)

        # ------------------------------------------------------------------
        # 5. Upsert Fandom source (priority=20 — lowest, loses to all others).
        # ------------------------------------------------------------------
        source, _ = Source.objects.update_or_create(
            slug="fandom",
            defaults={
                "name": "Pinball Wiki (Fandom)",
                "source_type": "wiki",
                "priority": 20,
                "url": "https://pinball.fandom.com",
            },
        )

        # ------------------------------------------------------------------
        # 6. Load existing DB records into lookup dicts.
        # ------------------------------------------------------------------
        existing_machines: dict[str, MachineModel] = {
            m.name.lower(): m for m in MachineModel.objects.all()
        }
        existing_persons = build_person_lookup()

        # ------------------------------------------------------------------
        # 7. Ingest game credits (as relationship claims).
        # ------------------------------------------------------------------
        credit_claims: list[Claim] = []
        credits_by_role: dict[str, int] = {}
        persons_credited: dict[str, list[str]] = {}
        matched_games = 0
        unmatched_games: list[str] = []
        matched_persons_credits: set[str] = set()
        unmatched_persons_credits: set[str] = set()
        credits_found = 0
        matched_machine_ids: set[int] = set()

        ct_machine = ContentType.objects.get_for_model(MachineModel).pk
        role_slug_to_pk: dict[str, int] = dict(
            CreditRole.objects.values_list("slug", "pk")
        )

        # Also build name → game-titles map for person near-duplicate checking.
        fandom_credits_by_name: dict[str, set[str]] = {}

        for game in games:
            machine = existing_machines.get(game.title.lower())
            if machine is None:
                unmatched_games.append(game.title)
                if verbosity >= 2:
                    self.stdout.write(f"  [NO MATCH] {game.title}")
                continue

            matched_games += 1
            matched_machine_ids.add(machine.pk)
            if verbosity >= 2:
                self.stdout.write(f"  [MATCH]    {game.title}")

            for credit in game.credits:
                fandom_credits_by_name.setdefault(
                    credit.person_name.lower(), set()
                ).add(game.title)
                person = existing_persons.get(credit.person_name.lower())
                if person is None:
                    unmatched_persons_credits.add(credit.person_name)
                    continue
                matched_persons_credits.add(person.name)
                credits_found += 1

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
                credits_by_role[credit.role] = credits_by_role.get(credit.role, 0) + 1
                persons_credited.setdefault(person.name, []).append(
                    f"{credit.role} on {machine.name}"
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

        # ------------------------------------------------------------------
        # 8. Ingest persons.
        # ------------------------------------------------------------------
        # Preload machine → credited persons for near-duplicate detection.
        from apps.catalog.models import Credit

        machine_credited_persons: dict[int, list[Person]] = {}
        for dc in Credit.objects.select_related("person").all():
            if dc.model_id is None:
                continue
            machine_credited_persons.setdefault(dc.model_id, []).append(dc.person)

        person_ct_id = ContentType.objects.get_for_model(Person).pk

        persons_created = 0
        persons_matched_bio = 0
        persons_skipped_no_credits = 0
        persons_skipped_near_dupe: list[str] = []
        pending_person_claims: list[Claim] = []
        existing_person_slugs: set[str] = set(
            Person.objects.values_list("slug", flat=True)
        )

        # Refresh existing_persons after any credits-section changes.
        existing_persons = build_person_lookup()

        for fp in fandom_persons:
            # Skip persons with no game credits — not useful to create.
            if fp.title.lower() not in fandom_credits_by_name:
                persons_skipped_no_credits += 1
                continue

            # Exact name match → update bio claim only.
            person = existing_persons.get(fp.title.lower())
            if person is not None:
                persons_matched_bio += 1
            else:
                # Near-duplicate check: same last name + shared game credit.
                fp_last = _last_name(fp.title)
                near_match: Person | None = None
                near_game_titles: list[str] = []

                for game_title in sorted(
                    fandom_credits_by_name.get(fp.title.lower(), set())
                ):
                    machine = existing_machines.get(game_title.lower())
                    if machine is None:
                        continue
                    for credited_person in machine_credited_persons.get(machine.pk, []):
                        if _last_name(credited_person.name) == fp_last:
                            if near_match is None:
                                near_match = credited_person
                            near_game_titles.append(game_title)
                            break

                if near_match:
                    persons_skipped_near_dupe.append(
                        f"Skipped '{fp.title}': possible match '{near_match.name}' "
                        f"(DB id={near_match.pk}), both credited on "
                        f"[{', '.join(sorted(near_game_titles))}]"
                    )
                    continue

                # Safe to create.
                validate_no_mojibake(fp.title)
                slug = generate_unique_slug(fp.title, existing_person_slugs)
                person = Person.objects.create(name=fp.title, slug=slug)
                existing_persons[fp.title.lower()] = person
                persons_created += 1

            # Assert name + slug + bio claims. Name is asserted so that
            # resolve_person() does not reset the name field (it resets all
            # resolvable fields before applying winning claims; without a
            # name claim, name becomes "").
            pending_person_claims.append(
                Claim(
                    content_type_id=person_ct_id,
                    object_id=person.pk,
                    field_name="name",
                    value=fp.title,
                    citation=fp.citation_url,
                )
            )
            pending_person_claims.append(
                Claim(
                    content_type_id=person_ct_id,
                    object_id=person.pk,
                    field_name="slug",
                    value=person.slug,
                    citation=fp.citation_url,
                )
            )
            if fp.bio:
                pending_person_claims.append(
                    Claim(
                        content_type_id=person_ct_id,
                        object_id=person.pk,
                        field_name="fandom.bio",
                        value=fp.bio,
                        citation=fp.citation_url,
                    )
                )

        if pending_person_claims:
            Claim.objects.bulk_assert_claims(source, pending_person_claims)

        # Resolve claims into Person fields.
        resolved_person_ids: set[int] = {c.object_id for c in pending_person_claims}
        resolve_all_entities(
            Person,
            object_ids=resolved_person_ids,
        )

        # ------------------------------------------------------------------
        # 9. Ingest manufacturers.
        # ------------------------------------------------------------------
        resolver = ManufacturerResolver()
        mfr_ct_id = ContentType.objects.get_for_model(Manufacturer).pk

        mfrs_matched = 0
        unmatched_mfrs: list[str] = []
        pending_mfr_claims: list[Claim] = []
        matched_mfr_objects: list[Manufacturer] = []

        for fm in fandom_mfrs:
            mfr = resolver.resolve_object(fm.title)
            if mfr is None:
                mfr_slug: str | None = resolver.resolve_by_corporate_entity(fm.title)
                if mfr_slug is None:
                    mfr_slug = resolver.resolve_by_corporate_entity_normalized(fm.title)
                if mfr_slug is None:
                    mfr_slug = resolver.resolve_normalized(fm.title)
                mfr = resolver.get_by_slug(mfr_slug) if mfr_slug else None
            if mfr is None:
                unmatched_mfrs.append(fm.title)
                continue

            mfrs_matched += 1
            matched_mfr_objects.append(mfr)
            pending_mfr_claims.extend(_collect_manufacturer_claims(fm, mfr, mfr_ct_id))

        if pending_mfr_claims:
            Claim.objects.bulk_assert_claims(source, pending_mfr_claims)

        matched_mfr_ids = {mfr.pk for mfr in matched_mfr_objects}
        resolve_all_entities(
            Manufacturer,
            object_ids=matched_mfr_ids,
        )

        # ------------------------------------------------------------------
        # 10. Summary.
        # ------------------------------------------------------------------
        if persons_credited:
            items = ", ".join(
                f"{name}: {', '.join(sorted(persons_credited[name]))}"
                for name in sorted(persons_credited)
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Persons with new credits ({len(persons_credited)}): "
                )
                + f"{dim}{items}{undim}"
            )
        if unmatched_persons_credits:
            self.stdout.write(
                self.style.WARNING(
                    f"  Unmatched persons in credits ({len(unmatched_persons_credits)}): "
                )
                + f"{dim}{', '.join(sorted(unmatched_persons_credits))}{undim}"
            )
        if unmatched_games:
            self.stdout.write(
                self.style.WARNING(f"  Unmatched games ({len(unmatched_games)}): ")
                + f"{dim}{', '.join(sorted(unmatched_games))}{undim}"
            )
        if persons_skipped_near_dupe:
            self.stdout.write(
                self.style.WARNING(
                    f"  Persons skipped (near-duplicate, {len(persons_skipped_near_dupe)}):"
                )
            )
            for msg in persons_skipped_near_dupe:
                self.stdout.write(f"    {dim}{msg}{undim}")
        if unmatched_mfrs:
            self.stdout.write(
                self.style.WARNING(
                    f"  Unmatched manufacturers ({len(unmatched_mfrs)}): "
                )
                + f"{dim}{', '.join(sorted(unmatched_mfrs))}{undim}"
            )

        role_breakdown = ", ".join(
            f"{role}: {n}"
            for role, n in sorted(credits_by_role.items(), key=lambda x: -x[1])
        )
        n_games = len(games)
        n_persons_credits = len(matched_persons_credits) + len(
            unmatched_persons_credits
        )
        n_fandom_persons = len(fandom_persons)
        n_mfrs = len(fandom_mfrs)

        self.stdout.write(
            f"{b}  Games:        {r} {n_games} found, {matched_games} matched, "
            f"{len(unmatched_games)} unmatched"
        )
        self.stdout.write(
            f"{b}  Credits:      {r} {credits_found} found"
            + (f" {dim}({role_breakdown}){undim}" if role_breakdown else "")
        )
        self.stdout.write(
            f"{b}  Persons (credits):{r} {n_persons_credits} found, "
            f"{len(matched_persons_credits)} matched, "
            f"{len(unmatched_persons_credits)} unmatched"
        )
        persons_skipped_total = persons_skipped_no_credits + len(
            persons_skipped_near_dupe
        )
        self.stdout.write(
            f"{b}  Persons (pages):{r} {n_fandom_persons} found, "
            f"{persons_matched_bio} matched, {persons_created} created, "
            f"{persons_skipped_total} skipped"
            + (
                f" {dim}({persons_skipped_no_credits} no credits, "
                f"{len(persons_skipped_near_dupe)} near-dupe){undim}"
                if persons_skipped_total
                else ""
            )
        )
        self.stdout.write(
            f"{b}  Manufacturers:{r} {n_mfrs} found, {mfrs_matched} matched, "
            f"{len(unmatched_mfrs)} unmatched"
        )
        self.stdout.write(self.style.SUCCESS("Fandom ingestion complete."))


def _collect_manufacturer_claims(
    fm: FandomManufacturer,
    mfr: Manufacturer,
    ct_id: int,
) -> list[Claim]:
    """Build unsaved Claim objects for non-empty Fandom manufacturer fields."""
    claims: list[Claim] = []
    citation = fm.citation_url

    def add(
        field_name: str,
        value: Any,  # noqa: ANN401 - claim value is arbitrary JSON
    ) -> None:
        if value is not None and value != "":
            claims.append(
                Claim(
                    content_type_id=ct_id,
                    object_id=mfr.pk,
                    field_name=field_name,
                    value=value,
                    citation=citation,
                )
            )

    # Include name so that resolve_manufacturer() does not reset the name field
    # (it resets all resolvable fields before applying winning claims).
    add("name", fm.title)
    add("fandom.description", fm.description)
    add("website", fm.website)
    # year_start, year_end, headquarters are now on CorporateEntity.
    # TODO: Fandom ingest should create CE claims instead of Manufacturer claims.

    return claims
