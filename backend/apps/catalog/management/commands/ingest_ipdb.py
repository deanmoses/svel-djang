"""Ingest pinball machines from an IPDB JSON dump.

Creates MachineModel records, asserts Claims for each field, and creates
Person/DesignCredit records for design credits.

Claims, Persons, and DesignCredits are collected during the main loop and
written in bulk after all records are processed.
"""

from __future__ import annotations

import json
import logging
from html import unescape
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.ingestion.bulk_utils import format_names, generate_unique_slug
from apps.catalog.ingestion.constants import IPDB_SKIP_MANUFACTURER_IDS
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
    MachineModel,
    Manufacturer,
    Person,
    Theme,
)
from apps.catalog.resolve import resolve_credits, resolve_themes
from apps.provenance.models import Claim, Source

logger = logging.getLogger(__name__)

# IPDB field → Claim field_name for direct/extra_data claims.
CLAIM_FIELDS = {
    "Title": "name",
    "IpdbId": "ipdb_id",
    "Players": "player_count",
    "ProductionNumber": "production_quantity",
    "AverageFunRating": "ipdb_rating",
    # Extra data (no dedicated column)
    "NotableFeatures": "notable_features",
    "Notes": "notes",
    "Toys": "toys",
    "MarketingSlogans": "marketing_slogans",
    "CommonAbbreviations": "abbreviation",
    "ModelNumber": "model_number",
}

