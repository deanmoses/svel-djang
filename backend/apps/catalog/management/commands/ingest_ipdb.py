"""Ingest pinball machines from an IPDB JSON dump.

Creates MachineModel records, asserts Claims for each field, and creates
Person/Credit records for design credits.

Claims, Persons, and Credits are collected during the main loop and
written in bulk after all records are processed.
"""

from __future__ import annotations

import json
from apps.catalog.ingestion.constants import DEFAULT_IPDB_PATH
import logging
import re
from html import unescape
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
    LocationValidationError,
    get_ipdb_location,
    parse_credit_string,
    parse_ipdb_date,
    parse_ipdb_machine_type,
    parse_ipdb_manufacturer_string,
)
from apps.catalog.claims import build_relationship_claim, make_authoritative_scope
from apps.catalog.ingestion.vocabulary import (
    build_feature_slug_map,
    build_reward_type_map,
)
from apps.catalog.models import (
    Address,
    CorporateEntity,
    CorporateEntityAlias,
    GameplayFeature,
    MachineModel,
    Person,
    RewardType,
    Theme,
)
from apps.catalog.resolve import (
    resolve_all_credits,
    resolve_all_gameplay_features,
    resolve_all_reward_types,
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


# Regex patterns for features that appear in narrative text rather than
# the structured "Feature (N)" list.  Each pattern is matched against
# the full notable_features string.  Target slugs are validated at startup
# against the DB-driven feature/reward-type maps.
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
    (re.compile(r"\b[Hh]ead.?to.?[Hh]ead\b"), "head-to-head"),
]

# Regex for inserting a comma before a period followed by an uppercase letter.
# Handles IPDB encoding artifacts like "5 cents.Flippers" → "5 cents,Flippers".
_PERIOD_UPPERCASE_RE = re.compile(r"\.(?=[A-Z])")

# Regex for extracting "feature name (count)" from a segment.
# Requires a bare integer in parens — \(\d+\) — matching only "Flippers (2)",
# not narrative like "(42 inches long...)" or "(5-ball mode)".
# Group 1 = feature name, group 2 = count.
# No $ anchor so trailing description text is ignored.
_COUNT_SEGMENT_RE = re.compile(r"^(.+?)\s*\((\d+)\)")

# ---------------------------------------------------------------------------
# Multiball special handling
#
# For every other IPDB feature the parenthesized number is a *quantity*
# ("Flippers (2)" = two flippers).  For multiball the number is a
# *qualifier* that identifies WHICH feature: "Multiball (3)" means
# 3-ball-multiball, NOT "three instances of multiball."
#
# When future quantity capture is added, multiball must NOT store the
# parenthesized number as a quantity — it is consumed into the slug here.
# ---------------------------------------------------------------------------
_MULTIBALL_SLUG = "multiball"

# Matches "Multiball (...)" with any paren content (not just bare integers).
# Used as a fallback when _COUNT_SEGMENT_RE doesn't match.
_MULTIBALL_PAREN_RE = re.compile(r"^[Mm]ulti-?ball\s*\((.+)\)")

# Inside multiball parens, extracts digits that are ball counts.
# Negative lookahead excludes digits followed by "mode" (e.g. "3 modes").
_MULTIBALL_BALL_COUNT_RE = re.compile(r"(\d+)(?![\s-]*[Mm]ode)")

# Narrative: "3-ball multiball", "2-ball and 3-ball Multiball", etc.
# Captures the compound prefix so all N values can be extracted.
_NBALL_MULTIBALL_RE = re.compile(
    r"\b((?:\d+-ball\s+(?:and|or)\s+)*\d+-ball)\s+[Mm]ulti-?ball\b"
)

# Spelled-out numbers for "Three ball multiball" etc.
_WORD_TO_DIGIT: dict[str, str] = {
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
}
_WORD_NBALL_MULTIBALL_RE = re.compile(
    r"\b(two|three|four|five|six)[\s-]*ball\s+[Mm]ulti-?ball\b", re.IGNORECASE
)


