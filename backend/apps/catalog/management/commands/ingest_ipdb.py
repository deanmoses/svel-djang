"""Ingest pinball machines from an IPDB JSON dump.

Creates MachineModel records, asserts Claims for each field, and creates
Person/Credit records for design credits.

Claims, Persons, and Credits are collected during the main loop and
written in bulk after all records are processed.
"""

from __future__ import annotations

import json
from apps.catalog.ingestion.constants import DEFAULT_EXPORT_DIR, DEFAULT_IPDB_PATH
import logging
import re
from html import unescape
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.ingestion.bulk_utils import (
    ManufacturerResolver,
    format_names,
    generate_unique_slug,
)
from apps.catalog.ingestion.constants import IPDB_SKIP_MANUFACTURER_IDS
from apps.catalog.ingestion.ipdb.records import IpdbRecord
from apps.catalog.ingestion.person_lookup import build_person_lookup
from apps.catalog.ingestion.ipdb_title_fixes import TITLE_FIXES
from apps.catalog.ingestion.parsers import (
    parse_credit_string,
    parse_ipdb_date,
    parse_ipdb_location,
    parse_ipdb_machine_type,
    parse_ipdb_manufacturer_string,
)
from apps.catalog.claims import build_relationship_claim, make_authoritative_scope
from apps.catalog.models import (
    Address,
    CorporateEntity,
    GameplayFeature,
    MachineModel,
    Person,
    Theme,
)
from apps.catalog.resolve import (
    resolve_all_credits,
    resolve_all_gameplay_features,
    resolve_all_themes,
)
from apps.provenance.models import Claim, Source

logger = logging.getLogger(__name__)

# IpdbRecord attribute → Claim field_name for direct/extra_data claims.
CLAIM_FIELDS = {
    "title": "name",
    "ipdb_id": "ipdb_id",
    "players": "player_count",
    "production_number": "production_quantity",
    "average_fun_rating": "ipdb_rating",
    # Extra data (no dedicated column) — namespaced by source
    "notable_features": "ipdb.notable_features",
    "notes": "ipdb.notes",
    "toys": "ipdb.toys",
    "marketing_slogans": "ipdb.marketing_slogans",
    "model_number": "ipdb.model_number",
}

# IpdbRecord attribute → Credit role.
CREDIT_FIELDS = {
    "design_by": "design",
    "art_by": "art",
    "dots_animation_by": "animation",
    "mechanics_by": "mechanics",
    "music_by": "music",
    "sound_by": "sound",
    "software_by": "software",
}

# Raw IPDB tag → list of canonical theme slugs.
# After splitting on " - ", each token is looked up here.
# Unmapped tags are logged as warnings.
# TBD: full mapping is a taxonomy decision; this skeleton covers data quality fixes.
IPDB_TAG_MAP: dict[str, list[str]] = {
    # Spelling/encoding fixes
    "Basebal": ["baseball"],
    "BIlliards": ["billiards"],
    "Music \ufffd Singing": ["music"],
    # Duplicate normalization
    "Circus/Carnival": ["circus"],
    "Circus / Carnival": ["circus"],
    "Auto racing": ["auto-racing"],
}


# Structured IPDB token (lowercased, count suffix stripped) → gameplay feature slug.
# Covers the "Feature (N)" entries that appear at the start of notable_features.
_STRUCTURED_FEATURE_MAP: dict[str, str] = {
    "flippers": "flippers",
    "flipper": "flippers",
    "zipper flippers": "flippers",
    "impulse flippers": "flippers",
    "reverse flippers": "flippers",
    "reversed flippers": "flippers",
    "pop bumpers": "pop-bumpers",
    "pop bumper": "pop-bumpers",
    "jet bumpers": "pop-bumpers",
    "slingshots": "slingshots",
    "slingshot": "slingshots",
    "slingshot kickers": "slingshots",
    "drop targets": "drop-targets",
    "drop target": "drop-targets",
    "solitary drop target": "drop-targets",
    "solitary drop targets": "drop-targets",
    "single drop target": "drop-targets",
    "single drop targets": "drop-targets",
    "stand-alone drop target": "drop-targets",
    "standup targets": "standup-targets",
    "standup target": "standup-targets",
    "stand-up targets": "standup-targets",
    "spinning target": "spinners",
    "spinning targets": "spinners",
    "spinners": "spinners",
    "spinner": "spinners",
    "rollunder spinner": "spinners",
    "rollunder spinners": "spinners",
    "ramps": "ramps",
    "ramp": "ramps",
    "captive ball": "captive-ball",
    "captive balls": "captive-ball",
    "kick-out holes": "kick-out-holes",
    "kick-out hole": "kick-out-holes",
    "kickout holes": "kick-out-holes",
    "relay kick-out holes": "kick-out-holes",
    "gobble holes": "gobble-holes",
    "gobble hole": "gobble-holes",
    "magnets": "magnets",
    "magnet": "magnets",
    "electromagnet": "magnets",
    "electromagnets": "magnets",
    "stop magnet": "magnets",
    "stop magnets": "magnets",
    "multiball": "multiball",
}