# IPDB credit field → DesignCredit role.
CREDIT_FIELDS = {
    "DesignBy": "design",
    "ArtBy": "art",
    "DotsAnimationBy": "animation",
    "MechanicsBy": "mechanics",
    "MusicBy": "music",
    "SoundBy": "sound",
    "SoftwareBy": "software",
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


_SYSTEMS_JSON = Path(__file__).parents[5] / "data" / "systems.json"


def _load_mpu_to_system_slug() -> dict[str, str]:
    """Build {mpu_string: system_slug} from data/systems.json."""
    with open(_SYSTEMS_JSON) as f:
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


class Command(BaseCommand):
    help = "Ingest pinball machines from an IPDB JSON dump."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ipdb",
            default="../data/dump1/ipdbdatabase.json",
            help="Path to IPDB JSON dump.",
        )

    def handle(self, *args, **options):
        ipdb_path = options["ipdb"]
        mpu_to_slug = _load_mpu_to_system_slug()

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

        # Build manufacturer resolution lookups.
        entity_name_to_slug: dict[str, str] = {
            ce.name.lower(): ce.manufacturer.slug
            for ce in CorporateEntity.objects.select_related("manufacturer").all()
        }
        mfr_name_to_slug: dict[str, str] = {}
        existing_mfr_slugs: set[str] = set()
        for m in Manufacturer.objects.all():
            mfr_name_to_slug[m.name.lower()] = m.slug
            if m.trade_name:
                mfr_name_to_slug[m.trade_name.lower()] = m.slug
            existing_mfr_slugs.add(m.slug)
        # Cache CE→CorporateEntity for address creation.
        ce_by_name: dict[str, CorporateEntity] = {
            ce.name.lower(): ce for ce in CorporateEntity.objects.all()
        }

        with open(ipdb_path) as f:
            data = json.load(f)

        records = data["Data"]
        self.stdout.write(f"Processing {len(records)} IPDB records...")

        # --- Phase 1: Ensure all MachineModels exist ---
        existing_by_ipdb: dict[int, MachineModel] = {
            pm.ipdb_id: pm for pm in MachineModel.objects.filter(ipdb_id__isnull=False)
        }
        existing_slugs: set[str] = set(
            MachineModel.objects.values_list("slug", flat=True)
        )

        new_models: list[MachineModel] = []
        record_models: list[tuple[MachineModel, dict, bool]] = []
        skipped = 0

        for rec in records:
            ipdb_id = rec.get("IpdbId")
            if not ipdb_id:
                skipped += 1
                continue

            title = unescape(TITLE_FIXES.get(ipdb_id, rec.get("Title", "Unknown")))

            pm = existing_by_ipdb.get(ipdb_id)
            if pm:
                record_models.append((pm, rec, False))
            else:
                slug = generate_unique_slug(title, existing_slugs)
                pm = MachineModel(ipdb_id=ipdb_id, name=title, slug=slug)
                new_models.append(pm)
                existing_by_ipdb[ipdb_id] = pm
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

        # --- Phase 2: Collect claims, credits, and theme slugs ---
        pending_claims: list[Claim] = []
        credit_queue: list[tuple[int, str, str]] = []
        theme_queue: list[tuple[int, list[str]]] = []  # (model_pk, [slugs])
        unknown_mpu_strings: set[str] = set()
        failed = 0
        failed_ids: list = []

        for pm, rec, _was_created in record_models:
            try:
                self._collect_record_data(
                    pm,
                    rec,
                    ct_id,
                    pending_claims,
                    credit_queue,
                    theme_queue,
                    mpu_to_slug,
                    unknown_mpu_strings,
                    entity_name_to_slug,
                    mfr_name_to_slug,
                    existing_mfr_slugs,
                    ce_by_name,
                )
            except Exception:
                ipdb_id = rec.get("IpdbId", "?")
                logger.exception("Failed to collect data for IPDB record %s", ipdb_id)
                failed += 1
                failed_ids.append(ipdb_id)

        if failed_ids:
            self.stderr.write(f"  Failed IDs: {failed_ids}")

        if unknown_mpu_strings:
            lines = "\n".join(f"  {s}" for s in sorted(unknown_mpu_strings))
            raise CommandError(
                f"Unknown MPU strings not in data/systems.json:\n{lines}\n"
                "Add entries to data/systems.json and run ingest_pinbase_systems before re-ingesting."
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

        self.stdout.write(self.style.SUCCESS("IPDB ingestion complete."))

        if failed:
            raise SystemExit(1)

    def _collect_record_data(
        self,
        pm: MachineModel,
        rec: dict,
        ct_id: int,
        pending_claims: list[Claim],
        credit_queue: list[tuple[int, str, str]],
        theme_queue: list[tuple[int, list[str]]],
        mpu_to_slug: dict[str, str],
        unknown_mpu_strings: set[str],
        entity_name_to_slug: dict[str, str],
        mfr_name_to_slug: dict[str, str],
        existing_mfr_slugs: set[str],
        ce_by_name: dict[str, CorporateEntity],
    ) -> None:
        """Collect claims, credits, and theme slugs for a single IPDB record."""
        ipdb_id = rec.get("IpdbId")

        # Collect claims for mapped fields.
        for ipdb_field, claim_field in CLAIM_FIELDS.items():
            value = rec.get(ipdb_field)
            if value is None or value == "":
                continue
            # Use corrected title for name claims.
            if ipdb_field == "Title" and ipdb_id in TITLE_FIXES:
                value = TITLE_FIXES[ipdb_id]
            # Convert production number to string.
            if ipdb_field == "ProductionNumber":
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

        # Manufacturer: resolve at ingest time to a slug claim.
        mfr_id = rec.get("ManufacturerId")
        raw_mfr = rec.get("Manufacturer", "")
        if mfr_id and mfr_id not in IPDB_SKIP_MANUFACTURER_IDS and raw_mfr:
            parsed = parse_ipdb_manufacturer_string(raw_mfr)
            company = parsed["company_name"]
            trade = parsed["trade_name"]
            location = parsed["location"]

            # 3-priority resolution cascade (matches DuckDB view).
            slug = (
                entity_name_to_slug.get(company.lower())
                or (trade and mfr_name_to_slug.get(trade.lower()))
                or mfr_name_to_slug.get(company.lower())
            )

            if not slug:
                # Auto-create manufacturer from parsed name.
                display_name = trade or company
                slug = generate_unique_slug(display_name, existing_mfr_slugs)
                Manufacturer.objects.create(
                    name=display_name,
                    slug=slug,
                    trade_name=trade,
                )
                mfr_name_to_slug[display_name.lower()] = slug
                if trade:
                    mfr_name_to_slug[trade.lower()] = slug

            pending_claims.append(
                Claim(
                    content_type_id=ct_id,
                    object_id=pm.pk,
                    field_name="manufacturer",
                    value=slug,
                )
            )

            # Create address on matched CE when location is available.
            if location:
                ce = ce_by_name.get(company.lower())
                if ce:
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
        mpu_value = rec.get("MPU", "")
        if isinstance(mpu_value, str):
            mpu_value = mpu_value.strip().replace("\ufffd", "")
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
        date_str = rec.get("DateOfManufacture")
        if date_str:
            year, month = parse_ipdb_date(date_str)
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
        type_short = rec.get("TypeShortName")
        type_full = rec.get("Type")
        technology_generation = parse_ipdb_machine_type(type_short, type_full)
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
        image_files = rec.get("ImageFiles")
        if image_files:
            urls = [img["Url"] for img in image_files if img.get("Url")]
            if urls:
                pending_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=pm.pk,
                        field_name="image_urls",
                        value=urls,
                    )
                )

        # Collect theme slugs for bulk creation later.
        raw_theme = rec.get("Theme")
        if raw_theme:
            theme_slugs = _parse_ipdb_themes(unescape(raw_theme))
            if theme_slugs:
                theme_queue.append((pm.pk, theme_slugs))

        # Collect design credits for bulk creation later.
        for ipdb_field, role in CREDIT_FIELDS.items():
            raw = rec.get(ipdb_field)
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

        Person records and name claims are created as before.  DesignCredit
        rows are no longer created directly — instead, credit relationship
        claims are asserted and materialized by the resolution layer.
        """
        if not credit_queue:
            return

        from django.contrib.contenttypes.models import ContentType

        # Discover all unique person names needed.
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
            # Refresh to get PKs.
            existing_persons = {p.name.lower(): p for p in Person.objects.all()}

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

        # Resolve credit claims into materialized DesignCredit rows.
        for machine in MachineModel.objects.filter(pk__in=all_model_ids):
            resolve_credits(machine)

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
        for machine in MachineModel.objects.filter(pk__in=all_model_ids):
            resolve_themes(machine)