def _resolve_multiball_slugs(paren_content: str, valid_slugs: set[str]) -> list[str]:
    """Extract n-ball-multiball slugs from multiball paren content.

    Handles: "3", "2-ball", "3 ball", "3 balls", "2 or 3",
    "2 ball, 3 ball", "2-Ball, 3-Ball, 4-Ball", "4 ball, 3 modes".
    Skips digits followed by "mode/modes" (not ball counts).
    Falls back to generic "multiball" if no valid n-ball slugs found.
    """
    results: list[str] = []
    for m in _MULTIBALL_BALL_COUNT_RE.finditer(paren_content):
        specific = f"{m.group(1)}-ball-multiball"
        if specific in valid_slugs:
            results.append(specific)
    return results if results else [_MULTIBALL_SLUG]


def _extract_ipdb_gameplay_features(
    raw: str, feature_map: dict[str, str]
) -> tuple[list[tuple[str, int | None]], list[str]]:
    """Extract gameplay feature slugs and counts from an IPDB notable_features string.

    Uses a structured 4-step pipeline:
    1. Clean: strip prefix, normalize mojibake, insert comma before period+uppercase.
    2. Split: on comma or period+whitespace; strip preamble before colon.
    3. Parse: process segments with "Feature (N)" count syntax, plus
       "Multiball (...)" segments with complex paren content.
    4. Classify: look up extracted feature name in feature_map.
       Also apply _NARRATIVE_FEATURE_PATTERNS and n-ball-multiball
       narrative patterns to the full cleaned text.

    Returns ``([(slug, count | None), ...], unmatched_terms)``.

    For multiball the parenthesized number is consumed into the slug
    (e.g. "Multiball (3)" → "3-ball-multiball") and is NOT stored as a
    count.  Narrative-pattern matches have ``count=None``.
    """
    seen: set[str] = set()
    pairs: list[tuple[str, int | None]] = []
    unmatched: list[str] = []
    valid_slugs = set(feature_map.values())

    def _add(slug: str, count: int | None = None) -> None:
        if slug not in seen:
            seen.add(slug)
            pairs.append((slug, count))

    # Step 1: Clean.
    cleaned = raw
    if cleaned.lower().startswith("notable features:"):
        cleaned = cleaned[len("notable features:") :]
    cleaned = cleaned.replace("\ufffd", " ")
    cleaned = _PERIOD_UPPERCASE_RE.sub(",", cleaned)

    # Step 2: Split on comma or period+whitespace.
    # The comma split uses a negative lookahead to avoid splitting inside
    # parentheses, e.g. "Multiball (2-Ball, 3-Ball, 4-Ball)" stays intact.
    segments: list[str] = []
    for part in re.split(r",(?![^()]*\))|\.(?:\s+)", cleaned):
        segment = part.strip()
        if not segment:
            continue
        # Strip preamble text before a colon within each segment.
        if ":" in segment:
            segment = segment.split(":", 1)[1].strip()
        if segment:
            segments.append(segment)

    # Step 3 + 4: Parse then classify.
    for segment in segments:
        # Branch 1: standard "Feature (N)" count syntax.
        m = _COUNT_SEGMENT_RE.match(segment)
        if m:
            term = m.group(1).strip().lower()
            qty = int(m.group(2))
            if not term:
                continue
            slug = feature_map.get(term)
            if slug:
                # Multiball special case: the parenthesized number is NOT a
                # quantity — it identifies WHICH multiball variant.
                # "Multiball (3)" → 3-ball-multiball, not multiball qty=3.
                if slug == _MULTIBALL_SLUG:
                    for s in _resolve_multiball_slugs(str(qty), valid_slugs):
                        _add(s)
                else:
                    _add(slug, qty)
            else:
                unmatched.append(term)
            continue

        # Branch 2: "Multiball (...)" with complex paren content that doesn't
        # match bare-integer syntax, e.g. "Multiball (2-ball)",
        # "Multiball (4 ball, 3 modes)".
        mb_m = _MULTIBALL_PAREN_RE.match(segment)
        if mb_m:
            for s in _resolve_multiball_slugs(mb_m.group(1), valid_slugs):
                _add(s)

    # Narrative patterns applied to cleaned text.
    for pattern, slug in _NARRATIVE_FEATURE_PATTERNS:
        if pattern.search(cleaned):
            _add(slug)

    # N-ball multiball narrative: "3-ball Multiball", "2-ball and 3-ball Multiball"
    for nball_m in _NBALL_MULTIBALL_RE.finditer(cleaned):
        # Extract all digit values from the compound prefix
        # e.g. "2-ball and 3-ball" → ["2", "3"]
        for digit in re.findall(r"(\d+)-ball", nball_m.group(1)):
            specific = f"{digit}-ball-multiball"
            if specific in valid_slugs:
                _add(specific)

    # Spelled-out: "Three ball multiball"
    wm = _WORD_NBALL_MULTIBALL_RE.search(cleaned)
    if wm:
        digit = _WORD_TO_DIGIT.get(wm.group(1).lower())
        if digit:
            specific = f"{digit}-ball-multiball"
            if specific in valid_slugs:
                _add(specific)

    # If a specific n-ball-multiball variant was found, suppress the generic
    # "multiball" slug — the hierarchy already links variants to the parent.
    if any(s.endswith("-ball-multiball") for s in seen) and _MULTIBALL_SLUG in seen:
        pairs = [(s, c) for s, c in pairs if s != _MULTIBALL_SLUG]
        seen.discard(_MULTIBALL_SLUG)

    return pairs, unmatched