# Regex patterns for features that appear in narrative text rather than
# the structured "Feature (N)" list.  Each pattern is matched against
# the full notable_features string.
_NARRATIVE_FEATURE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b[Mm]ulti-?ball\b"), "multiball"),
    (re.compile(r"\b[Kk]ickback\b"), "kickback"),
    (re.compile(r"\b[Mm]agna.?[Ss]ave\b"), "magna-save"),
    (re.compile(r"\b[Bb]all [Ss]ave\b"), "ball-save"),
    (re.compile(r"\b[Ss]kill.?[Ss]hot\b"), "skill-shot"),
    (
        re.compile(
            r"\b[Mm]ulti.?level playfield\b"
            r"|\b[Uu]pper playfield\b"
            r"|\b[Ee]levated.{0,20}playfield\b"
            r"|\b[Mm]ini.?playfield\b"
        ),
        "multi-level-playfield",
    ),
    (re.compile(r"\b[Aa]dd.?a.?[Bb]all\b"), "add-a-ball"),
    (re.compile(r"\b[Hh]ead.?to.?[Hh]ead\b"), "head-to-head"),
]


def _load_mpu_to_system_slug(export_dir: str) -> dict[str, str]:
    """Build {mpu_string: system_slug} from the pinbase export's system.json."""
    systems_path = Path(export_dir) / "system.json"
    with open(systems_path) as f:
        systems = json.load(f)
    return {
        mpu: system["slug"]
        for system in systems
        for mpu in system.get("mpu_strings", [])
    }


def _parse_ipdb_themes(raw_theme: str) -> list[str]:
    """Split an IPDB theme string and return canonical theme slugs.

    Splits on `` - `` (and ``, `` for comma-delimited entries), looks up
    each token in IPDB_TAG_MAP (or slugifies if unmapped), and returns
    deduplicated slugs.
    """
    from django.utils.text import slugify

    tags: list[str] = []
    for part in raw_theme.split(" - "):
        for sub in part.split(", "):
            tag = sub.strip()
            if tag:
                tags.append(tag)

    slugs: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        mapped = IPDB_TAG_MAP.get(tag)
        if mapped:
            for slug in mapped:
                if slug not in seen:
                    slugs.append(slug)
                    seen.add(slug)
        else:
            slug = slugify(tag)
            if slug and slug not in seen:
                slugs.append(slug)
                seen.add(slug)
    return slugs


_DROP_TARGET_BANK_RE = re.compile(r"^\d+-bank drop targets?$")
_COUNT_SUFFIX_RE = re.compile(r"\s*\(\d+\)\s*$")


