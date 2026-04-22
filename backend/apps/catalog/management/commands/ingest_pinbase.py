"""Ingest all Pinbase-authored data from exported JSON files.

Reads JSON files from the pinbase export directory (produced by
scripts/export_pinbase_json.py) and ingests them in dependency order:

  taxonomy → manufacturers → corporate entities → systems →
  people → series → titles → models

Each phase creates/updates Django records and asserts editorial claims
at priority 300, which outrank OPDB (200), IPDB (100), and other sources.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.claims import build_relationship_claim, make_authoritative_scope
from apps.catalog.ingestion.bulk_utils import generate_unique_slug
from apps.catalog.models import (
    Cabinet,
    CorporateEntity,
    Credit,
    CreditRole,
    DisplaySubtype,
    DisplayType,
    Franchise,
    GameFormat,
    GameplayFeature,
    Location,
    MachineModel,
    Manufacturer,
    Person,
    RewardType,
    Series,
    System,
    SystemMpuString,
    Tag,
    TechnologyGeneration,
    TechnologySubgeneration,
    Theme,
    Title,
)
from apps.catalog.resolve import (
    resolve_all_corporate_entity_locations,
    resolve_all_credits,
    resolve_all_entities,
    resolve_all_gameplay_features,
    resolve_all_location_aliases,
    resolve_all_reward_types,
    resolve_all_tags,
    resolve_all_themes,
    resolve_all_title_abbreviations,
    resolve_corporate_entity_aliases,
    resolve_entity,
    resolve_gameplay_feature_aliases,
    resolve_gameplay_feature_parents,
    resolve_manufacturer_aliases,
    resolve_person_aliases,
    resolve_reward_type_aliases,
    resolve_theme_aliases,
    resolve_theme_parents,
)
from apps.core.models import CatalogModel, LinkableModel
from apps.core.validators import bulk_create_validated
from apps.provenance.models import Claim, Source

logger = logging.getLogger(__name__)

DEFAULT_EXPORT_DIR = Path(__file__).parents[5] / "data" / "explore" / "pinbase"


def _parent_path(location_path: str) -> str | None:
    """Return the parent location_path by dropping the last segment, or None."""
    parts = location_path.rsplit("/", 1)
    return parts[0] if len(parts) > 1 else None


def _resolve_ce_location_path(entry: dict, loc_by_path: dict) -> str | None:
    """Return the canonical location_path for a CE entry, or None if absent."""
    path = (entry.get("headquarters_location") or "").strip()
    if not path:
        return None
    return path if path in loc_by_path else None


# Map authored credit role names to CreditRole slugs.
_CREDIT_ROLE_MAP: dict[str, str] = {
    "dots/animation": "animation",
}


def _normalize_credit_role(raw: str) -> str:
    """Normalize a credit role name to a CreditRole slug."""
    lower = raw.lower()
    return _CREDIT_ROLE_MAP.get(lower, lower)


# Model class → source slug suffix for per-entity AI description sources.
# Derived from CatalogModel subclasses so new catalog entities are picked up
# automatically. Location is not a CatalogModel but has its own AI source.
AI_DESC_SOURCE_REGISTRY: Sequence[tuple[type, str]] = tuple(
    (cls, cls.entity_type) for cls in CatalogModel.__subclasses__()
) + ((Location, "location"),)

# Taxonomy ingest registry: (json_filename, model_class, has_display_order, parent_config)
# parent_config: (model_fk_field, parent_model, json_fk_key) or None
TAXONOMY_REGISTRY = [
    # Top-level (no parent FK) — order matters: parents before children.
    ("technology_generation.json", TechnologyGeneration, True, None),
    ("display_type.json", DisplayType, True, None),
    ("cabinet.json", Cabinet, True, None),
    ("game_format.json", GameFormat, True, None),
    ("reward_type.json", RewardType, True, None),
    ("tag.json", Tag, True, None),
    ("credit_role.json", CreditRole, True, None),
    ("franchise.json", Franchise, False, None),
    # Child models (parents must be seeded first).
    (
        "technology_subgeneration.json",
        TechnologySubgeneration,
        True,
        ("technology_generation", TechnologyGeneration, "technology_generation_slug"),
    ),
    (
        "display_subtype.json",
        DisplaySubtype,
        True,
        ("display_type", DisplayType, "display_type_slug"),
    ),
]


def validate_cross_entity_wikilinks(export_dir: Path, stdout, stderr) -> None:
    """Validate cross-entity [[type:slug]] wikilinks in all taxonomy descriptions.

    Called by ingest_all after the full pipeline so all entities (manufacturers,
    titles, systems) are in the DB.  Broken references are printed as warnings;
    nothing is raised so a stale pindata link never aborts a completed ingest.
    """
    import json
    import re

    from django.apps import apps

    linkable_models: dict[str, Any] = {}
    for model in apps.get_models():
        if issubclass(model, LinkableModel) and hasattr(model, "slug"):
            model_name = model._meta.model_name
            if model_name is None:
                raise RuntimeError(f"{model.__name__} has no model_name")
            link_type = getattr(
                model,
                "link_type_name",
                model_name.replace("_", "-"),
            )
            linkable_models[link_type] = model

    pattern = re.compile(r"\[\[([a-z0-9-]+):([a-zA-Z0-9_-]+)\]\]")
    broken: list[str] = []

    for json_file, _, _, _ in TAXONOMY_REGISTRY:
        path = export_dir / json_file
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        for entry in data:
            description = entry.get("description", "")
            if not description:
                continue
            for link_type, slug in pattern.findall(description):
                target_model = linkable_models.get(link_type)
                if target_model is None:
                    broken.append(
                        f"  {json_file} {entry['slug']}: unknown link type {link_type!r}"
                    )
                elif not target_model.objects.filter(slug=slug).exists():
                    broken.append(
                        f"  {json_file} {entry['slug']}: [[{link_type}:{slug}]] not found"
                    )

    if broken:
        stderr.write(
            f"Wikilink warnings ({len(broken)} broken references):\n"
            + "\n".join(broken)
        )


class Command(BaseCommand):
    help = "Ingest all Pinbase-authored data from exported JSON files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--export-dir",
            default=str(DEFAULT_EXPORT_DIR),
            help="Path to exported Pinbase JSON directory.",
        )

    def handle(self, *args, **options):
        self.export_dir = Path(options["export_dir"])

        # Create sources used across phases.
        self.pinbase_source, _ = Source.objects.get_or_create(
            slug="pinbase",
            defaults={
                "name": "Pinbase",
                "source_type": Source.SourceType.EDITORIAL,
                "priority": 300,
                "description": "Pinbase curated data.",
            },
        )
        self.editorial_source, _ = Source.objects.update_or_create(
            slug="editorial",
            defaults={
                "name": "Editorial",
                "source_type": Source.SourceType.EDITORIAL,
                "priority": 300,
            },
        )

        # Per-entity-type AI description sources. Each can be toggled
        # independently via is_enabled in admin.
        self._ai_desc_sources: dict[type, Source] = {}
        for model_class, slug_suffix in AI_DESC_SOURCE_REGISTRY:
            src, _ = Source.objects.get_or_create(
                slug=f"pinbase-ai-desc-{slug_suffix}",
                defaults={
                    "name": f"Pinbase AI Descriptions ({model_class.__name__})",
                    "source_type": Source.SourceType.EDITORIAL,
                    "priority": 300,
                },
            )
            self._ai_desc_sources[model_class] = src

        # Description claims contain wikilinks like [[manufacturer:williams]]
        # that are converted to [[manufacturer:id:42]] during validation.
        # Defer them until all entities exist so the lookups succeed.
        self._deferred_desc_claims: list[tuple[type, Claim]] = []

        for phase in [
            self._ingest_locations,
            self._ingest_taxonomy,
            self._ingest_themes,
            self._ingest_gameplay_features,
            self._sync_reward_type_aliases,
            self._ingest_manufacturers,
            self._ingest_corporate_entities,
            self._ingest_systems,
            self._ingest_people,
            self._ingest_series,
            self._ingest_titles,
            self._ingest_models,
            self._flush_deferred_descriptions,
        ]:
            self._run_timed(phase)

        self.stdout.write(self.style.SUCCESS("Pinbase ingestion complete."))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run_timed(self, phase):
        """Run a phase function and print elapsed time."""
        start = time.monotonic()
        phase()
        elapsed = time.monotonic() - start
        if elapsed >= 1:
            self.stdout.write(f"  ({elapsed:.0f}s)")

    def _assert_claims_split_descriptions(
        self,
        model_class: type,
        pending_claims: list[Claim],
        **kwargs,
    ) -> dict[str, int]:
        """Assert claims, deferring description claims for later.

        Non-description claims go to self.pinbase_source immediately.
        Description claims are stashed in ``_deferred_desc_claims`` and
        flushed at the end of the pipeline (after all entities exist)
        so that wikilink validation can resolve cross-references.
        """
        desc_claims = [c for c in pending_claims if c.field_name == "description"]
        other_claims = [c for c in pending_claims if c.field_name != "description"]

        stats: dict[str, int] = {
            "unchanged": 0,
            "created": 0,
            "superseded": 0,
            "swept": 0,
            "duplicates_removed": 0,
        }

        if other_claims:
            s = Claim.objects.bulk_assert_claims(
                self.pinbase_source, other_claims, **kwargs
            )
            for k in stats:
                stats[k] += s[k]

        if desc_claims:
            self._deferred_desc_claims.extend((model_class, c) for c in desc_claims)

        return stats

    def _flush_deferred_descriptions(self):
        """Assert all deferred description claims now that every entity exists."""
        if not self._deferred_desc_claims:
            return

        # Group by model class so each batch goes to the right AI source.
        by_model: dict[type, list[Claim]] = {}
        for model_class, claim in self._deferred_desc_claims:
            by_model.setdefault(model_class, []).append(claim)

        total_created = 0
        total_unchanged = 0
        for model_class, claims in by_model.items():
            ai_source = self._ai_desc_sources.get(model_class)
            if ai_source is None:
                ai_source = self.pinbase_source
            s = Claim.objects.bulk_assert_claims(ai_source, claims)
            total_created += s["created"]
            total_unchanged += s["unchanged"]

            # Re-resolve affected entities so descriptions land on the objects.
            obj_ids = {c.object_id for c in claims}
            resolve_all_entities(model_class, object_ids=obj_ids)

        self.stdout.write(
            f"  Deferred descriptions: {total_created} created, "
            f"{total_unchanged} unchanged"
        )

    def _assert_alias_claims(
        self,
        source,
        ct_id: int,
        aliases_by_pk: dict[int, list[str]],
        field_name: str,
    ) -> dict:
        """Assert alias claims for a batch of entities.

        aliases_by_pk: {entity_pk: [alias_str, ...]}
        All alias values are lowercased before assertion (make_claim_key is
        case-sensitive; the DB UniqueConstraint uses Lower("value"), so
        normalising at claim time keeps the two consistent).
        Returns bulk_assert_claims stats.
        """
        pending: list[Claim] = []
        for pk, alias_values in aliases_by_pk.items():
            for alias_str in alias_values:
                lower = alias_str.lower()
                claim_key, value = build_relationship_claim(
                    field_name, {"alias_value": lower, "alias_display": alias_str}
                )
                pending.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=pk,
                        field_name=field_name,
                        claim_key=claim_key,
                        value=value,
                    )
                )
        scope = {(ct_id, pk) for pk in aliases_by_pk}
        return Claim.objects.bulk_assert_claims(
            source, pending, sweep_field=field_name, authoritative_scope=scope
        )

    def _load(self, filename: str) -> list[dict]:
        path = self.export_dir / filename
        if not path.exists():
            self.stderr.write(f"  Skipping {filename} (not found)")
            return []
        with open(path) as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # Phase 0: Locations
    # ------------------------------------------------------------------

    def _ingest_locations(self):
        """Ingest canonical Location records from location.json.

        Runs before all other phases so that location_path lookups are
        available when corporate entities are ingested.
        """
        entries = self._load("location.json")
        if not entries:
            return

        source = self.pinbase_source
        ct = ContentType.objects.get_for_model(Location)

        # Sort: countries first (type order 0), then intermediates (1), then cities (2).
        # Within each tier, sort by location_path so parents always precede children.
        type_order = {"country": 0, "city": 2}
        entries_sorted = sorted(
            entries,
            key=lambda e: (type_order.get(e["type"], 1), e["location_path"]),
        )

        # Pass 1: upsert Location rows (slug + display fields).
        objs = bulk_create_validated(
            Location,
            [
                Location(
                    location_path=e["location_path"],
                    slug=e["slug"],
                    name=e["name"],
                    location_type=e["type"],
                    code=e.get("code", ""),
                    short_name=e.get("short_name", ""),
                    divisions=e.get("divisions"),
                )
                for e in entries_sorted
            ],
            update_conflicts=True,
            unique_fields=["location_path"],
            update_fields=[
                "slug",
                "name",
                "location_type",
                "code",
                "short_name",
                "divisions",
            ],
        )

        # Pass 2: build scalar + FK claims and alias data.
        pending_claims: list[Claim] = []
        alias_by_pk: dict[int, list[str]] = {}

        for obj, entry in zip(objs, entries_sorted, strict=True):
            pending_claims.append(
                Claim.for_object(obj, field_name="slug", value=entry["slug"])
            )
            pending_claims.append(
                Claim.for_object(obj, field_name="name", value=entry["name"])
            )
            pending_claims.append(
                Claim.for_object(obj, field_name="location_type", value=entry["type"])
            )
            if entry.get("code"):
                pending_claims.append(
                    Claim(
                        content_type_id=ct.pk,
                        object_id=obj.pk,
                        field_name="code",
                        value=entry["code"],
                    )
                )
            if entry.get("short_name"):
                pending_claims.append(
                    Claim(
                        content_type_id=ct.pk,
                        object_id=obj.pk,
                        field_name="short_name",
                        value=entry["short_name"],
                    )
                )
            if entry.get("divisions"):
                pending_claims.append(
                    Claim(
                        content_type_id=ct.pk,
                        object_id=obj.pk,
                        field_name="divisions",
                        value=entry["divisions"],
                    )
                )
            parent_path = _parent_path(entry["location_path"])
            if parent_path:
                pending_claims.append(
                    Claim(
                        content_type_id=ct.pk,
                        object_id=obj.pk,
                        field_name="parent",
                        value=parent_path,
                    )
                )
            if entry.get("aliases"):
                alias_by_pk[obj.pk] = entry["aliases"]

        Claim.objects.bulk_assert_claims(source, pending_claims)
        resolve_all_entities(Location)

        alias_stats = self._assert_alias_claims(
            source, ct.pk, alias_by_pk, "location_alias"
        )
        resolve_all_location_aliases()

        self.stdout.write(
            f"  Locations: {len(objs)} upserted, "
            f"{alias_stats['created']} aliases created"
        )

    # ------------------------------------------------------------------
    # Phase 1: Taxonomy
    # ------------------------------------------------------------------

    def _ingest_taxonomy(self):
        for (
            json_file,
            model_class,
            has_display_order,
            parent_config,
        ) in TAXONOMY_REGISTRY:
            data = self._load(json_file)
            if not data:
                continue

            # Resolve parent FK lookup if needed.
            parent_lookup = {}
            if parent_config:
                _, parent_model, _ = parent_config
                parent_lookup = {p.slug: p for p in parent_model.objects.all()}

            # Build model instances, tracking entries that survive filtering.
            objs = []
            entries_used = []
            for entry in data:
                slug = entry["slug"]
                name = entry["name"]
                description = entry.get("description", "")
                display_order = entry.get("display_order", 0)

                kwargs: dict = {
                    "slug": slug,
                    "name": name,
                    "description": description,
                }
                if has_display_order:
                    kwargs["display_order"] = display_order

                if parent_config:
                    fk_field, _, json_fk_key = parent_config
                    parent_slug = entry[json_fk_key]
                    parent_obj = parent_lookup.get(parent_slug)
                    if parent_obj is None:
                        logger.warning(
                            "Parent slug %r not found for %s %r — skipping",
                            parent_slug,
                            model_class.__name__,
                            slug,
                        )
                        continue
                    kwargs[fk_field] = parent_obj

                objs.append(model_class(**kwargs))
                entries_used.append(entry)

            # Bulk upsert.
            update_fields = ["name", "description"]
            if has_display_order:
                update_fields.append("display_order")
            if parent_config:
                fk_field, _, _ = parent_config
                update_fields.append(fk_field)

            objs = bulk_create_validated(
                model_class,
                objs,
                update_conflicts=True,
                unique_fields=["slug"],
                update_fields=update_fields,
            )

            # Assert claims.
            pending_claims: list[Claim] = []
            for obj, entry in zip(objs, entries_used, strict=True):
                pending_claims.append(
                    Claim.for_object(obj, field_name="slug", value=obj.slug)
                )
                pending_claims.append(
                    Claim.for_object(obj, field_name="name", value=obj.name)
                )
                if has_display_order:
                    pending_claims.append(
                        Claim.for_object(
                            obj, field_name="display_order", value=obj.display_order
                        )
                    )
                if parent_config:
                    fk_field, _, json_fk_key = parent_config
                    pending_claims.append(
                        Claim.for_object(
                            obj, field_name=fk_field, value=entry[json_fk_key]
                        )
                    )
                description = entry.get("description", "")
                if description:
                    pending_claims.append(
                        Claim.for_object(
                            obj, field_name="description", value=description
                        )
                    )

            stats = self._assert_claims_split_descriptions(model_class, pending_claims)
            label = model_class.__name__
            self.stdout.write(
                f"  {label}: {len(data)} records — "
                f"{stats['created']} claims created, "
                f"{stats['unchanged']} unchanged"
            )

    # ------------------------------------------------------------------
    # Phase 1b: Themes (entities + parents + aliases)
    # ------------------------------------------------------------------

    def _ingest_themes(self):
        entries = self._load("theme.json")
        if not entries:
            return

        source = self.pinbase_source
        ct = ContentType.objects.get_for_model(Theme)

        # --- Entity upsert ---
        objs = [
            Theme(slug=e["slug"], name=e["name"], description=e.get("description", ""))
            for e in entries
        ]
        objs = bulk_create_validated(
            Theme,
            objs,
            update_conflicts=True,
            unique_fields=["slug"],
            update_fields=["name", "description"],
        )

        # --- Entity claims ---
        pending_claims: list[Claim] = []
        for obj, entry in zip(objs, entries, strict=True):
            pending_claims.append(
                Claim.for_object(obj, field_name="slug", value=obj.slug)
            )
            pending_claims.append(
                Claim(
                    content_type_id=ct.pk,
                    object_id=obj.pk,
                    field_name="name",
                    value=obj.name,
                )
            )
            description = entry.get("description", "")
            if description:
                pending_claims.append(
                    Claim(
                        content_type_id=ct.pk,
                        object_id=obj.pk,
                        field_name="description",
                        value=description,
                    )
                )

        stats = self._assert_claims_split_descriptions(Theme, pending_claims)
        resolve_all_entities(Theme)
        self.stdout.write(
            f"  Theme: {len(entries)} records — "
            f"{stats['created']} claims created, "
            f"{stats['unchanged']} unchanged"
        )

        # --- Parents (claim-controlled) ---
        themes_by_name = {t.name: t for t in Theme.objects.all()}
        all_theme_pks: set[int] = {t.pk for t in themes_by_name.values()}
        parent_claims: list[Claim] = []

        for entry in entries:
            theme = themes_by_name.get(entry["name"])
            if theme is None:
                continue
            for pname in entry.get("parents", []):
                parent = themes_by_name.get(pname)
                if parent is None:
                    logger.warning(
                        "Theme parent %r not found for theme %r — skipping",
                        pname,
                        entry["name"],
                    )
                    continue
                claim_key, value = build_relationship_claim(
                    "theme_parent", {"parent": parent.pk}
                )
                parent_claims.append(
                    Claim(
                        content_type_id=ct.pk,
                        object_id=theme.pk,
                        field_name="theme_parent",
                        claim_key=claim_key,
                        value=value,
                    )
                )

        scope = make_authoritative_scope(Theme, all_theme_pks)
        parent_stats = Claim.objects.bulk_assert_claims(
            source, parent_claims, sweep_field="theme_parent", authoritative_scope=scope
        )
        resolve_theme_parents()
        self.stdout.write(
            f"  Theme parents: {parent_stats['created']} created, "
            f"{parent_stats['unchanged']} unchanged, {parent_stats['swept']} swept"
        )

        # --- Aliases (claim-controlled) ---
        aliases_by_pk: dict[int, list[str]] = {}
        for entry in entries:
            theme = themes_by_name.get(entry["name"])
            if theme is None:
                continue
            aliases_by_pk[theme.pk] = entry.get("aliases", [])

        alias_stats = self._assert_alias_claims(
            source, ct.pk, aliases_by_pk, "theme_alias"
        )
        resolve_theme_aliases()
        self.stdout.write(
            f"  Theme aliases: {alias_stats['created']} created, "
            f"{alias_stats['unchanged']} unchanged, {alias_stats['swept']} swept"
        )

    # ------------------------------------------------------------------
    # Phase 1d: Gameplay features (entities + parents + aliases)
    # ------------------------------------------------------------------

    def _ingest_gameplay_features(self):
        entries = self._load("gameplay_feature.json")
        if not entries:
            return

        source = self.pinbase_source
        ct = ContentType.objects.get_for_model(GameplayFeature)

        # --- Entity upsert ---
        objs = [
            GameplayFeature(
                slug=e["slug"], name=e["name"], description=e.get("description", "")
            )
            for e in entries
        ]
        objs = bulk_create_validated(
            GameplayFeature,
            objs,
            update_conflicts=True,
            unique_fields=["slug"],
            update_fields=["name", "description"],
        )

        # --- Entity claims ---
        pending_claims: list[Claim] = []
        for obj, entry in zip(objs, entries, strict=True):
            pending_claims.append(
                Claim.for_object(obj, field_name="slug", value=obj.slug)
            )
            pending_claims.append(
                Claim(
                    content_type_id=ct.pk,
                    object_id=obj.pk,
                    field_name="name",
                    value=obj.name,
                )
            )
            description = entry.get("description", "")
            if description:
                pending_claims.append(
                    Claim(
                        content_type_id=ct.pk,
                        object_id=obj.pk,
                        field_name="description",
                        value=description,
                    )
                )

        stats = self._assert_claims_split_descriptions(GameplayFeature, pending_claims)
        resolve_all_entities(GameplayFeature)
        self.stdout.write(
            f"  GameplayFeature: {len(entries)} records — "
            f"{stats['created']} claims created, "
            f"{stats['unchanged']} unchanged"
        )

        # --- Parents (claim-controlled, identified by slug) ---
        features_by_slug = {f.slug: f for f in GameplayFeature.objects.all()}
        all_feature_pks: set[int] = {f.pk for f in features_by_slug.values()}
        parent_claims: list[Claim] = []

        for entry in entries:
            feature = features_by_slug.get(entry["slug"])
            if feature is None:
                continue
            for parent_slug in entry.get("is_type_of", []):
                if parent_slug not in features_by_slug:
                    raise CommandError(
                        f"GameplayFeature parent slug {parent_slug!r} not found "
                        f"(referenced by {entry['slug']!r})"
                    )
                claim_key, value = build_relationship_claim(
                    "gameplay_feature_parent",
                    {"parent": features_by_slug[parent_slug].pk},
                )
                parent_claims.append(
                    Claim(
                        content_type_id=ct.pk,
                        object_id=feature.pk,
                        field_name="gameplay_feature_parent",
                        claim_key=claim_key,
                        value=value,
                    )
                )

        scope = make_authoritative_scope(GameplayFeature, all_feature_pks)
        parent_stats = Claim.objects.bulk_assert_claims(
            source,
            parent_claims,
            sweep_field="gameplay_feature_parent",
            authoritative_scope=scope,
        )
        resolve_gameplay_feature_parents()
        self.stdout.write(
            f"  Feature parents: {parent_stats['created']} created, "
            f"{parent_stats['unchanged']} unchanged, {parent_stats['swept']} swept"
        )

        # --- Aliases (claim-controlled) ---
        aliases_by_pk: dict[int, list[str]] = {}
        for entry in entries:
            feature = features_by_slug.get(entry["slug"])
            if feature is None:
                continue
            aliases_by_pk[feature.pk] = entry.get("aliases", [])

        alias_stats = self._assert_alias_claims(
            source, ct.pk, aliases_by_pk, "gameplay_feature_alias"
        )
        resolve_gameplay_feature_aliases()
        self.stdout.write(
            f"  Feature aliases: {alias_stats['created']} created, "
            f"{alias_stats['unchanged']} unchanged, {alias_stats['swept']} swept"
        )

    # ------------------------------------------------------------------
    # Phase 1e: RewardType aliases
    # ------------------------------------------------------------------

    def _sync_reward_type_aliases(self):
        rt_entries = self._load("reward_type.json")
        if not rt_entries:
            return

        source = self.pinbase_source
        rt_by_slug = {r.slug: r for r in RewardType.objects.all()}
        rt_ct_id = ContentType.objects.get_for_model(RewardType).pk
        rt_aliases_by_pk: dict[int, list[str]] = {}
        for entry in rt_entries:
            rt = rt_by_slug.get(entry["slug"])
            if rt is None:
                continue
            rt_aliases_by_pk[rt.pk] = entry.get("aliases", [])

        rt_alias_stats = self._assert_alias_claims(
            source, rt_ct_id, rt_aliases_by_pk, "reward_type_alias"
        )
        resolve_reward_type_aliases()
        self.stdout.write(
            f"  RewardType aliases: {rt_alias_stats['created']} created, "
            f"{rt_alias_stats['unchanged']} unchanged, "
            f"{rt_alias_stats['swept']} swept"
        )

    # ------------------------------------------------------------------
    # Phase 2: Manufacturers
    # ------------------------------------------------------------------

    def _ingest_manufacturers(self):
        entries = self._load("manufacturer.json")
        if not entries:
            return

        source = self.editorial_source
        existing_slugs = set(Manufacturer.objects.values_list("slug", flat=True))

        objs = [
            Manufacturer(
                slug=e["slug"],
                name=e["name"],
                opdb_manufacturer_id=e.get("opdb_manufacturer_id"),
            )
            for e in entries
        ]
        objs = bulk_create_validated(
            Manufacturer,
            objs,
            update_conflicts=True,
            unique_fields=["slug"],
            update_fields=["name", "opdb_manufacturer_id"],
        )

        created = sum(1 for o in objs if o.slug not in existing_slugs)
        self.stdout.write(
            f"  Manufacturers: {created} created, {len(objs) - created} updated"
        )

        pending_claims: list[Claim] = []
        for obj, entry in zip(objs, entries, strict=True):
            pending_claims.append(
                Claim.for_object(obj, field_name="slug", value=obj.slug)
            )
            pending_claims.append(
                Claim.for_object(obj, field_name="name", value=obj.name)
            )
            if obj.opdb_manufacturer_id is not None:
                pending_claims.append(
                    Claim.for_object(
                        obj,
                        field_name="opdb_manufacturer_id",
                        value=obj.opdb_manufacturer_id,
                    )
                )
            description = entry.get("description", "")
            if description:
                pending_claims.append(
                    Claim.for_object(obj, field_name="description", value=description)
                )

        if pending_claims:
            stats = self._assert_claims_split_descriptions(Manufacturer, pending_claims)
            self.stdout.write(
                f"  Claims: {stats['unchanged']} unchanged, "
                f"{stats['created']} created, {stats['superseded']} superseded"
            )
            touched_ids = {o.pk for o in objs}
            resolve_all_entities(Manufacturer, object_ids=touched_ids)

        # Sync aliases (claim-controlled).
        mfr_by_slug = {o.slug: o for o in objs}
        mfr_ct_id = ContentType.objects.get_for_model(Manufacturer).pk
        aliases_by_pk: dict[int, list[str]] = {}
        for entry in entries:
            mfr = mfr_by_slug.get(entry["slug"])
            if not mfr:
                continue
            aliases_by_pk[mfr.pk] = entry.get("aliases", [])

        alias_stats = self._assert_alias_claims(
            source, mfr_ct_id, aliases_by_pk, "manufacturer_alias"
        )
        resolve_manufacturer_aliases()
        self.stdout.write(
            f"  Aliases: {alias_stats['created']} created, "
            f"{alias_stats['unchanged']} unchanged, {alias_stats['swept']} swept"
        )

    # ------------------------------------------------------------------
    # Phase 3: Corporate entities
    # ------------------------------------------------------------------

    def _ingest_corporate_entities(self):
        entries = self._load("corporate_entity.json")
        if not entries:
            return

        source = self.editorial_source
        ct_id = ContentType.objects.get_for_model(CorporateEntity).pk
        mfr_by_slug = {m.slug: m for m in Manufacturer.objects.all()}
        existing_slugs = set(CorporateEntity.objects.values_list("slug", flat=True))

        objs = []
        valid_entries = []
        missing_mfr: list[str] = []
        seen_slugs: set[str] = set()

        for entry in entries:
            mfr_slug = entry["manufacturer_slug"]
            mfr = mfr_by_slug.get(mfr_slug)
            if mfr is None:
                missing_mfr.append(mfr_slug)
                logger.warning(
                    "Manufacturer slug %r not found for CE %r", mfr_slug, entry["name"]
                )
                continue

            slug = entry.get("slug", "")
            if slug in seen_slugs:
                logger.warning("Duplicate corporate entity slug %r — skipping", slug)
                continue
            seen_slugs.add(slug)

            objs.append(
                CorporateEntity(
                    manufacturer=mfr,
                    name=entry["name"],
                    slug=entry.get("slug", ""),
                    year_start=entry.get("year_start"),
                    year_end=entry.get("year_end"),
                    ipdb_manufacturer_id=entry.get("ipdb_manufacturer_id"),
                )
            )
            valid_entries.append(entry)

        objs = bulk_create_validated(
            CorporateEntity,
            objs,
            update_conflicts=True,
            unique_fields=["slug"],
            update_fields=["name", "year_start", "year_end", "ipdb_manufacturer_id"],
        )

        created = sum(1 for o in objs if o.slug not in existing_slugs)
        self.stdout.write(
            f"  Corporate entities: {created} created, {len(objs) - created} updated"
        )

        if missing_mfr:
            self.stderr.write(
                f"  Warning: {len(missing_mfr)} missing manufacturer slug(s)"
            )

        # Assert claims and resolve.
        pending_claims: list[Claim] = []
        for obj in objs:
            pending_claims.append(
                Claim.for_object(obj, field_name="slug", value=obj.slug)
            )
            pending_claims.append(
                Claim.for_object(obj, field_name="name", value=obj.name)
            )
            pending_claims.append(
                Claim.for_object(
                    obj, field_name="manufacturer", value=obj.manufacturer.slug
                )
            )
            if obj.ipdb_manufacturer_id is not None:
                pending_claims.append(
                    Claim.for_object(
                        obj,
                        field_name="ipdb_manufacturer_id",
                        value=obj.ipdb_manufacturer_id,
                    )
                )
            if obj.year_start is not None:
                pending_claims.append(
                    Claim.for_object(obj, field_name="year_start", value=obj.year_start)
                )
            if obj.year_end is not None:
                pending_claims.append(
                    Claim.for_object(obj, field_name="year_end", value=obj.year_end)
                )

        if pending_claims:
            stats = self._assert_claims_split_descriptions(
                CorporateEntity, pending_claims
            )
            self.stdout.write(
                f"  Claims: {stats['unchanged']} unchanged, "
                f"{stats['created']} created, {stats['superseded']} superseded"
            )
            for ce in objs:
                resolve_entity(ce)

        # Assert alias claims.
        aliases_by_pk: dict[int, list[str]] = {}
        for obj, entry in zip(objs, valid_entries, strict=True):
            entry_aliases = entry.get("aliases", [])
            if entry_aliases:
                aliases_by_pk[obj.pk] = entry_aliases

        if aliases_by_pk:
            alias_stats = self._assert_alias_claims(
                source, ct_id, aliases_by_pk, "corporate_entity_alias"
            )
            self.stdout.write(
                f"  CE aliases: {alias_stats['created']} created, "
                f"{alias_stats['unchanged']} unchanged"
            )
        resolve_corporate_entity_aliases()

        # Assert location relationship claims and sync CorporateEntityLocation rows.
        loc_by_path = {
            loc.location_path: loc
            for loc in Location.objects.only("location_path", "pk")
        }
        location_claims: list[Claim] = []
        all_ce_pks: set[int] = {obj.pk for obj in objs}

        for obj, entry in zip(objs, valid_entries, strict=True):
            hq_path = _resolve_ce_location_path(entry, loc_by_path)
            if hq_path:
                claim_key, value = build_relationship_claim(
                    "location", {"location": loc_by_path[hq_path].pk}
                )
                location_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=obj.pk,
                        field_name="location",
                        claim_key=claim_key,
                        value=value,
                    )
                )
            elif entry.get("headquarters_location"):
                raise CommandError(
                    f"CE {entry['slug']!r}: headquarters_location "
                    f"{entry['headquarters_location']!r} is not a known canonical Location."
                )

        Claim.objects.bulk_assert_claims(
            source,
            location_claims,
            sweep_field="location",
            authoritative_scope=make_authoritative_scope(CorporateEntity, all_ce_pks),
        )
        loc_stats = resolve_all_corporate_entity_locations()
        self.stdout.write(
            f"  Locations: {loc_stats['created']} created, {loc_stats['deleted']} deleted"
        )

    # ------------------------------------------------------------------
    # Phase 4: Systems
    # ------------------------------------------------------------------

    def _ingest_systems(self):
        entries = self._load("system.json")
        if not entries:
            return

        mfr_by_slug = {m.slug: m for m in Manufacturer.objects.all()}
        subgen_by_slug = {t.slug: t for t in TechnologySubgeneration.objects.all()}
        existing_slugs = set(System.objects.values_list("slug", flat=True))

        objs = []
        for entry in entries:
            mfr_slug = entry.get("manufacturer_slug")
            mfr = mfr_by_slug.get(mfr_slug) if mfr_slug else None
            subgen_slug = entry.get("technology_subgeneration_slug")
            subgen = subgen_by_slug.get(subgen_slug) if subgen_slug else None

            objs.append(
                System(
                    slug=entry["slug"],
                    name=entry["name"],
                    description=entry.get("description", ""),
                    manufacturer=mfr,
                    technology_subgeneration=subgen,
                )
            )

        objs = bulk_create_validated(
            System,
            objs,
            update_conflicts=True,
            unique_fields=["slug"],
            update_fields=[
                "name",
                "description",
                "manufacturer",
                "technology_subgeneration",
            ],
        )

        created = sum(1 for o in objs if o.slug not in existing_slugs)
        self.stdout.write(
            f"  Systems: {created} created, {len(objs) - created} updated"
        )

        pending_claims: list[Claim] = []
        for obj, entry in zip(objs, entries, strict=True):
            pending_claims.append(
                Claim.for_object(obj, field_name="slug", value=obj.slug)
            )
            for field in ("name", "description"):
                value = entry.get(field, "")
                if value:
                    pending_claims.append(
                        Claim.for_object(obj, field_name=field, value=value)
                    )
            mfr_slug = entry.get("manufacturer_slug")
            if mfr_slug:
                pending_claims.append(
                    Claim.for_object(obj, field_name="manufacturer", value=mfr_slug)
                )
            subgen_slug = entry.get("technology_subgeneration_slug")
            if subgen_slug:
                pending_claims.append(
                    Claim.for_object(
                        obj,
                        field_name="technology_subgeneration",
                        value=subgen_slug,
                    )
                )

        if pending_claims:
            stats = self._assert_claims_split_descriptions(System, pending_claims)
            self.stdout.write(
                f"  Claims: {stats['created']} created, {stats['unchanged']} unchanged"
            )

        # Sync MPU strings.
        sys_by_slug = {o.slug: o for o in objs}
        existing_mpus: dict[int, set[str]] = {}
        for ms in SystemMpuString.objects.all():
            existing_mpus.setdefault(ms.system_id, set()).add(ms.value)

        mpu_to_create: list[SystemMpuString] = []
        mpu_to_delete: dict[int, set[str]] = {}
        for entry in entries:
            mpu_values = entry.get("mpu_strings", [])
            system = sys_by_slug.get(entry["slug"])
            if not system:
                continue

            existing = existing_mpus.get(system.pk, set())
            desired = set(mpu_values)

            for v in desired - existing:
                mpu_to_create.append(SystemMpuString(system=system, value=v))
            removed = existing - desired
            if removed:
                mpu_to_delete[system.pk] = removed

        mpu_created = len(mpu_to_create)
        if mpu_to_create:
            bulk_create_validated(SystemMpuString, mpu_to_create)
        mpu_deleted = 0
        for sys_pk, values in mpu_to_delete.items():
            mpu_deleted += SystemMpuString.objects.filter(
                system_id=sys_pk, value__in=values
            ).delete()[0]

        if mpu_created or mpu_deleted:
            self.stdout.write(
                f"  MPU strings: {mpu_created} created, {mpu_deleted} deleted"
            )

    # ------------------------------------------------------------------
    # Phase 5: People
    # ------------------------------------------------------------------

    def _ingest_people(self):
        entries = self._load("person.json")
        if not entries:
            return

        source = self.pinbase_source
        ct_id = ContentType.objects.get_for_model(Person).pk
        existing_slugs = set(Person.objects.values_list("slug", flat=True))

        objs = [Person(slug=e["slug"], name=e["name"]) for e in entries]
        objs = bulk_create_validated(
            Person,
            objs,
            update_conflicts=True,
            unique_fields=["slug"],
            update_fields=["name"],
        )

        created = sum(1 for o in objs if o.slug not in existing_slugs)
        persons_by_slug = {o.slug: o for o in objs}
        self.stdout.write(f"  People: {created} created, {len(objs) - created} updated")

        # Assert name/description claims.
        pending_claims: list[Claim] = []
        for entry in entries:
            person = persons_by_slug.get(entry["slug"])
            if not person:
                continue
            pending_claims.append(
                Claim.for_object(person, field_name="slug", value=person.slug)
            )
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
            stats = self._assert_claims_split_descriptions(Person, pending_claims)
            self.stdout.write(
                f"  Claims: {stats['created']} created, {stats['unchanged']} unchanged"
            )

        # Sync PersonAlias rows (claim-controlled).
        person_ct_id = ContentType.objects.get_for_model(Person).pk
        person_aliases_by_pk: dict[int, list[str]] = {}
        for entry in entries:
            person = persons_by_slug.get(entry["slug"])
            if not person:
                continue
            person_aliases_by_pk[person.pk] = entry.get("aliases", [])

        alias_stats = self._assert_alias_claims(
            source, person_ct_id, person_aliases_by_pk, "person_alias"
        )
        resolve_person_aliases()
        self.stdout.write(
            f"  Aliases: {alias_stats['created']} created, "
            f"{alias_stats['unchanged']} unchanged, {alias_stats['swept']} swept"
        )

    # ------------------------------------------------------------------
    # Phase 6: Series
    # ------------------------------------------------------------------

    def _ingest_series(self):
        series_entries = self._load("series.json")
        if not series_entries:
            return

        ct_id = ContentType.objects.get_for_model(Series).pk
        existing_slugs = set(Series.objects.values_list("slug", flat=True))

        objs = [
            Series(
                slug=e["slug"],
                name=e["name"],
                description=e.get("description", ""),
            )
            for e in series_entries
        ]
        objs = bulk_create_validated(
            Series,
            objs,
            update_conflicts=True,
            unique_fields=["slug"],
            update_fields=["name", "description"],
        )

        created = sum(1 for o in objs if o.slug not in existing_slugs)
        series_by_slug = {o.slug: o for o in objs}
        self.stdout.write(f"  Series: {created} created, {len(objs) - created} updated")

        # Assert claims.
        pending_claims: list[Claim] = []
        for obj, entry in zip(objs, series_entries, strict=True):
            pending_claims.append(
                Claim.for_object(obj, field_name="slug", value=obj.slug)
            )
            for field in ("name", "description"):
                value = entry.get(field, "")
                if value:
                    pending_claims.append(
                        Claim(
                            content_type_id=ct_id,
                            object_id=obj.pk,
                            field_name=field,
                            value=value,
                        )
                    )

        if pending_claims:
            stats = self._assert_claims_split_descriptions(Series, pending_claims)
            self.stdout.write(
                f"  Claims: {stats['created']} created, {stats['unchanged']} unchanged"
            )

        # Create series-level credits from inline credit_refs.
        people_by_slug = {p.slug: p for p in Person.objects.all()}
        role_lookup = {r.slug: r for r in CreditRole.objects.all()}
        if not role_lookup:
            raise CommandError(
                "CreditRole table is empty — taxonomy must be ingested first."
            )

        credits_to_create = []
        credits_skipped = 0

        for entry in series_entries:
            series_obj = series_by_slug.get(entry["slug"])
            if series_obj is None:
                continue
            for ref in entry.get("credit_refs") or []:
                person_obj = people_by_slug.get(ref.get("person_slug"))
                if person_obj is None:
                    credits_skipped += 1
                    continue
                role_obj = role_lookup.get(ref.get("role", "").lower())
                if role_obj is None:
                    credits_skipped += 1
                    continue
                credits_to_create.append(
                    Credit(series=series_obj, person=person_obj, role=role_obj)
                )

        if credits_to_create:
            created_credits = bulk_create_validated(
                Credit, credits_to_create, ignore_conflicts=True
            )
            self.stdout.write(
                f"  Credits: {len(created_credits)} created, {credits_skipped} skipped"
            )

    # ------------------------------------------------------------------
    # Phase 7: Titles
    # ------------------------------------------------------------------

    def _ingest_titles(self):
        entries = self._load("title.json")
        if not entries:
            return

        with transaction.atomic():
            self._ingest_titles_body(entries)

    def _ingest_titles_body(self, entries):
        titles_by_opdb_id = {t.opdb_id: t for t in Title.objects.all()}
        titles_by_slug = {t.slug: t for t in Title.objects.all()}
        existing_slugs: set[str] = set(Title.objects.values_list("slug", flat=True))
        franchises_by_slug = {f.slug: f for f in Franchise.objects.all()}
        series_by_slug = {s.slug: s for s in Series.objects.all()}

        # Pass 1: create Titles that don't exist yet.
        new_titles: list[Title] = []
        for entry in entries:
            opdb_group_id = entry.get("opdb_group_id")
            slug = entry.get("slug")

            if opdb_group_id and opdb_group_id in titles_by_opdb_id:
                continue
            if slug and slug in titles_by_slug:
                continue

            slug = slug or generate_unique_slug(entry.get("name", ""), existing_slugs)
            opdb_id = opdb_group_id or None
            new_titles.append(
                Title(
                    opdb_id=opdb_id,
                    name=entry.get("name", ""),
                    slug=slug,
                    fandom_page_id=entry.get("fandom_page_id"),
                )
            )
            existing_slugs.add(slug)

        titles_created = len(new_titles)
        if new_titles:
            bulk_create_validated(Title, new_titles)

        # Re-fetch lookups after creation.
        titles_by_opdb_id = {t.opdb_id: t for t in Title.objects.all()}
        titles_by_slug = {t.slug: t for t in Title.objects.all()}

        # Pass 2 (collect): find each title, detect transforms — no claim building yet.
        collected: list[tuple[Title, dict]] = []
        pending_slugs: dict[int, str] = {}
        pending_fandom_updates: list[Title] = []
        skipped = 0

        for entry in entries:
            opdb_group_id = entry.get("opdb_group_id")
            slug = entry.get("slug")

            title = None
            if opdb_group_id:
                title = titles_by_opdb_id.get(opdb_group_id)
            if title is None and slug:
                title = titles_by_slug.get(slug)
            if title is None:
                skipped += 1
                continue

            # Slug override — direct write, not yet claim-controlled (see A1).
            if slug and title.slug != slug:
                pending_slugs[title.pk] = slug

            # Fandom page ID — direct write, not yet claim-controlled (see A1).
            fandom_page_id = entry.get("fandom_page_id")
            if fandom_page_id and title.fandom_page_id != fandom_page_id:
                title.fandom_page_id = fandom_page_id
                pending_fandom_updates.append(title)

            collected.append((title, entry))

        # Apply slug renames before building claims so claim values always
        # reference the final post-rename slug.  safe_slugs contains only
        # renames that were actually applied (conflicts are skipped).
        slug_set = 0
        safe_slugs: dict[int, str] = {}
        if pending_slugs:
            pks_being_renamed = set(pending_slugs.keys())
            desired_slugs = set(pending_slugs.values())
            conflicting = set(
                Title.objects.filter(slug__in=desired_slugs)
                .exclude(pk__in=pks_being_renamed)
                .values_list("slug", flat=True)
            )
            safe_slugs = {
                pk: slug
                for pk, slug in pending_slugs.items()
                if slug not in conflicting
            }
            for slug in conflicting:
                logger.warning("Slug %r already taken — skipping rename", slug)

            if safe_slugs:
                from django.utils import timezone

                now = timezone.now()
                for pk in safe_slugs:
                    Title.objects.filter(pk=pk).update(
                        slug=f"_tmp_{pk}", updated_at=now
                    )
                for pk, slug in safe_slugs.items():
                    Title.objects.filter(pk=pk).update(slug=slug)
                slug_set = len(safe_slugs)

        # Batch fandom_page_id updates.
        if pending_fandom_updates:
            Title.objects.bulk_update(pending_fandom_updates, ["fandom_page_id"])

        # Pass 3 (assert): build and assert all claims against stable post-rename state.
        membership_set = 0
        pending_claims: list[Claim] = []
        touched_ids: set[int] = set()

        for title, entry in collected:
            # final_slug is the slug that now exists in the DB for this title.
            final_slug = safe_slugs.get(title.pk, title.slug)

            touched_ids.add(title.pk)
            pending_claims.append(
                Claim.for_object(title, field_name="slug", value=final_slug)
            )

            opdb_id = entry.get("opdb_group_id")
            if opdb_id:
                pending_claims.append(
                    Claim.for_object(title, field_name="opdb_id", value=opdb_id)
                )

            fandom_page_id = entry.get("fandom_page_id")
            if fandom_page_id:
                touched_ids.add(title.pk)
                pending_claims.append(
                    Claim.for_object(
                        title, field_name="fandom_page_id", value=fandom_page_id
                    )
                )

            name = entry.get("name")
            if name:
                touched_ids.add(title.pk)
                pending_claims.append(
                    Claim.for_object(title, field_name="name", value=name)
                )

            description = entry.get("description")
            if description:
                touched_ids.add(title.pk)
                pending_claims.append(
                    Claim.for_object(title, field_name="description", value=description)
                )

            franchise_slug = entry.get("franchise_slug")
            if franchise_slug:
                franchise = franchises_by_slug.get(franchise_slug)
                if franchise is None:
                    logger.warning(
                        "Franchise slug %r not found — skipping", franchise_slug
                    )
                else:
                    touched_ids.add(title.pk)
                    pending_claims.append(
                        Claim.for_object(
                            title, field_name="franchise", value=franchise_slug
                        )
                    )

            for abbr in entry.get("abbreviations", []):
                claim_key, value = build_relationship_claim(
                    "abbreviation", {"value": abbr}
                )
                touched_ids.add(title.pk)
                pending_claims.append(
                    Claim.for_object(
                        title,
                        field_name="abbreviation",
                        claim_key=claim_key,
                        value=value,
                    )
                )

            series_slug = entry.get("series_slug")
            if series_slug:
                series = series_by_slug.get(series_slug)
                if series is None:
                    logger.warning("Series slug %r not found — skipping", series_slug)
                else:
                    touched_ids.add(title.pk)
                    pending_claims.append(
                        Claim.for_object(title, field_name="series", value=series_slug)
                    )
                    membership_set += 1

        # Sweep franchise and series so removing the slug in a later
        # pindata export retracts the stale claim.
        claim_stats: dict = {}
        if pending_claims:
            sweep_kwargs = {}
            if touched_ids:
                sweep_kwargs["sweep_field"] = ["franchise", "series"]
                sweep_kwargs["authoritative_scope"] = make_authoritative_scope(
                    Title, touched_ids
                )
            claim_stats = self._assert_claims_split_descriptions(
                Title, pending_claims, **sweep_kwargs
            )

        # Resolve touched titles.
        if touched_ids:
            resolve_all_entities(Title, object_ids=touched_ids)
            resolve_all_title_abbreviations(model_ids=touched_ids)

        self.stdout.write(
            f"  Titles: {titles_created} created, {membership_set} series memberships, "
            f"{slug_set} slug overrides, {skipped} skipped"
        )
        if claim_stats:
            self.stdout.write(
                f"  Claims: {claim_stats.get('created', 0)} created, "
                f"{claim_stats.get('unchanged', 0)} unchanged"
            )

    # ------------------------------------------------------------------
    # Phase 8: Models
    # ------------------------------------------------------------------

    # Fields stored as claim values (claim field_name → raw frontmatter key).
    # Frontmatter uses _slug suffix for FK references; claim field names
    # match Django model field names (no suffix).
    MODEL_CLAIM_FIELDS = {
        "name": "name",
        "title": "title_slug",
        "corporate_entity": "corporate_entity_slug",
        "year": "year",
        "month": "month",
        "player_count": "player_count",
        "flipper_count": "flipper_count",
        "production_quantity": "production_quantity",
        "cabinet": "cabinet_slug",
        "display_type": "display_type_slug",
        "display_subtype": "display_subtype_slug",
        "technology_generation": "technology_generation_slug",
        "technology_subgeneration": "technology_subgeneration_slug",
        "system": "system_slug",
        "game_format": "game_format_slug",
        "description": "description",
        "ipdb_id": "ipdb_id",
        "opdb_id": "opdb_id",
        "converted_from": "converted_from",
        "variant_of": "variant_of",
        "remake_of": "remake_of",
    }

    def _ingest_models(self):
        entries = self._load("model.json")
        if not entries:
            return

        source = self.pinbase_source
        ct_id = ContentType.objects.get_for_model(MachineModel).pk

        by_opdb_id: dict[str, MachineModel] = {
            opdb_id: mm
            for mm in MachineModel.objects.filter(opdb_id__isnull=False)
            if (opdb_id := mm.opdb_id) is not None
        }
        by_ipdb_id: dict[int, MachineModel] = {
            ipdb_id: mm
            for mm in MachineModel.objects.filter(ipdb_id__isnull=False)
            if (ipdb_id := mm.ipdb_id) is not None
        }
        existing_slugs: set[str] = set(
            MachineModel.objects.values_list("slug", flat=True)
        )

        by_slug: dict[str, MachineModel] = {
            mm.slug: mm for mm in MachineModel.objects.all()
        }

        # Titles are required at construction time (NOT NULL FK). Resolve each
        # entry's title_slug against the Titles ingested in Phase 7.
        titles_by_slug: dict[str, Title] = {t.slug: t for t in Title.objects.all()}

        # Pass 1: match or create MachineModels for every entry.
        new_models: list[MachineModel] = []
        models_needing_update: list[MachineModel] = []
        # Map each entry index → MachineModel for pass 2.
        entry_models: list[MachineModel | None] = []

        for entry in entries:
            opdb_id = entry.get("opdb_id")
            ipdb_id = entry.get("ipdb_id")
            slug = entry.get("slug")

            # Try to match an existing model.
            mm = None
            if opdb_id:
                mm = by_opdb_id.get(opdb_id)
            if mm is None and ipdb_id:
                mm = by_ipdb_id.get(ipdb_id)
            if mm is None and slug:
                mm = by_slug.get(slug)

            if mm:
                # Backfill external IDs if missing.
                needs_update = False
                if opdb_id and mm.opdb_id is None and opdb_id not in by_opdb_id:
                    mm.opdb_id = opdb_id
                    by_opdb_id[opdb_id] = mm
                    needs_update = True
                if ipdb_id and mm.ipdb_id is None and ipdb_id not in by_ipdb_id:
                    mm.ipdb_id = ipdb_id
                    by_ipdb_id[ipdb_id] = mm
                    needs_update = True
                if needs_update:
                    models_needing_update.append(mm)
                entry_models.append(mm)
            else:
                # Create new model.
                title_slug = entry.get("title_slug")
                title_obj = titles_by_slug.get(title_slug) if title_slug else None
                if title_obj is None:
                    raise CommandError(
                        f"model.json entry slug={entry.get('slug')!r} "
                        f"name={entry.get('name')!r}: "
                        f"title_slug={title_slug!r} is missing or does not "
                        f"match any existing Title."
                    )
                slug = slug or generate_unique_slug(
                    entry.get("name", ""), existing_slugs
                )
                mm = MachineModel(
                    name=entry.get("name", ""),
                    slug=slug,
                    title=title_obj,
                    opdb_id=opdb_id,
                    ipdb_id=ipdb_id,
                )
                new_models.append(mm)
                existing_slugs.add(slug)
                if opdb_id:
                    by_opdb_id[opdb_id] = mm
                if ipdb_id:
                    by_ipdb_id[ipdb_id] = mm
                by_slug[slug] = mm
                entry_models.append(mm)

        models_created = len(new_models)
        if new_models:
            bulk_create_validated(MachineModel, new_models)
        if models_needing_update:
            MachineModel.objects.bulk_update(
                models_needing_update, ["opdb_id", "ipdb_id"]
            )
        # Re-fetch PKs after bulk_create (SQLite doesn't return them).
        if new_models:
            all_by_slug = {mm.slug: mm for mm in MachineModel.objects.all()}
            entry_models = [
                all_by_slug.get(mm.slug, mm) if mm else None for mm in entry_models
            ]

        # Pre-validate gameplay_feature_slugs and reward_type_slugs.
        valid_feature_slugs = frozenset(
            GameplayFeature.objects.values_list("slug", flat=True)
        )
        valid_reward_type_slugs = frozenset(
            RewardType.objects.values_list("slug", flat=True)
        )
        bad_feature_slugs: list[str] = []
        bad_reward_type_slugs: list[str] = []
        for entry in entries:
            for slug in entry.get("gameplay_feature_slugs") or []:
                if slug not in valid_feature_slugs:
                    bad_feature_slugs.append(f"{entry.get('slug', '?')}: {slug!r}")
            for slug in entry.get("reward_type_slugs") or []:
                if slug not in valid_reward_type_slugs:
                    bad_reward_type_slugs.append(f"{entry.get('slug', '?')}: {slug!r}")
        if bad_feature_slugs:
            raise CommandError(
                "model.json references nonexistent gameplay feature slugs:\n"
                + "\n".join(f"  {s}" for s in bad_feature_slugs)
            )
        if bad_reward_type_slugs:
            raise CommandError(
                "model.json references nonexistent reward type slugs:\n"
                + "\n".join(f"  {s}" for s in bad_reward_type_slugs)
            )

        # Build slug→PK lookup dicts for relationship claims.
        person_slug_to_pk = dict(Person.objects.values_list("slug", "pk"))
        role_slug_to_pk = dict(CreditRole.objects.values_list("slug", "pk"))
        tag_slug_to_pk = dict(Tag.objects.values_list("slug", "pk"))
        theme_slug_to_pk = dict(Theme.objects.values_list("slug", "pk"))
        feature_slug_to_pk = dict(GameplayFeature.objects.values_list("slug", "pk"))
        rt_slug_to_pk = dict(RewardType.objects.values_list("slug", "pk"))

        # Pass 2: assert scalar + relationship claims.
        pending_claims: list[Claim] = []
        credit_claims: list[Claim] = []
        tag_claims: list[Claim] = []
        theme_claims: list[Claim] = []
        gameplay_feature_claims: list[Claim] = []
        reward_type_claims: list[Claim] = []
        matched_pks: set[int] = set()
        matched = 0
        skipped = 0

        for entry, mm in zip(entries, entry_models, strict=True):
            if mm is None or not mm.pk:
                skipped += 1
                continue

            matched += 1
            matched_pks.add(mm.pk)

            pending_claims.append(
                Claim.for_object(mm, field_name="slug", value=mm.slug)
            )

            for claim_field, json_key in self.MODEL_CLAIM_FIELDS.items():
                value = entry.get(json_key)
                if value is not None and value != "":
                    pending_claims.append(
                        Claim(
                            content_type_id=ct_id,
                            object_id=mm.pk,
                            field_name=claim_field,
                            value=value,
                        )
                    )

            # Credit relationship claims.
            for ref in entry.get("credit_refs") or []:
                person_slug = ref.get("person_slug")
                role = _normalize_credit_role(ref.get("role", ""))
                person_pk = person_slug_to_pk.get(person_slug) if person_slug else None
                role_pk = role_slug_to_pk.get(role) if role else None
                if person_pk and role_pk:
                    claim_key, value = build_relationship_claim(
                        "credit", {"person": person_pk, "role": role_pk}
                    )
                    credit_claims.append(
                        Claim(
                            content_type_id=ct_id,
                            object_id=mm.pk,
                            field_name="credit",
                            claim_key=claim_key,
                            value=value,
                        )
                    )

            # Tag relationship claims.
            for tag_slug in entry.get("tag_slugs") or []:
                tag_pk = tag_slug_to_pk.get(tag_slug)
                if tag_pk is None:
                    continue
                claim_key, value = build_relationship_claim("tag", {"tag": tag_pk})
                tag_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=mm.pk,
                        field_name="tag",
                        claim_key=claim_key,
                        value=value,
                    )
                )

            # Theme relationship claims.
            for theme_slug in entry.get("theme_slugs") or []:
                theme_pk = theme_slug_to_pk.get(theme_slug)
                if theme_pk is None:
                    continue
                claim_key, value = build_relationship_claim(
                    "theme", {"theme": theme_pk}
                )
                theme_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=mm.pk,
                        field_name="theme",
                        claim_key=claim_key,
                        value=value,
                    )
                )

            # GameplayFeature relationship claims.
            for feature_slug in entry.get("gameplay_feature_slugs") or []:
                feature_pk = feature_slug_to_pk.get(feature_slug)
                if feature_pk is None:
                    continue
                claim_key, value = build_relationship_claim(
                    "gameplay_feature",
                    {"gameplay_feature": feature_pk},
                )
                gameplay_feature_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=mm.pk,
                        field_name="gameplay_feature",
                        claim_key=claim_key,
                        value=value,
                    )
                )

            # RewardType relationship claims.
            for rt_slug in entry.get("reward_type_slugs") or []:
                rt_pk = rt_slug_to_pk.get(rt_slug)
                if rt_pk is None:
                    continue
                claim_key, value = build_relationship_claim(
                    "reward_type", {"reward_type": rt_pk}
                )
                reward_type_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=mm.pk,
                        field_name="reward_type",
                        claim_key=claim_key,
                        value=value,
                    )
                )

        self.stdout.write(
            f"  Models: {models_created} created, {matched} matched, {skipped} skipped"
        )

        # Assert scalar claims.
        claim_stats = self._assert_claims_split_descriptions(
            MachineModel, pending_claims
        )
        self.stdout.write(
            f"  Claims: {claim_stats['unchanged']} unchanged, "
            f"{claim_stats['created']} created, "
            f"{claim_stats['superseded']} superseded"
        )

        # Assert credit and tag relationship claims with sweep.
        scope = make_authoritative_scope(MachineModel, matched_pks)
        if credit_claims or matched_pks:
            credit_stats = Claim.objects.bulk_assert_claims(
                source, credit_claims, sweep_field="credit", authoritative_scope=scope
            )
            self.stdout.write(
                f"  Credits: {credit_stats['created']} created, "
                f"{credit_stats['unchanged']} unchanged, "
                f"{credit_stats['swept']} swept"
            )
            resolve_all_credits(model_ids=matched_pks)

        if tag_claims or matched_pks:
            tag_stats = Claim.objects.bulk_assert_claims(
                source, tag_claims, sweep_field="tag", authoritative_scope=scope
            )
            self.stdout.write(
                f"  Tags: {tag_stats['created']} created, "
                f"{tag_stats['unchanged']} unchanged, "
                f"{tag_stats['swept']} swept"
            )
            resolve_all_tags(model_ids=matched_pks)

        if theme_claims or matched_pks:
            theme_stats = Claim.objects.bulk_assert_claims(
                source, theme_claims, sweep_field="theme", authoritative_scope=scope
            )
            self.stdout.write(
                f"  Themes: {theme_stats['created']} created, "
                f"{theme_stats['unchanged']} unchanged, "
                f"{theme_stats['swept']} swept"
            )
            resolve_all_themes(model_ids=matched_pks)

        if gameplay_feature_claims or matched_pks:
            gf_stats = Claim.objects.bulk_assert_claims(
                source,
                gameplay_feature_claims,
                sweep_field="gameplay_feature",
                authoritative_scope=scope,
            )
            self.stdout.write(
                f"  Features: {gf_stats['created']} created, "
                f"{gf_stats['unchanged']} unchanged, "
                f"{gf_stats['swept']} swept"
            )
            resolve_all_gameplay_features(model_ids=matched_pks)

        if reward_type_claims or matched_pks:
            rt_stats = Claim.objects.bulk_assert_claims(
                source,
                reward_type_claims,
                sweep_field="reward_type",
                authoritative_scope=scope,
            )
            self.stdout.write(
                f"  Reward types: {rt_stats['created']} created, "
                f"{rt_stats['unchanged']} unchanged, "
                f"{rt_stats['swept']} swept"
            )
            resolve_all_reward_types(model_ids=matched_pks)