def _extract_ipdb_reward_types(raw: str, reward_map: dict[str, str]) -> list[str]:
    """Extract reward type slugs from an IPDB notable_features string.

    Uses word-boundary keyword matching against the raw text — reward types
    appear as keywords in IPDB narrative text with or without counts.

    Returns deduplicated slugs in discovery order.
    """
    seen: set[str] = set()
    slugs: list[str] = []
    for term, slug in reward_map.items():
        if re.search(r"\b" + re.escape(term) + r"\b", raw, re.IGNORECASE):
            if slug not in seen:
                seen.add(slug)
                slugs.append(slug)
    return slugs


def _load_mpu_to_system_slug() -> dict[str, str]:
    """Build {mpu_string: system_slug} from SystemMpuString records."""
    from apps.catalog.models import SystemMpuString

    return {
        ms.value: ms.system.slug
        for ms in SystemMpuString.objects.select_related("system").all()
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
            default=DEFAULT_IPDB_PATH,
            help="Path to IPDB JSON dump.",
        )

    def handle(self, *args, **options):
        ipdb_path = options["ipdb"]
        mpu_to_slug = _load_mpu_to_system_slug()

        # Build DB-driven vocabulary maps.
        feature_map = build_feature_slug_map()
        reward_map = build_reward_type_map()

        # Validate all hardcoded narrative pattern slugs exist in the DB.
        all_vocab_slugs = set(feature_map.values()) | set(reward_map.values())
        bad_narrative_slugs = [
            slug
            for _, slug in _NARRATIVE_FEATURE_PATTERNS
            if slug not in all_vocab_slugs
        ]
        if bad_narrative_slugs:
            raise CommandError(
                f"Narrative feature pattern slug(s) not found in pinbase vocabulary: "
                f"{', '.join(bad_narrative_slugs)}\n"
                "Update _NARRATIVE_FEATURE_PATTERNS to use valid slugs."
            )

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
        for alias in CorporateEntityAlias.objects.select_related(
            "corporate_entity__manufacturer"
        ).all():
            key = alias.value.lower()
            if key not in ce_by_name:
                ce_by_name[key] = alias.corporate_entity
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
        gameplay_feature_queue: list[tuple[int, list[tuple[str, int | None]]]] = []
        reward_type_queue: list[tuple[int, list[str]]] = []
        unmatched_feature_terms: list[str] = []
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
                reward_type_queue,
                feature_map,
                reward_map,
                unmatched_feature_terms,
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

        # --- Assert reward type claims ---
        self._bulk_create_reward_types(reward_type_queue, source, all_model_ids)

        # --- Warn about unmatched feature terms ---
        if unmatched_feature_terms:
            sample = unmatched_feature_terms[:25]
            suffix = (
                f", ... ({len(unmatched_feature_terms)} total not in pinbase)"
                if len(unmatched_feature_terms) > 25
                else ""
            )
            self.stdout.write(
                self.style.WARNING(
                    f"  Unmatched IPDB feature terms: {', '.join(sample)}{suffix}"
                )
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
        gameplay_feature_queue: list[tuple[int, list[tuple[str, int | None]]]],
        reward_type_queue: list[tuple[int, list[str]]],
        feature_map: dict[str, str],
        reward_map: dict[str, str],
        unmatched_feature_terms: list[str],
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
                    or resolver.resolve_by_corporate_entity(company)
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
                try:
                    addr = get_ipdb_location(mfr_id, location)
                except LocationValidationError as exc:
                    raise CommandError(str(exc)) from exc
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

        # Collect gameplay feature and reward type slugs for bulk creation later.
        if rec.notable_features:
            raw_features = unescape(rec.notable_features)
            feature_pairs, unmatched = _extract_ipdb_gameplay_features(
                raw_features, feature_map
            )
            unmatched_feature_terms.extend(unmatched)
            if feature_pairs:
                gameplay_feature_queue.append((pm.pk, feature_pairs))
            reward_slugs = _extract_ipdb_reward_types(raw_features, reward_map)
            if reward_slugs:
                reward_type_queue.append((pm.pk, reward_slugs))

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
        gameplay_feature_queue: list[tuple[int, list[tuple[str, int | None]]]],
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
        for _, pairs in gameplay_feature_queue:
            all_slugs.update(slug for slug, _count in pairs)

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
        for pm_pk, pairs in gameplay_feature_queue:
            for slug, count in pairs:
                if slug not in existing_slugs:
                    continue
                claim_key, value = build_relationship_claim(
                    "gameplay_feature", {"gameplay_feature_slug": slug}
                )
                if count is not None:
                    value["count"] = count
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

    def _bulk_create_reward_types(
        self,
        reward_type_queue: list[tuple[int, list[str]]],
        source,
        all_model_ids: set[int],
    ) -> None:
        """Assert reward type relationship claims and resolve into M2M rows.

        All RewardType records already exist from the taxonomy seed, so
        no get-or-create step is needed — only claim assertion and resolution.
        """
        if not reward_type_queue:
            return

        from django.contrib.contenttypes.models import ContentType

        # Verify all referenced slugs exist.
        all_slugs: set[str] = set()
        for _, slugs in reward_type_queue:
            all_slugs.update(slugs)

        existing_slugs = set(
            RewardType.objects.filter(slug__in=all_slugs).values_list("slug", flat=True)
        )
        missing = all_slugs - existing_slugs
        if missing:
            logger.warning(
                "Reward type slugs not found in DB (skipping): %s",
                sorted(missing),
            )

        # Build reward type relationship claims.
        ct_machine = ContentType.objects.get_for_model(MachineModel).pk
        reward_type_claims: list[Claim] = []
        for pm_pk, slugs in reward_type_queue:
            for slug in slugs:
                if slug not in existing_slugs:
                    continue
                claim_key, value = build_relationship_claim(
                    "reward_type", {"reward_type_slug": slug}
                )
                reward_type_claims.append(
                    Claim(
                        content_type_id=ct_machine,
                        object_id=pm_pk,
                        field_name="reward_type",
                        claim_key=claim_key,
                        value=value,
                    )
                )

        auth_scope = make_authoritative_scope(MachineModel, all_model_ids)
        reward_type_stats = Claim.objects.bulk_assert_claims(
            source,
            reward_type_claims,
            sweep_field="reward_type",
            authoritative_scope=auth_scope,
        )
        self.stdout.write(
            f"  Reward type claims: {reward_type_stats['unchanged']} unchanged, "
            f"{reward_type_stats['created']} created, "
            f"{reward_type_stats['superseded']} superseded, "
            f"{reward_type_stats['swept']} swept"
        )

        # Resolve reward type claims into materialized M2M rows.
        resolve_all_reward_types([], model_ids=all_model_ids)
