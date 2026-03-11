"""Ingest pinball machines from an OPDB JSON dump.

Matches existing MachineModels by ipdb_id cross-reference, then by opdb_id,
then creates new records. Ingests both machines and OPDB aliases (stored as
variant_of FK). Optionally processes groups and changelog data.

Claims are collected during the main loops and written in bulk afterward.
"""

from __future__ import annotations

import json
import logging

from django.core.management.base import BaseCommand

from apps.catalog.ingestion.bulk_utils import format_names, generate_unique_slug
from apps.catalog.ingestion.parsers import (
    map_opdb_display,
    map_opdb_type,
    parse_opdb_date,
    parse_opdb_group_id,
)
from apps.catalog.claims import build_relationship_claim
from apps.catalog.models import MachineModel, Manufacturer, Title
from apps.provenance.models import Claim, Source

logger = logging.getLogger(__name__)

# Feature labels that indicate a "default" (canonical) variant, in priority order.
# Collector's Edition is always a variant, never promoted.
_DEFAULT_FEATURES = [
    "Premium edition",
    "Pro edition",
    "Limited edition",
    "Platinum edition",
]
_VARIANT_FEATURES = ["Collector's edition"]


def _pick_default_alias(aliases: list[dict]) -> dict:
    """Pick the alias that should be promoted to canonical model.

    Heuristic priority:
    1. Alias with Premium/Pro/Limited/Platinum edition feature (first match wins)
    2. First alias that is NOT a Collector's Edition
    3. First in the list (arbitrary — models.json corrects ambiguous cases)
    """
    for label in _DEFAULT_FEATURES:
        for rec in aliases:
            features = rec.get("features") or []
            if label in features:
                return rec
    # Avoid promoting Collector's Edition if there's any alternative.
    for rec in aliases:
        features = rec.get("features") or []
        if not any(f in features for f in _VARIANT_FEATURES):
            return rec
    return aliases[0]