def _parse_ipdb_gameplay_features(raw: str) -> list[str]:
    """Extract gameplay feature slugs from an IPDB notable_features string.

    Two extraction passes:
      1. Structured tokens — comma-separated "Feature (N)" entries are
         stripped of their count suffix and looked up in _STRUCTURED_FEATURE_MAP.
      2. Narrative patterns — regex patterns in _NARRATIVE_FEATURE_PATTERNS are
         matched against the full text for features that appear in prose
         (e.g. "multiball", "kickback", "skill shot").

    Returns deduplicated slugs in discovery order.
    """
    seen: set[str] = set()
    slugs: list[str] = []

    def _add(slug: str) -> None:
        if slug not in seen:
            seen.add(slug)
            slugs.append(slug)

    # Pass 1: structured tokens.
    # Split on commas first, then on periods within each segment,
    # since IPDB uses both as separators between features.
    for segment in raw.split(","):
        for part in segment.split("."):
            token = _COUNT_SUFFIX_RE.sub("", part).strip().lower()
            if not token:
                continue
            mapped = _STRUCTURED_FEATURE_MAP.get(token)
            if mapped:
                _add(mapped)
            elif _DROP_TARGET_BANK_RE.match(token):
                _add("drop-targets")

    # Pass 2: narrative patterns.
    for pattern, slug in _NARRATIVE_FEATURE_PATTERNS:
        if pattern.search(raw):
            _add(slug)

    return slugs


