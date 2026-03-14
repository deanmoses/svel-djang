"""Ingest pinball machines from an OPDB JSON dump.

Matches existing MachineModels by ipdb_id cross-reference, then by opdb_id,
then creates new records. Ingests both machines and OPDB aliases (stored as
variant_of FK). Optionally processes groups and changelog data.

Claims are collected during the main loops and written in bulk afterward.
"""

from __future__ import annotations

import json
import logging

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.ingestion.bulk_utils import (
    ManufacturerResolver,
    format_names,
    generate_unique_slug,
)
from apps.catalog.ingestion.opdb.records import OpdbRecord
from apps.catalog.ingestion.opdb.relationships import (
    classify_alias_relationship,
    pick_default_alias,
)
from apps.catalog.ingestion.parsers import (
    map_opdb_display,
    map_opdb_type,
    parse_opdb_date,
)
from apps.catalog.claims import build_relationship_claim
from apps.catalog.models import MachineModel, Title
from apps.provenance.models import Claim, Source

logger = logging.getLogger(__name__)


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
        parser.add_argument(
            "--titles",
            default="",
            help="Path to titles.json (split_from_opdb_group entries skip group creation).",
        )

    def handle(self, *args, **options):
        opdb_path = options["opdb"]
        groups_path = options["groups"]
        changelog_path = options["changelog"]
        models_path = options["models"]
        titles_path = options["titles"]

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

        # Manufacturer resolver (shared lookup + auto-create-on-miss).
        resolver = ManufacturerResolver()

        # --- Changelog pre-processing ---
        if changelog_path:
            self._process_changelog(changelog_path)

        # --- Build skip set from titles.json split_from_opdb_group entries ---
        split_group_ids: set[str] = set()
        if titles_path:
            with open(titles_path) as f:
                for entry in json.load(f):
                    gid = entry.get("split_from_opdb_group")
                    if gid:
                        split_group_ids.add(gid)

        # --- Titles pre-loading ---
        title_slug_by_group: dict[str, str] = {}
        if groups_path:
            title_slug_by_group = self._load_titles(
                groups_path, source, split_group_ids
            )

        # --- Supplemental cross-references from models.json ---
        ipdb_id_supplement: dict[str, int] = {}
        pinbase_variant_of: dict[str, str] = {}  # opdb_id → variant_of slug
        pinbase_is_conversion: set[str] = set()  # opdb_ids marked is_conversion
        if models_path:
            with open(models_path) as f:
                for entry in json.load(f):
                    opdb_id = entry.get("opdb_id")
                    ipdb_id = entry.get("ipdb_id")
                    if opdb_id and ipdb_id:
                        ipdb_id_supplement[opdb_id] = ipdb_id
                    if opdb_id and entry.get("variant_of"):
                        pinbase_variant_of[opdb_id] = entry["variant_of"]
                    if opdb_id and entry.get("is_conversion"):
                        pinbase_is_conversion.add(opdb_id)

        # --- Load and parse machine data into typed records ---
        with open(opdb_path) as f:
            raw_data = json.load(f)

        records: list[OpdbRecord] = []
        parse_errors = 0
        for raw in raw_data:
            if "opdb_id" not in raw:
                parse_errors += 1
                logger.warning(
                    "OPDB record missing opdb_id (name=%r)",
                    raw.get("name", "<unknown>"),
                )
                continue
            try:
                records.append(OpdbRecord.from_raw(raw))
            except (KeyError, ValueError, TypeError) as e:
                parse_errors += 1
                logger.warning(
                    "Unparseable OPDB record (id=%s): %s",
                    raw.get("opdb_id", "?"),
                    e,
                )
        if parse_errors:
            raise CommandError(
                f"{parse_errors} OPDB record(s) failed to parse — aborting to prevent partial import. "
                f"Check warnings above for details."
            )

        all_machines = [r for r in records if r.is_machine]
        machines = [r for r in all_machines if r.physical_machine != 0]

        # Build opdb_id→manufacturer-name lookup for clone detection.
        opdb_mfr_by_id: dict[str, str] = {
            r.opdb_id: r.manufacturer_name for r in records if r.manufacturer_name
        }
        non_physical_ids = {r.opdb_id for r in all_machines if r.physical_machine == 0}
        aliases = [r for r in records if r.is_alias]
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
        machine_models: list[tuple[MachineModel, OpdbRecord]] = []
        matched = 0
        created = 0
        skipped = 0

        for rec in machines:
            ipdb_id = rec.ipdb_id or ipdb_id_supplement.get(rec.opdb_id)

            pm = None
            if ipdb_id:
                pm = by_ipdb_id.get(ipdb_id)
            if not pm:
                pm = by_opdb_id.get(rec.opdb_id)

            if pm:
                matched += 1
                # Set opdb_id if not already set (conflict check in memory).
                if pm.opdb_id is None and rec.opdb_id:
                    if rec.opdb_id not in by_opdb_id:
                        pm.opdb_id = rec.opdb_id
                        by_opdb_id[rec.opdb_id] = pm
                        models_needing_opdb_update.append(pm)
                    else:
                        logger.warning(
                            "Cannot set opdb_id=%s on %r (ipdb_id=%s): "
                            "already owned by %r",
                            rec.opdb_id,
                            pm.name,
                            ipdb_id,
                            by_opdb_id[rec.opdb_id].name,
                        )
                elif pm.opdb_id and pm.opdb_id != rec.opdb_id:
                    logger.warning(
                        "MachineModel %r already has opdb_id=%s, skipping %s",
                        pm.name,
                        pm.opdb_id,
                        rec.opdb_id,
                    )
            else:
                created += 1
                slug = generate_unique_slug(rec.name, existing_slugs)
                pm = MachineModel(name=rec.name, opdb_id=rec.opdb_id, slug=slug)
                new_models.append(pm)
                by_opdb_id[rec.opdb_id] = pm
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
        normal_aliases: list[OpdbRecord] = []
        non_phys_groups: dict[str, list[OpdbRecord]] = {}

        for rec in aliases:
            if rec.parent_opdb_id in non_physical_ids:
                non_phys_groups.setdefault(rec.parent_opdb_id, []).append(rec)
            else:
                normal_aliases.append(rec)

        # --- Phase 1c: Promote default alias from each non-physical group ---
        promoted_new: list[MachineModel] = []
        promoted_update: list[MachineModel] = []
        promoted_count = 0
        review_issues = []

        for parent_id, group_aliases in non_phys_groups.items():
            default_rec, issues = pick_default_alias(group_aliases)
            review_issues.extend(issues)
            rest = [r for r in group_aliases if r is not default_rec]

            ipdb_id = default_rec.ipdb_id or ipdb_id_supplement.get(default_rec.opdb_id)

            # Match-or-create like Phase 1a, but as a standalone machine.
            pm = None
            if ipdb_id:
                pm = by_ipdb_id.get(ipdb_id)
            if not pm:
                pm = by_opdb_id.get(default_rec.opdb_id)

            if pm:
                if (
                    pm.opdb_id is None
                    and default_rec.opdb_id
                    and default_rec.opdb_id not in by_opdb_id
                ):
                    pm.opdb_id = default_rec.opdb_id
                    by_opdb_id[default_rec.opdb_id] = pm
                    promoted_update.append(pm)
                # Stale variant_of claims from prior runs are swept by
                # bulk_assert_claims(sweep_field="variant_of"); no direct
                # model mutation needed here.
            else:
                slug = generate_unique_slug(default_rec.name, existing_slugs)
                pm = MachineModel(
                    name=default_rec.name, opdb_id=default_rec.opdb_id, slug=slug
                )
                promoted_new.append(pm)
                by_opdb_id[default_rec.opdb_id] = pm
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
            MachineModel.objects.bulk_update(promoted_update, ["opdb_id"])

        if promoted_count:
            self.stdout.write(
                f"  Promoted {promoted_count} aliases from "
                f"{len(non_phys_groups)} non-physical groups"
            )

        # --- Phase 1d: Match/create normal aliases (stored as variants) ---
        new_variant_models: list[MachineModel] = []
        variant_models_needing_update: list[MachineModel] = []
        variant_models: list[tuple[MachineModel, OpdbRecord]] = []
        # Explicit mappings replace dict mutation (_variant_of_slug,
        # _skip_opdb_id_claim).
        variant_of_slugs: dict[str, str] = {}  # alias opdb_id → target slug
        skip_opdb_id_claims: set[str] = set()  # alias opdb_ids to skip
        alias_linked = 0
        alias_created = 0
        alias_skipped = 0

        for rec in normal_aliases:
            ipdb_id = rec.ipdb_id or ipdb_id_supplement.get(rec.opdb_id)

            # Find the parent machine in memory.
            parent = by_opdb_id.get(rec.parent_opdb_id)

            if not parent:
                logger.warning(
                    "Alias %s (%s): parent %s not found, skipping",
                    rec.opdb_id,
                    rec.name,
                    rec.parent_opdb_id,
                )
                alias_skipped += 1
                continue

            pm = None
            if ipdb_id:
                pm = by_ipdb_id.get(ipdb_id)
            if not pm:
                pm = by_opdb_id.get(rec.opdb_id)

            # Classify relationship using extracted logic.
            parent_mfr = opdb_mfr_by_id.get(rec.parent_opdb_id, "")
            is_conversion = rec.opdb_id in pinbase_is_conversion
            rel_type = classify_alias_relationship(
                rec.manufacturer_name, parent_mfr, is_conversion
            )

            if rel_type == "variant":
                # Chain collapse: if parent has a variant_of in pinbase,
                # point at the root instead.
                root_slug = pinbase_variant_of.get(parent.opdb_id)
                target_slug = root_slug or parent.slug
                # Skip self-referential: promoted non-physical parent may
                # chain-collapse back to the alias itself.
                if not (pm and target_slug == pm.slug):
                    variant_of_slugs[rec.opdb_id] = target_slug

            if pm:
                alias_linked += 1
                needs_update = False
                # Set opdb_id if not already set.
                if pm.opdb_id is None and rec.opdb_id:
                    if rec.opdb_id not in by_opdb_id:
                        pm.opdb_id = rec.opdb_id
                        by_opdb_id[rec.opdb_id] = pm
                        needs_update = True
                elif pm.opdb_id and pm.opdb_id != rec.opdb_id:
                    # Model already has a different opdb_id (e.g. matched by
                    # ipdb_id to a machine that has its own OPDB identity).
                    # Suppress the opdb_id claim so resolve_claims doesn't
                    # overwrite the correct value with the alias id.
                    skip_opdb_id_claims.add(rec.opdb_id)
                if needs_update:
                    variant_models_needing_update.append(pm)
            else:
                alias_created += 1
                slug = generate_unique_slug(rec.name, existing_slugs)
                pm = MachineModel(name=rec.name, opdb_id=rec.opdb_id, slug=slug)
                new_variant_models.append(pm)
                by_opdb_id[rec.opdb_id] = pm
                if ipdb_id:
                    by_ipdb_id[ipdb_id] = pm

            variant_models.append((pm, rec))

        if new_variant_models:
            MachineModel.objects.bulk_create(new_variant_models)
        if variant_models_needing_update:
            MachineModel.objects.bulk_update(variant_models_needing_update, ["opdb_id"])

        self.stdout.write(
            f"  Aliases — Linked: {alias_linked}, Created: {alias_created}, "
            f"Skipped: {alias_skipped}"
        )
        if new_variant_models:
            self.stdout.write(
                f"    New: {format_names([pm.name for pm in new_variant_models])}"
            )

        if review_issues:
            for issue in review_issues:
                logger.info(
                    "Review: [%s] %s — %s",
                    issue.issue_type,
                    issue.source_opdb_id,
                    issue.description,
                )

        # --- Phase 2: Collect claims ---
        pending_claims: list[Claim] = []

        for pm, rec in machine_models:
            self._collect_claims(
                pm,
                rec,
                ct_id,
                pending_claims,
                resolver,
                title_slug=title_slug_by_group.get(rec.group_opdb_id),
            )

        for pm, rec in variant_models:
            self._collect_claims(
                pm,
                rec,
                ct_id,
                pending_claims,
                resolver,
                variant_of_slug=variant_of_slugs.get(rec.opdb_id),
                skip_opdb_id_claim=rec.opdb_id in skip_opdb_id_claims,
                title_slug=title_slug_by_group.get(rec.group_opdb_id),
            )

        # --- Bulk-assert all collected claims ---
        # Sweep stale variant_of claims: if a model was previously a variant
        # but is now standalone (e.g. promoted from non-physical group), the
        # old variant_of claim must be deactivated.
        variant_of_scope: set[tuple[int, int]] = set()
        for pm, _rec in machine_models:
            variant_of_scope.add((ct_id, pm.pk))
        for pm, _rec in variant_models:
            variant_of_scope.add((ct_id, pm.pk))
        claim_stats = Claim.objects.bulk_assert_claims(
            source,
            pending_claims,
            sweep_field="variant_of",
            authoritative_scope=variant_of_scope,
        )
        self.stdout.write(
            f"  Claims: {claim_stats['unchanged']} unchanged, "
            f"{claim_stats['created']} created, "
            f"{claim_stats['superseded']} superseded, "
            f"{claim_stats['duplicates_removed']} duplicates removed"
        )

        self.stdout.write(self.style.SUCCESS("OPDB ingestion complete."))

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

    def _load_titles(
        self,
        path: str,
        source: Source,
        split_group_ids: set[str] | None = None,
    ) -> dict[str, str]:
        """Load groups JSON, create Title records, and assert name/short_name claims.

        Groups in *split_group_ids* are skipped — they have been split into
        separate titles in titles.json.

        Returns a dict mapping group opdb_id → title slug.
        """
        from django.contrib.contenttypes.models import ContentType

        from apps.catalog.resolve import TITLE_DIRECT_FIELDS, _resolve_bulk

        with open(path) as f:
            data = json.load(f)

        ct_id = ContentType.objects.get_for_model(Title).pk

        # Build lookup of raw group data, skipping split groups.
        _skip = split_group_ids or set()
        groups_by_id: dict[str, dict] = {}
        skipped_splits = 0
        for rec in data:
            opdb_id = rec.get("opdb_id")
            if not opdb_id:
                continue
            if opdb_id in _skip:
                skipped_splits += 1
                continue
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

        # Build the group_opdb_id → title_slug mapping (replaces _title_slug
        # injection into group dicts).
        title_slug_by_group: dict[str, str] = {}

        # Collect name and abbreviation claims for all titles from this source.
        pending_claims: list[Claim] = []
        touched_ids: set[int] = set()

        for opdb_id, rec in groups_by_id.items():
            title = all_titles.get(opdb_id)
            if not title:
                continue

            title_slug_by_group[opdb_id] = title.slug

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

        self.stdout.write(
            f"  Titles: {titles_created} created, {unchanged} unchanged"
            + (f", {skipped_splits} split groups skipped" if skipped_splits else "")
        )
        self.stdout.write(
            f"  Title claims: {claim_stats['created']} created, "
            f"{claim_stats['unchanged']} unchanged"
        )
        return title_slug_by_group

    # ------------------------------------------------------------------
    # Claim collection
    # ------------------------------------------------------------------

    def _collect_claims(
        self,
        pm: MachineModel,
        rec: OpdbRecord,
        ct_id: int,
        pending_claims: list[Claim],
        resolver: ManufacturerResolver,
        *,
        variant_of_slug: str | None = None,
        skip_opdb_id_claim: bool = False,
        title_slug: str | None = None,
    ) -> None:
        """Collect claim objects for a machine or alias record."""

        def _add(field_name: str, value) -> None:
            pending_claims.append(
                Claim(
                    content_type_id=ct_id,
                    object_id=pm.pk,
                    field_name=field_name,
                    value=value,
                )
            )

        if rec.name:
            _add("name", rec.name)
        if rec.opdb_id and not skip_opdb_id_claim:
            _add("opdb_id", rec.opdb_id)

        # Manufacturer: resolve OPDB name to slug at ingest time.
        if rec.manufacturer_name:
            slug = resolver.resolve_or_create(
                rec.manufacturer_name, trade_name=rec.manufacturer_name
            )
            _add("manufacturer", slug)

        # Date.
        if rec.manufacture_date:
            year, month = parse_opdb_date(rec.manufacture_date)
            if year is not None:
                _add("year", year)
            if month is not None:
                _add("month", month)

        # Player count.
        if rec.player_count is not None:
            _add("player_count", rec.player_count)

        # Technology generation (slug-based, resolved to FK).
        technology_generation = map_opdb_type(rec.type)
        if technology_generation:
            _add("technology_generation", technology_generation)

        # Display type (slug-based, resolved to FK).
        display_type = map_opdb_display(rec.display)
        if display_type:
            _add("display_type", display_type)

        # Extra data fields.
        # OPDB 'features' are variant labels (LE, SE, shaker motor etc.) — stored
        # as 'variant_features' to avoid future confusion with gameplay features.
        if rec.features:
            _add("opdb.variant_features", rec.features)

        # variant_of: determined by Phase 1d classification, passed explicitly.
        if variant_of_slug:
            _add("variant_of", variant_of_slug)

        for attr, claim_field in (
            ("keywords", "opdb.keywords"),
            ("description", "opdb.description"),
            ("common_name", "opdb.common_name"),
            ("images", "opdb.images"),
        ):
            value = getattr(rec, attr)
            if value:
                _add(claim_field, value)

        # Shortname becomes a relationship claim for abbreviations.
        if rec.shortname:
            claim_key, abbr_value = build_relationship_claim(
                "abbreviation", {"value": rec.shortname}
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

        # Title claim (passed explicitly from title_slug_by_group lookup).
        if title_slug:
            _add("title", title_slug)