class Command(BaseCommand):
    help = "Ingest pinball machines from an OPDB JSON dump."

    def add_arguments(self, parser):
        parser.add_argument(
            "--opdb",
            default="../data/dump1/opdb_export_machines.json",
            help="Path to OPDB JSON dump.",
        )
        parser.add_argument(
            "--groups",
            default="",
            help="Path to OPDB groups JSON dump.",
        )
        parser.add_argument(
            "--changelog",
            default="",
            help="Path to OPDB changelog JSON dump.",
        )
        parser.add_argument(
            "--models",
            default="",
            help="Path to models.json (supplements ipdb_id cross-references).",
        )

    def handle(self, *args, **options):
        opdb_path = options["opdb"]
        groups_path = options["groups"]
        changelog_path = options["changelog"]
        models_path = options["models"]

        from django.contrib.contenttypes.models import ContentType

        ct_id = ContentType.objects.get_for_model(MachineModel).pk

        source, _ = Source.objects.update_or_create(
            slug="opdb",
            defaults={
                "name": "OPDB",
                "source_type": "database",
                "priority": 200,
                "url": "https://opdb.org",
            },
        )

        # Build manufacturer name→slug lookup for ingest-time resolution.
        mfr_name_to_slug: dict[str, str] = {}
        existing_mfr_slugs: set[str] = set()
        for m in Manufacturer.objects.all():
            mfr_name_to_slug[m.name.lower()] = m.slug
            if m.trade_name:
                mfr_name_to_slug[m.trade_name.lower()] = m.slug
            existing_mfr_slugs.add(m.slug)

        # --- Changelog pre-processing ---
        if changelog_path:
            self._process_changelog(changelog_path)

        # --- Titles pre-loading ---
        groups_by_id: dict[str, dict] = {}
        if groups_path:
            groups_by_id = self._load_titles(groups_path, source)

        # --- Supplemental ipdb_id cross-references from models.json ---
        ipdb_id_supplement: dict[str, int] = {}
        if models_path:
            with open(models_path) as f:
                for entry in json.load(f):
                    opdb_id = entry.get("opdb_id")
                    ipdb_id = entry.get("ipdb_id")
                    if opdb_id and ipdb_id:
                        ipdb_id_supplement[opdb_id] = ipdb_id

        # --- Load machine data ---
        with open(opdb_path) as f:
            data = json.load(f)

        all_machines = [r for r in data if r.get("is_machine") is True]
        machines = [r for r in all_machines if r.get("physical_machine") != 0]
        non_physical_ids = {
            r["opdb_id"]
            for r in all_machines
            if r.get("physical_machine") == 0 and r.get("opdb_id")
        }
        aliases = [r for r in data if r.get("is_alias") is True]
        self.stdout.write(
            f"Processing {len(machines)} OPDB machines "
            f"({len(non_physical_ids)} non-physical skipped) "
            f"+ {len(aliases)} aliases..."
        )

        # --- Pre-fetch all MachineModels into lookup dicts ---
        by_ipdb_id: dict[int, MachineModel] = {
            pm.ipdb_id: pm for pm in MachineModel.objects.filter(ipdb_id__isnull=False)
        }
        by_opdb_id: dict[str, MachineModel] = {
            pm.opdb_id: pm for pm in MachineModel.objects.filter(opdb_id__isnull=False)
        }
        existing_slugs: set[str] = set(
            MachineModel.objects.values_list("slug", flat=True)
        )

        # --- Phase 1a: Match/create machines ---
        new_models: list[MachineModel] = []
        models_needing_opdb_update: list[MachineModel] = []
        machine_models: list[tuple[MachineModel, dict]] = []
        matched = 0
        created = 0
        skipped = 0

        for rec in machines:
            opdb_id = rec.get("opdb_id")
            if not opdb_id:
                skipped += 1
                continue

            ipdb_id = rec.get("ipdb_id") or ipdb_id_supplement.get(opdb_id)
            name = rec.get("name", "Unknown")

            pm = None
            if ipdb_id:
                pm = by_ipdb_id.get(ipdb_id)
            if not pm:
                pm = by_opdb_id.get(opdb_id)

            if pm:
                matched += 1
                # Set opdb_id if not already set (conflict check in memory).
                if pm.opdb_id is None and opdb_id:
                    if opdb_id not in by_opdb_id:
                        pm.opdb_id = opdb_id
                        by_opdb_id[opdb_id] = pm
                        models_needing_opdb_update.append(pm)
                    else:
                        logger.warning(
                            "Cannot set opdb_id=%s on %r (ipdb_id=%s): "
                            "already owned by %r",
                            opdb_id,
                            pm.name,
                            ipdb_id,
                            by_opdb_id[opdb_id].name,
                        )
                elif pm.opdb_id and pm.opdb_id != opdb_id:
                    logger.warning(
                        "MachineModel %r already has opdb_id=%s, skipping %s",
                        pm.name,
                        pm.opdb_id,
                        opdb_id,
                    )
            else:
                created += 1
                slug = generate_unique_slug(name, existing_slugs)
                pm = MachineModel(name=name, opdb_id=opdb_id, slug=slug)
                new_models.append(pm)
                by_opdb_id[opdb_id] = pm
                if ipdb_id:
                    by_ipdb_id[ipdb_id] = pm

            machine_models.append((pm, rec))

        if new_models:
            MachineModel.objects.bulk_create(new_models)
        if models_needing_opdb_update:
            MachineModel.objects.bulk_update(models_needing_opdb_update, ["opdb_id"])

        self.stdout.write(
            f"  Machines — Matched: {matched}, Created: {created}, Skipped: {skipped}"
        )
        if new_models:
            self.stdout.write(
                f"    New: {format_names([pm.name for pm in new_models])}"
            )

        # --- Phase 1b: Separate aliases into normal vs non-physical groups ---
        normal_aliases: list[dict] = []
        non_phys_groups: dict[str, list[dict]] = {}

        for rec in aliases:
            opdb_id = rec.get("opdb_id")
            if not opdb_id:
                continue
            parent_opdb_id = "-".join(opdb_id.split("-")[:2])
            if parent_opdb_id in non_physical_ids:
                non_phys_groups.setdefault(parent_opdb_id, []).append(rec)
            else:
                normal_aliases.append(rec)

        # --- Phase 1c: Promote default alias from each non-physical group ---
        promoted_new: list[MachineModel] = []
        promoted_update: list[MachineModel] = []
        promoted_count = 0

        for parent_id, group_aliases in non_phys_groups.items():
            default_rec = _pick_default_alias(group_aliases)
            rest = [r for r in group_aliases if r is not default_rec]

            opdb_id = default_rec.get("opdb_id")
            if not opdb_id:
                normal_aliases.extend(group_aliases)
                continue

            ipdb_id = default_rec.get("ipdb_id") or ipdb_id_supplement.get(opdb_id)
            name = default_rec.get("name", "Unknown")

            # Match-or-create like Phase 1a, but as a standalone machine.
            pm = None
            if ipdb_id:
                pm = by_ipdb_id.get(ipdb_id)
            if not pm:
                pm = by_opdb_id.get(opdb_id)

            if pm:
                if pm.opdb_id is None and opdb_id and opdb_id not in by_opdb_id:
                    pm.opdb_id = opdb_id
                    by_opdb_id[opdb_id] = pm
                    promoted_update.append(pm)
                # Clear variant_of if it was previously set (e.g. from a prior run).
                if pm.variant_of_id is not None:
                    pm.variant_of = None
                    if pm not in promoted_update:
                        promoted_update.append(pm)
            else:
                slug = generate_unique_slug(name, existing_slugs)
                pm = MachineModel(name=name, opdb_id=opdb_id, slug=slug)
                promoted_new.append(pm)
                by_opdb_id[opdb_id] = pm
                if ipdb_id:
                    by_ipdb_id[ipdb_id] = pm

            machine_models.append((pm, default_rec))
            # Register under the non-physical parent's opdb_id too,
            # so remaining aliases can find their parent.
            by_opdb_id[parent_id] = pm
            promoted_count += 1

            # Put remaining aliases back into normal processing.
            normal_aliases.extend(rest)

        if promoted_new:
            MachineModel.objects.bulk_create(promoted_new)
        if promoted_update:
            MachineModel.objects.bulk_update(
                promoted_update, ["opdb_id", "variant_of_id"]
            )

        if promoted_count:
            self.stdout.write(
                f"  Promoted {promoted_count} aliases from "
                f"{len(non_phys_groups)} non-physical groups"
            )

        # --- Phase 1d: Match/create normal aliases (stored as variants) ---
        new_variant_models: list[MachineModel] = []
        variant_models_needing_update: list[MachineModel] = []
        variant_models: list[tuple[MachineModel, dict]] = []
        alias_linked = 0
        alias_created = 0
        alias_skipped = 0

        for rec in normal_aliases:
            opdb_id = rec.get("opdb_id")
            if not opdb_id:
                alias_skipped += 1
                continue

            ipdb_id = rec.get("ipdb_id") or ipdb_id_supplement.get(opdb_id)
            name = rec.get("name", "Unknown")

            # Find the parent machine in memory.
            parent_opdb_id = "-".join(opdb_id.split("-")[:2])
            parent = by_opdb_id.get(parent_opdb_id)

            if not parent:
                logger.warning(
                    "Alias %s (%s): parent %s not found, skipping",
                    opdb_id,
                    name,
                    parent_opdb_id,
                )
                alias_skipped += 1
                continue

            pm = None
            if ipdb_id:
                pm = by_ipdb_id.get(ipdb_id)
            if not pm:
                pm = by_opdb_id.get(opdb_id)

            if pm:
                alias_linked += 1
                needs_update = False
                # Set opdb_id if not already set.
                if pm.opdb_id is None and opdb_id:
                    if opdb_id not in by_opdb_id:
                        pm.opdb_id = opdb_id
                        by_opdb_id[opdb_id] = pm
                        needs_update = True
                # Link to parent.
                if pm.variant_of_id != parent.pk:
                    pm.variant_of = parent
                    needs_update = True
                if needs_update:
                    variant_models_needing_update.append(pm)
            else:
                alias_created += 1
                slug = generate_unique_slug(name, existing_slugs)
                pm = MachineModel(
                    name=name, opdb_id=opdb_id, variant_of=parent, slug=slug
                )
                new_variant_models.append(pm)
                by_opdb_id[opdb_id] = pm
                if ipdb_id:
                    by_ipdb_id[ipdb_id] = pm

            variant_models.append((pm, rec))

        if new_variant_models:
            MachineModel.objects.bulk_create(new_variant_models)
        if variant_models_needing_update:
            MachineModel.objects.bulk_update(
                variant_models_needing_update, ["opdb_id", "variant_of_id"]
            )

        self.stdout.write(
            f"  Aliases — Linked: {alias_linked}, Created: {alias_created}, "
            f"Skipped: {alias_skipped}"
        )
        if new_variant_models:
            self.stdout.write(
                f"    New: {format_names([pm.name for pm in new_variant_models])}"
            )

        # --- Phase 2: Collect claims ---
        pending_claims: list[Claim] = []
        failed = 0
        failed_ids: list = []

        for pm, rec in machine_models:
            try:
                self._collect_claims(
                    pm,
                    rec,
                    ct_id,
                    groups_by_id,
                    pending_claims,
                    mfr_name_to_slug,
                    existing_mfr_slugs,
                )
            except Exception:
                opdb_id = rec.get("opdb_id", "?")
                logger.exception("Failed to collect claims for OPDB record %s", opdb_id)
                failed += 1
                failed_ids.append(opdb_id)

        for pm, rec in variant_models:
            try:
                self._collect_claims(
                    pm,
                    rec,
                    ct_id,
                    groups_by_id,
                    pending_claims,
                    mfr_name_to_slug,
                    existing_mfr_slugs,
                )
            except Exception:
                opdb_id = rec.get("opdb_id", "?")
                logger.exception("Failed to collect claims for OPDB alias %s", opdb_id)
                failed += 1
                failed_ids.append(opdb_id)

        if failed_ids:
            self.stderr.write(f"  Failed IDs: {failed_ids}")

        # --- Bulk-assert all collected claims ---
        claim_stats = Claim.objects.bulk_assert_claims(source, pending_claims)
        self.stdout.write(
            f"  Claims: {claim_stats['unchanged']} unchanged, "
            f"{claim_stats['created']} created, "
            f"{claim_stats['superseded']} superseded, "
            f"{claim_stats['duplicates_removed']} duplicates removed"
        )

        self.stdout.write(self.style.SUCCESS("OPDB ingestion complete."))

        if failed:
            raise SystemExit(1)

    # ------------------------------------------------------------------
    # Changelog
    # ------------------------------------------------------------------

    def _process_changelog(self, path: str) -> None:
        """Apply changelog: update stale opdb_ids for 'move' actions."""
        with open(path) as f:
            entries = json.load(f)

        moves = 0
        deletes = 0
        for entry in entries:
            action = entry.get("action")
            deleted_id = entry.get("opdb_id_deleted")
            replacement_id = entry.get("opdb_id_replacement")

            if action == "move" and deleted_id and replacement_id:
                updated = MachineModel.objects.filter(opdb_id=deleted_id)
                # Only update if the replacement isn't already taken.
                if not MachineModel.objects.filter(opdb_id=replacement_id).exists():
                    count = updated.update(opdb_id=replacement_id)
                    if count:
                        self.stdout.write(
                            f"  Changelog: moved {deleted_id} → {replacement_id}"
                        )
                        moves += 1
                elif updated.exists():
                    logger.warning(
                        "Changelog move %s → %s: replacement already exists",
                        deleted_id,
                        replacement_id,
                    )
            elif action == "delete" and deleted_id:
                if MachineModel.objects.filter(opdb_id=deleted_id).exists():
                    logger.info(
                        "Changelog delete %s: model exists but not deleting",
                        deleted_id,
                    )
                deletes += 1

        self.stdout.write(
            f"  Changelog: {moves} moves applied, {deletes} deletes logged"
        )

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    def _load_titles(self, path: str, source: Source) -> dict[str, dict]:
        """Load groups JSON, create Title records, and assert name/short_name claims.

        Returns a dict mapping group opdb_id → group record for later lookup.
        """
        from django.contrib.contenttypes.models import ContentType

        from apps.catalog.resolve import TITLE_DIRECT_FIELDS, _resolve_bulk

        with open(path) as f:
            data = json.load(f)

        ct_id = ContentType.objects.get_for_model(Title).pk

        # Build lookup of raw group data.
        groups_by_id: dict[str, dict] = {}
        for rec in data:
            opdb_id = rec.get("opdb_id")
            if opdb_id:
                groups_by_id[opdb_id] = rec

        # Pre-fetch existing titles.
        existing_titles: dict[str, Title] = {t.opdb_id: t for t in Title.objects.all()}
        existing_slugs: set[str] = set(Title.objects.values_list("slug", flat=True))

        new_titles: list[Title] = []
        unchanged = 0

        for opdb_id, rec in groups_by_id.items():
            name = rec.get("name", "")

            existing = existing_titles.get(opdb_id)
            if existing:
                unchanged += 1
            else:
                slug = generate_unique_slug(name, existing_slugs)
                new_titles.append(
                    Title(
                        opdb_id=opdb_id,
                        name=name,
                        slug=slug,
                    )
                )

        titles_created = len(new_titles)
        if new_titles:
            Title.objects.bulk_create(new_titles)

        # Re-fetch all titles so we have PKs for claim assertions.
        all_titles: dict[str, Title] = {t.opdb_id: t for t in Title.objects.all()}

        # Collect name and abbreviation claims for all titles from this source.
        pending_claims: list[Claim] = []
        touched_ids: set[int] = set()

        for opdb_id, rec in groups_by_id.items():
            title = all_titles.get(opdb_id)
            if not title:
                continue

            name = rec.get("name", "")
            short_name = rec.get("shortname") or ""
            touched_ids.add(title.pk)

            if name:
                pending_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=title.pk,
                        field_name="name",
                        value=name,
                    )
                )
            if short_name:
                claim_key, value = build_relationship_claim(
                    "abbreviation", {"value": short_name}
                )
                pending_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=title.pk,
                        field_name="abbreviation",
                        claim_key=claim_key,
                        value=value,
                    )
                )

        claim_stats = Claim.objects.bulk_assert_claims(source, pending_claims)

        # Resolve touched titles so fields reflect winning claims.
        from apps.catalog.models import Franchise

        from apps.catalog.resolve import resolve_all_title_abbreviations

        franchise_lookup = {f.slug: f for f in Franchise.objects.all()}
        _resolve_bulk(
            Title,
            TITLE_DIRECT_FIELDS,
            fk_handlers={"franchise": ("franchise", franchise_lookup)},
            object_ids=touched_ids,
        )
        resolve_all_title_abbreviations(
            list(Title.objects.all()), title_ids=touched_ids
        )

        self.stdout.write(f"  Titles: {titles_created} created, {unchanged} unchanged")
        self.stdout.write(
            f"  Title claims: {claim_stats['created']} created, "
            f"{claim_stats['unchanged']} unchanged"
        )
        return groups_by_id

    # ------------------------------------------------------------------
    # Shared claim collection
    # ------------------------------------------------------------------

    def _collect_claims(
        self,
        pm: MachineModel,
        rec: dict,
        ct_id: int,
        groups_by_id: dict[str, dict],
        pending_claims: list[Claim],
        mfr_name_to_slug: dict[str, str],
        existing_mfr_slugs: set[str],
    ) -> None:
        """Collect claim objects for a machine or alias record."""
        opdb_id = rec.get("opdb_id")
        name = rec.get("name")

        def _add(field_name: str, value) -> None:
            pending_claims.append(
                Claim(
                    content_type_id=ct_id,
                    object_id=pm.pk,
                    field_name=field_name,
                    value=value,
                )
            )

        if name:
            _add("name", name)
        if opdb_id:
            _add("opdb_id", opdb_id)

        # Manufacturer: resolve OPDB name to slug at ingest time.
        mfr = rec.get("manufacturer")
        if mfr:
            opdb_mfr_name = mfr.get("name", "")
            if opdb_mfr_name:
                slug = mfr_name_to_slug.get(opdb_mfr_name.lower())
                if not slug:
                    # Auto-create manufacturer from OPDB name.
                    slug = generate_unique_slug(opdb_mfr_name, existing_mfr_slugs)
                    Manufacturer.objects.create(
                        name=opdb_mfr_name,
                        slug=slug,
                        trade_name=opdb_mfr_name,
                    )
                    mfr_name_to_slug[opdb_mfr_name.lower()] = slug
                _add("manufacturer", slug)

        # Date.
        date_str = rec.get("manufacture_date")
        if date_str:
            year, month = parse_opdb_date(date_str)
            if year is not None:
                _add("year", year)
            if month is not None:
                _add("month", month)

        # Player count.
        player_count = rec.get("player_count")
        if player_count is not None:
            _add("player_count", player_count)

        # Technology generation (slug-based, resolved to FK).
        technology_generation = map_opdb_type(rec.get("type"))
        if technology_generation:
            _add("technology_generation", technology_generation)

        # Display type (slug-based, resolved to FK).
        display_type = map_opdb_display(rec.get("display"))
        if display_type:
            _add("display_type", display_type)

        # Extra data fields.
        # OPDB 'features' are variant labels (LE, SE, shaker motor etc.) — stored
        # as 'variant_features' to avoid future confusion with gameplay features.
        opdb_features = rec.get("features")
        if opdb_features:
            _add("variant_features", opdb_features)

        for field in ("keywords", "description", "common_name", "images"):
            value = rec.get(field)
            if value:
                _add(field, value)

        # Shortname becomes a relationship claim for abbreviations.
        shortname = rec.get("shortname")
        if shortname:
            claim_key, abbr_value = build_relationship_claim(
                "abbreviation", {"value": shortname}
            )
            pending_claims.append(
                Claim(
                    content_type_id=ct_id,
                    object_id=pm.pk,
                    field_name="abbreviation",
                    claim_key=claim_key,
                    value=abbr_value,
                )
            )

        # Title claim (derived from opdb_id prefix).
        if opdb_id and groups_by_id:
            group_opdb_id = parse_opdb_group_id(opdb_id)
            if group_opdb_id and group_opdb_id in groups_by_id:
                _add("title", group_opdb_id)