class Command(BaseCommand):
    help = "Ingest pinball machines from an IPDB JSON dump."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ipdb",
            default=DEFAULT_IPDB_PATH,
            help="Path to IPDB JSON dump.",
        )
        parser.add_argument(
            "--export-dir",
            default=DEFAULT_EXPORT_DIR,
            help="Path to exported Pinbase JSON directory.",
        )

    def handle(self, *args, **options):
        ipdb_path = options["ipdb"]
        export_dir = options["export_dir"]
        mpu_to_slug = _load_mpu_to_system_slug(export_dir)

        from django.contrib.contenttypes.models import ContentType

        ct_id = ContentType.objects.get_for_model(MachineModel).pk

        source, _ = Source.objects.update_or_create(
            slug="ipdb",
            defaults={
                "name": "IPDB",
                "source_type": "database",
                "priority": 100,
                "url": "https://www.ipdb.org",
            },
        )

        # Manufacturer resolver (shared lookup + auto-create-on-miss).
        resolver = ManufacturerResolver()
        # Cache CEs for lookup: first by IPDB manufacturer ID, then by name.
        all_ces = list(CorporateEntity.objects.select_related("manufacturer").all())
        ce_by_ipdb_id: dict[int, CorporateEntity] = {
            ce.ipdb_manufacturer_id: ce
            for ce in all_ces
            if ce.ipdb_manufacturer_id is not None
        }
        ce_by_name: dict[str, CorporateEntity] = {ce.name.lower(): ce for ce in all_ces}
        ce_slugs: set[str] = {ce.slug for ce in all_ces}

        with open(ipdb_path) as f:
            data = json.load(f)

        # --- Parse raw JSON into typed records ---
        raw_records = data["Data"]
        records: list[IpdbRecord] = []
        parse_errors = 0
        for raw in raw_records:
            if "IpdbId" not in raw:
                parse_errors += 1
                logger.warning(
                    "IPDB record missing IpdbId (title=%r)",
                    raw.get("Title", "<unknown>"),
                )
                continue
            try:
                records.append(IpdbRecord.from_raw(raw))
            except (KeyError, ValueError, TypeError) as e:
                parse_errors += 1
                logger.warning(
                    "Unparseable IPDB record (id=%s): %s",
                    raw.get("IpdbId", "?"),
                    e,
                )
        if parse_errors:
            raise CommandError(
                f"{parse_errors} IPDB record(s) failed to parse — aborting to prevent partial import. "
                f"Check warnings above for details."
            )

        self.stdout.write(f"Processing {len(records)} IPDB records...")

        # --- Phase 1: Ensure all MachineModels exist ---
        existing_by_ipdb: dict[int, MachineModel] = {
            pm.ipdb_id: pm for pm in MachineModel.objects.filter(ipdb_id__isnull=False)
        }
        existing_slugs: set[str] = set(
            MachineModel.objects.values_list("slug", flat=True)
        )

        new_models: list[MachineModel] = []
        record_models: list[tuple[MachineModel, IpdbRecord, bool]] = []
        skipped = 0

        for rec in records:
            if not rec.ipdb_id:
                skipped += 1
                continue

            title = unescape(TITLE_FIXES.get(rec.ipdb_id, rec.title))

            pm = existing_by_ipdb.get(rec.ipdb_id)
            if pm:
                record_models.append((pm, rec, False))
            else:
                slug = generate_unique_slug(title, existing_slugs)
                pm = MachineModel(ipdb_id=rec.ipdb_id, name=title, slug=slug)
                new_models.append(pm)
                existing_by_ipdb[rec.ipdb_id] = pm
                record_models.append((pm, rec, True))

        created = len(new_models)
        matched = len(record_models) - created
        if new_models:
            MachineModel.objects.bulk_create(new_models)

        self.stdout.write(
            f"  Models — Matched: {matched}, Created: {created}, Skipped: {skipped}"
        )
        if new_models:
            self.stdout.write(
                f"    New: {format_names([pm.name for pm in new_models])}"
            )

        # --- Phase 2: Collect claims, credits, theme slugs, and feature slugs ---
        pending_claims: list[Claim] = []
        credit_queue: list[tuple[int, str, str]] = []
        theme_queue: list[tuple[int, list[str]]] = []  # (model_pk, [slugs])
        gameplay_feature_queue: list[tuple[int, list[str]]] = []
        unknown_mpu_strings: set[str] = set()

        for pm, rec, _was_created in record_models:
            self._collect_record_data(
                pm,
                rec,
                ct_id,
                pending_claims,
                credit_queue,
                theme_queue,
                gameplay_feature_queue,
                mpu_to_slug,
                unknown_mpu_strings,
                resolver,
                ce_by_ipdb_id,
                ce_by_name,
                ce_slugs,
            )

        if unknown_mpu_strings:
            lines = "\n".join(f"  {s}" for s in sorted(unknown_mpu_strings))
            raise CommandError(
                f"Unknown MPU strings not in pinbase systems:\n{lines}\n"
                "Add mpu_strings entries to data/pinbase/systems/ and re-export before re-ingesting."
            )

        # --- Bulk-assert all collected claims ---
        claim_stats = Claim.objects.bulk_assert_claims(source, pending_claims)
        self.stdout.write(
            f"  Claims: {claim_stats['unchanged']} unchanged, "
            f"{claim_stats['created']} created, "
            f"{claim_stats['superseded']} superseded, "
            f"{claim_stats['duplicates_removed']} duplicates removed"
        )

        # --- Assert credit claims and create Persons ---
        all_model_ids = {pm.pk for pm, _, _ in record_models}
        self._bulk_create_persons_and_credits(credit_queue, source, all_model_ids)

        # --- Assert theme claims ---
        self._bulk_create_themes(theme_queue, source, all_model_ids)

        # --- Assert gameplay feature claims ---
        self._bulk_create_gameplay_features(
            gameplay_feature_queue, source, all_model_ids
        )

        self.stdout.write(self.style.SUCCESS("IPDB ingestion complete."))

    def _collect_record_data(
        self,
        pm: MachineModel,
        rec: IpdbRecord,
        ct_id: int,
        pending_claims: list[Claim],
        credit_queue: list[tuple[int, str, str]],
        theme_queue: list[tuple[int, list[str]]],
        gameplay_feature_queue: list[tuple[int, list[str]]],
        mpu_to_slug: dict[str, str],
        unknown_mpu_strings: set[str],
        resolver: ManufacturerResolver,
        ce_by_ipdb_id: dict[int, CorporateEntity],
        ce_by_name: dict[str, CorporateEntity],
        ce_slugs: set[str],
    ) -> None:
        """Collect claims, credits, theme slugs, and feature slugs for a single IPDB record."""
        # Collect claims for mapped fields.
        for attr, claim_field in CLAIM_FIELDS.items():
            value = getattr(rec, attr)
            if value is None or value == "":
                continue
            # Use corrected title for name claims.
            if attr == "title" and rec.ipdb_id in TITLE_FIXES:
                value = TITLE_FIXES[rec.ipdb_id]
            # Convert production number to string.
            if attr == "production_number":
                value = str(value)
            # Decode HTML entities in string values from IPDB.
            if isinstance(value, str):
                value = unescape(value)
            pending_claims.append(
                Claim(
                    content_type_id=ct_id,
                    object_id=pm.pk,
                    field_name=claim_field,
                    value=value,
                )
            )

        # Common abbreviations: each abbreviation becomes its own relationship claim.
        if rec.common_abbreviations:
            for abbrev in rec.common_abbreviations.split(","):
                abbrev = unescape(abbrev.strip())
                if abbrev:
                    claim_key, value = build_relationship_claim(
                        "abbreviation", {"value": abbrev}
                    )
                    pending_claims.append(
                        Claim(
                            content_type_id=ct_id,
                            object_id=pm.pk,
                            field_name="abbreviation",
                            claim_key=claim_key,
                            value=value,
                        )
                    )

        # IPDB "manufacturer" is really a corporate entity with an optional
        # trade name (brand).  Process CE first, then derive the manufacturer.
        mfr_id = rec.manufacturer_id
        raw_mfr = rec.manufacturer
        if mfr_id and mfr_id not in IPDB_SKIP_MANUFACTURER_IDS and raw_mfr:
            parsed = parse_ipdb_manufacturer_string(raw_mfr)
            company = parsed["company_name"]
            trade = parsed["trade_name"]
            location = parsed["location"]

            # --- Step 1: Find or create CorporateEntity ---
            # Priority: match by IPDB manufacturer ID first, then by name.
            ce = ce_by_ipdb_id.get(mfr_id) or ce_by_name.get(company.lower())
            if ce:
                if ce.ipdb_manufacturer_id is None:
                    # CE matched by name but lacks IPDB ID — backfill it.
                    ce.ipdb_manufacturer_id = mfr_id
                    ce.save(update_fields=["ipdb_manufacturer_id"])
                    ce_by_ipdb_id[mfr_id] = ce
            else:
                # Parse years_active "YYYY-YYYY" into founded/dissolved.
                year_start = None
                year_end = None
                ya = parsed["years_active"]
                if ya:
                    parts = ya.split("-")
                    try:
                        year_start = int(parts[0])
                        if len(parts) > 1 and parts[1] != "present":
                            year_end = int(parts[1])
                    except ValueError:
                        raise CommandError(
                            f"Cannot parse years_active {ya!r} for IPDB manufacturer {company!r}"
                        )

                # Resolve manufacturer (brand) — trade name first, then company name.
                display_name = trade or company
                slug = (
                    (trade and resolver.resolve(trade))
                    or resolver.resolve_entity(company)
                    or resolver.resolve(company)
                )
                if not slug:
                    slug = resolver.resolve_or_create(display_name)
                mfr = resolver.get_by_slug(slug)

                ce_slug = generate_unique_slug(company, ce_slugs)
                ce = CorporateEntity.objects.create(
                    manufacturer=mfr,
                    slug=ce_slug,
                    name=company,
                    ipdb_manufacturer_id=mfr_id,
                    year_start=year_start,
                    year_end=year_end,
                )
                ce_by_ipdb_id[mfr_id] = ce
                ce_by_name[company.lower()] = ce

            # --- Step 2: Derive manufacturer claim from the CE's manufacturer ---
            pending_claims.append(
                Claim(
                    content_type_id=ct_id,
                    object_id=pm.pk,
                    field_name="manufacturer",
                    value=ce.manufacturer.slug,
                )
            )

            # --- Step 3: Create address on CE when location is available ---
            if location:
                addr = parse_ipdb_location(location)
                if addr["city"] or addr["state"] or addr["country"]:
                    Address.objects.get_or_create(
                        corporate_entity=ce,
                        city=addr["city"],
                        state=addr["state"],
                        country=addr["country"],
                    )

        # MPU: emit 'system' slug claim if known, else collect for deferred error.
        # Normalize U+FFFD (replacement char from IPDB encoding issues) before lookup.
        mpu_value = rec.mpu.strip().replace("\ufffd", "") if rec.mpu else ""
        if mpu_value:
            system_slug = mpu_to_slug.get(mpu_value)
            if system_slug:
                pending_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=pm.pk,
                        field_name="system",
                        value=system_slug,
                    )
                )
            else:
                unknown_mpu_strings.add(mpu_value)

        # Date fields (year + month from a single IPDB field).
        if rec.date_of_manufacture:
            year, month = parse_ipdb_date(rec.date_of_manufacture)
            if year is not None:
                pending_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=pm.pk,
                        field_name="year",
                        value=year,
                    )
                )
            if month is not None:
                pending_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=pm.pk,
                        field_name="month",
                        value=month,
                    )
                )

        # Technology generation (slug-based, resolved to FK).
        technology_generation = parse_ipdb_machine_type(rec.type_short_name, rec.type)
        if technology_generation:
            pending_claims.append(
                Claim(
                    content_type_id=ct_id,
                    object_id=pm.pk,
                    field_name="technology_generation",
                    value=technology_generation,
                )
            )

        # Image URLs → extra_data claim.
        if rec.image_files:
            urls = [img["Url"] for img in rec.image_files if img.get("Url")]
            if urls:
                pending_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=pm.pk,
                        field_name="ipdb.image_urls",
                        value=urls,
                    )
                )

        # Collect theme slugs for bulk creation later.
        if rec.theme:
            theme_slugs = _parse_ipdb_themes(unescape(rec.theme))
            if theme_slugs:
                theme_queue.append((pm.pk, theme_slugs))

        # Collect gameplay feature slugs for bulk creation later.
        if rec.notable_features:
            feature_slugs = _parse_ipdb_gameplay_features(
                unescape(rec.notable_features)
            )
            if feature_slugs:
                gameplay_feature_queue.append((pm.pk, feature_slugs))

        # Collect design credits for bulk creation later.
        for attr, role in CREDIT_FIELDS.items():
            raw = getattr(rec, attr)
            if not raw:
                continue
            names = parse_credit_string(raw)
            for name in names:
                credit_queue.append((pm.pk, name, role))

    def _bulk_create_persons_and_credits(
        self,
        credit_queue: list[tuple[int, str, str]],
        source,
        all_model_ids: set[int],
    ) -> None:
        """Create Persons and assert credit claims from the credit queue.

        Person records and name claims are created as before.  Credit
        rows are no longer created directly — instead, credit relationship
        claims are asserted and materialized by the resolution layer.
        """
        if not credit_queue:
            return

        from django.contrib.contenttypes.models import ContentType

        # Discover all unique person names needed (includes aliases).
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
            # Refresh to get PKs (includes aliases).
            existing_persons = build_person_lookup()

        self.stdout.write(
            f"  Persons: {len(existing_persons) - persons_created} existing, "
            f"{persons_created} created"
        )

        # Assert name claims for all unique persons referenced in this ingest.
        ct_person = ContentType.objects.get_for_model(Person)
        unique_names = {name.lower(): name for _, name, _ in credit_queue}
        person_claims: list[Claim] = [
            Claim(
                content_type_id=ct_person.pk,
                object_id=existing_persons[key].pk,
                field_name="name",
                value=canonical_name,
            )
            for key, canonical_name in unique_names.items()
            if key in existing_persons
        ]
        person_claim_stats = Claim.objects.bulk_assert_claims(source, person_claims)
        self.stdout.write(
            f"  Person claims: {person_claim_stats['unchanged']} unchanged, "
            f"{person_claim_stats['created']} created, "
            f"{person_claim_stats['superseded']} superseded"
        )

        # Assert credit relationship claims.
        ct_machine = ContentType.objects.get_for_model(MachineModel).pk
        credit_claims: list[Claim] = []
        for pm_pk, name, role in credit_queue:
            person = existing_persons.get(name.lower())
            if not person:
                continue
            claim_key, value = build_relationship_claim(
                "credit",
                {"person_slug": person.slug, "role": role.strip().lower()},
            )
            credit_claims.append(
                Claim(
                    content_type_id=ct_machine,
                    object_id=pm_pk,
                    field_name="credit",
                    claim_key=claim_key,
                    value=value,
                )
            )

        auth_scope = make_authoritative_scope(MachineModel, all_model_ids)
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
        resolve_all_credits([], model_ids=all_model_ids)

    def _bulk_create_themes(
        self,
        theme_queue: list[tuple[int, list[str]]],
        source,
        all_model_ids: set[int],
    ) -> None:
        """Get-or-create Theme objects and assert theme relationship claims.

        Also resolves theme claims into materialized M2M rows.
        """
        if not theme_queue:
            return

        from django.contrib.contenttypes.models import ContentType

        # Discover all unique theme slugs needed.
        all_slugs: set[str] = set()
        for _, slugs in theme_queue:
            all_slugs.update(slugs)

        # Get-or-create Theme objects.
        existing_themes: dict[str, Theme] = {
            t.slug: t for t in Theme.objects.filter(slug__in=all_slugs)
        }
        new_themes: list[Theme] = []
        for slug in sorted(all_slugs - existing_themes.keys()):
            # Derive display name from slug: "auto-racing" → "Auto Racing"
            name = slug.replace("-", " ").title()
            new_themes.append(Theme(name=name, slug=slug))
        if new_themes:
            Theme.objects.bulk_create(new_themes)
            for t in Theme.objects.filter(slug__in=all_slugs):
                existing_themes[t.slug] = t

        themes_created = len(new_themes)
        self.stdout.write(
            f"  Themes: {len(existing_themes) - themes_created} existing, "
            f"{themes_created} created"
        )

        # Build theme relationship claims.
        ct_machine = ContentType.objects.get_for_model(MachineModel).pk
        theme_claims: list[Claim] = []
        for pm_pk, slugs in theme_queue:
            for slug in slugs:
                claim_key, value = build_relationship_claim(
                    "theme", {"theme_slug": slug}
                )
                theme_claims.append(
                    Claim(
                        content_type_id=ct_machine,
                        object_id=pm_pk,
                        field_name="theme",
                        claim_key=claim_key,
                        value=value,
                    )
                )

        auth_scope = make_authoritative_scope(MachineModel, all_model_ids)
        theme_stats = Claim.objects.bulk_assert_claims(
            source,
            theme_claims,
            sweep_field="theme",
            authoritative_scope=auth_scope,
        )
        self.stdout.write(
            f"  Theme claims: {theme_stats['unchanged']} unchanged, "
            f"{theme_stats['created']} created, "
            f"{theme_stats['superseded']} superseded, "
            f"{theme_stats['swept']} swept"
        )

        # Resolve theme claims into materialized M2M rows.
        resolve_all_themes([], model_ids=all_model_ids)

    def _bulk_create_gameplay_features(
        self,
        gameplay_feature_queue: list[tuple[int, list[str]]],
        source,
        all_model_ids: set[int],
    ) -> None:
        """Assert gameplay feature relationship claims and resolve into M2M rows.

        All GameplayFeature records already exist from the taxonomy seed, so
        no get-or-create step is needed — only claim assertion and resolution.
        """
        if not gameplay_feature_queue:
            return

        from django.contrib.contenttypes.models import ContentType

        # Verify all referenced slugs exist.
        all_slugs: set[str] = set()
        for _, slugs in gameplay_feature_queue:
            all_slugs.update(slugs)

        existing_slugs = set(
            GameplayFeature.objects.filter(slug__in=all_slugs).values_list(
                "slug", flat=True
            )
        )
        missing = all_slugs - existing_slugs
        if missing:
            logger.warning(
                "Gameplay feature slugs not found in DB (skipping): %s",
                sorted(missing),
            )

        # Build gameplay feature relationship claims.
        ct_machine = ContentType.objects.get_for_model(MachineModel).pk
        feature_claims: list[Claim] = []
        for pm_pk, slugs in gameplay_feature_queue:
            for slug in slugs:
                if slug not in existing_slugs:
                    continue
                claim_key, value = build_relationship_claim(
                    "gameplay_feature", {"gameplay_feature_slug": slug}
                )
                feature_claims.append(
                    Claim(
                        content_type_id=ct_machine,
                        object_id=pm_pk,
                        field_name="gameplay_feature",
                        claim_key=claim_key,
                        value=value,
                    )
                )

        auth_scope = make_authoritative_scope(MachineModel, all_model_ids)
        feature_stats = Claim.objects.bulk_assert_claims(
            source,
            feature_claims,
            sweep_field="gameplay_feature",
            authoritative_scope=auth_scope,
        )
        self.stdout.write(
            f"  Gameplay feature claims: {feature_stats['unchanged']} unchanged, "
            f"{feature_stats['created']} created, "
            f"{feature_stats['superseded']} superseded, "
            f"{feature_stats['swept']} swept"
        )

        # Resolve gameplay feature claims into materialized M2M rows.
        resolve_all_gameplay_features([], model_ids=all_model_ids)
