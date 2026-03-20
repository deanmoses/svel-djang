"""Ingest pinball manufacturer data from Wikidata via SPARQL.

Fetches (or loads from a local dump) Wikidata manufacturers linked to
pinball machines, matches them to existing Manufacturer records by name,
asserts biographical claims (founded/dissolved year, country, headquarters,
description, logo, website), sets wikidata_id, and resolves claims.

Usage::

    # Live fetch (also saves a dump for inspection):
    python manage.py ingest_wikidata_manufacturers --dump /tmp/mfr_raw.json

    # Re-run from an existing dump (skips network call):
    python manage.py ingest_wikidata_manufacturers --from-dump /tmp/mfr_raw.json
"""

from __future__ import annotations

import json
import logging

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from apps.catalog.ingestion.bulk_utils import ManufacturerResolver
from apps.catalog.ingestion.wikidata_sparql import (
    WikidataManufacturer,
    fetch_manufacturer_sparql,
    parse_manufacturer_sparql_results,
)
from apps.catalog.models import Manufacturer
from apps.catalog.resolve import (
    MANUFACTURER_DIRECT_FIELDS,
    _resolve_bulk,
)
from apps.provenance.models import Claim, Source

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Ingest pinball manufacturer data from Wikidata via SPARQL."

    def add_arguments(self, parser):
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
        parser.add_argument(
            "--timeout",
            type=int,
            default=15,
            metavar="SECONDS",
            help="SPARQL query timeout in seconds (default: 15).",
        )

    def handle(self, *args, **options):
        dump_path = options["dump"]
        from_dump = options["from_dump"]

        timeout = options["timeout"]

        # 1. Fetch or load SPARQL data.
        if from_dump:
            self.stdout.write(f"Loading SPARQL data from {from_dump}...")
            with open(from_dump) as f:
                raw_data = json.load(f)
        else:
            self.stdout.write(
                "Fetching manufacturer data from Wikidata SPARQL endpoint..."
            )
            raw_data = fetch_manufacturer_sparql(timeout=timeout)

        # 2. Optionally save dump.
        if dump_path:
            with open(dump_path, "w") as f:
                json.dump(raw_data, f, indent=2)
            self.stdout.write(f"  Saved raw dump to {dump_path}")

        # 3. Parse into WikidataManufacturer list.
        wikidata_manufacturers = parse_manufacturer_sparql_results(raw_data)
        self.stdout.write(
            f"  Found {len(wikidata_manufacturers)} manufacturers in Wikidata"
        )

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

        # 5. Set up manufacturer resolver and content type.
        resolver = ManufacturerResolver()
        ct_id = ContentType.objects.get_for_model(Manufacturer).pk

        # 6. Match, report, collect claims.
        self.stdout.write("\nWikidata match report:")
        pending_claims: list[Claim] = []
        matched_pairs: list[tuple[WikidataManufacturer, Manufacturer]] = []
        matched_count = 0
        unmatched_count = 0

        for wm in wikidata_manufacturers:
            # Priority: match by Wikidata QID first, then by name.
            mfr = resolver.get_by_wikidata_id(wm.qid)
            match_type = "wikidata_id"
            if mfr is None:
                mfr = resolver.resolve_object(wm.name)
                match_type = "exact"
            if mfr is None:
                mfr = resolver.resolve_normalized_object(wm.name)
                match_type = "normalized"
            if mfr is None:
                unmatched_count += 1
                self.stdout.write(f"  [NO MATCH]  {wm.name} ({wm.qid})")
                continue

            tag = {
                "wikidata_id": "MATCH:QID",
                "exact": "MATCH",
                "normalized": "MATCH~",
            }[match_type]
            self.stdout.write(f"  [{tag:10s}] {wm.name} ({wm.qid}) → {mfr.name}")
            pending_claims.extend(_collect_manufacturer_claims(wm, mfr, ct_id))
            matched_pairs.append((wm, mfr))
            matched_count += 1

        # 7. Bulk-assert all claims.
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

        # 8. Set wikidata_id on matched manufacturers.
        for wm, mfr in matched_pairs:
            if mfr.wikidata_id != wm.qid:
                mfr.wikidata_id = wm.qid
                mfr.save(update_fields=["wikidata_id", "updated_at"])

        # 9. Bulk-resolve claims into Manufacturer fields.
        matched_mfr_ids = {mfr.pk for _wm, mfr in matched_pairs}
        _resolve_bulk(
            Manufacturer,
            MANUFACTURER_DIRECT_FIELDS,
            object_ids=matched_mfr_ids,
        )

        # 10. Summary.
        self.stdout.write(f"\n  Matched: {matched_count}, Unmatched: {unmatched_count}")
        self.stdout.write(
            self.style.SUCCESS("Wikidata manufacturer ingestion complete.")
        )


def _collect_manufacturer_claims(
    wm: WikidataManufacturer,
    mfr: Manufacturer,
    ct_id: int,
) -> list[Claim]:
    """Build unsaved Claim objects for all non-empty Wikidata manufacturer fields."""
    claims: list[Claim] = []
    citation = wm.citation_url

    def add(field_name: str, value) -> None:
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

    if wm.description:
        add("wikidata.description", wm.description)
    add("logo_url", wm.logo_url)
    if wm.website:
        add("website", wm.website)
    # year_start, year_end, country, headquarters are now on CorporateEntity.
    # TODO: Wikidata ingest should create CE claims instead of Manufacturer claims.

    return claims
