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
from collections import defaultdict
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError

from apps.catalog.claims import build_relationship_claim, make_authoritative_scope
from apps.catalog.ingestion.bulk_utils import generate_unique_slug
from apps.catalog.models import (
    Address,
    Cabinet,
    CorporateEntity,
    Credit,
    CreditRole,
    DisplaySubtype,
    DisplayType,
    Franchise,
    GameFormat,
    GameplayFeature,
    MachineModel,
    Manufacturer,
    Person,
    PersonAlias,
    Series,
    System,
    Tag,
    TechnologyGeneration,
    TechnologySubgeneration,
    Theme,
    Title,
)
from apps.catalog.resolve import (
    MANUFACTURER_DIRECT_FIELDS,
    TITLE_DIRECT_FIELDS,
    _resolve_bulk,
    resolve_all_credits,
    resolve_all_tags,
    resolve_all_title_abbreviations,
    resolve_corporate_entity,
)
from apps.provenance.models import Claim, Source

logger = logging.getLogger(__name__)

DEFAULT_EXPORT_DIR = Path(__file__).parents[5] / "data" / "explore" / "pinbase_export"

# Map authored credit role names to CreditRole slugs.
_CREDIT_ROLE_MAP: dict[str, str] = {
    "dots/animation": "animation",
}


def _normalize_credit_role(raw: str) -> str:
    """Normalize a credit role name to a CreditRole slug."""
    lower = raw.lower()
    return _CREDIT_ROLE_MAP.get(lower, lower)


# Taxonomy registry: (json_filename, model_class, has_display_order, parent_config)
# parent_config: (model_fk_field, parent_model, json_fk_key) or None
TAXONOMY_REGISTRY = [
    # Top-level (no parent FK) — order matters: parents before children.
    ("technology_generation.json", TechnologyGeneration, True, None),
    ("display_type.json", DisplayType, True, None),
    ("cabinet.json", Cabinet, True, None),
    ("game_format.json", GameFormat, True, None),
    ("gameplay_feature.json", GameplayFeature, True, None),
    ("tag.json", Tag, True, None),
    ("credit_role.json", CreditRole, True, None),
    ("franchise.json", Franchise, False, None),
    ("theme.json", Theme, False, None),
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
        self.titles_source, _ = Source.objects.update_or_create(
            slug="pinbase-titles",
            defaults={
                "name": "Pinbase Titles Seed",
                "source_type": "editorial",
                "priority": 300,
                "url": "",
            },
        )

        self._ingest_taxonomy()
        self._ingest_manufacturers()
        self._ingest_corporate_entities()
        self._ingest_systems()
        self._ingest_people()
        self._ingest_series()
        self._ingest_titles()
        self._ingest_models()

        self.stdout.write(self.style.SUCCESS("Pinbase ingestion complete."))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load(self, filename: str) -> list[dict]:
        path = self.export_dir / filename
        if not path.exists():
            self.stderr.write(f"  Skipping {filename} (not found)")
            return []
        with open(path) as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # Phase 1: Taxonomy
    # ------------------------------------------------------------------

    def _ingest_taxonomy(self):
        source = self.pinbase_source

        for (
            json_file,
            model_class,
            has_display_order,
            parent_config,
        ) in TAXONOMY_REGISTRY:
            data = self._load(json_file)
            if not data:
                continue

            ct = ContentType.objects.get_for_model(model_class)

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

            objs = model_class.objects.bulk_create(
                objs,
                update_conflicts=True,
                unique_fields=["slug"],
                update_fields=update_fields,
            )

            # Assert claims.
            pending_claims: list[Claim] = []
            for obj, entry in zip(objs, entries_used):
                pending_claims.append(
                    Claim(
                        content_type_id=ct.pk,
                        object_id=obj.pk,
                        field_name="name",
                        value=obj.name,
                    )
                )
                if has_display_order:
                    pending_claims.append(
                        Claim(
                            content_type_id=ct.pk,
                            object_id=obj.pk,
                            field_name="display_order",
                            value=obj.display_order,
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

            stats = Claim.objects.bulk_assert_claims(source, pending_claims)
            label = model_class.__name__
            self.stdout.write(
                f"  {label}: {len(data)} records — "
                f"{stats['created']} claims created, "
                f"{stats['unchanged']} unchanged"
            )

    # ------------------------------------------------------------------
    # Phase 2: Manufacturers
    # ------------------------------------------------------------------

    def _ingest_manufacturers(self):
        entries = self._load("manufacturer.json")
        if not entries:
            return

        source = self.editorial_source
        ct_id = ContentType.objects.get_for_model(Manufacturer).pk
        existing_slugs = set(Manufacturer.objects.values_list("slug", flat=True))

        objs = [Manufacturer(slug=e["slug"], name=e["name"]) for e in entries]
        objs = Manufacturer.objects.bulk_create(
            objs,
            update_conflicts=True,
            unique_fields=["slug"],
            update_fields=["name"],
        )

        created = sum(1 for o in objs if o.slug not in existing_slugs)
        self.stdout.write(
            f"  Manufacturers: {created} created, {len(objs) - created} updated"
        )

        pending_claims: list[Claim] = []
        for obj, entry in zip(objs, entries):
            pending_claims.append(
                Claim(
                    content_type_id=ct_id,
                    object_id=obj.pk,
                    field_name="name",
                    value=obj.name,
                )
            )
            description = entry.get("description", "")
            if description:
                pending_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=obj.pk,
                        field_name="description",
                        value=description,
                    )
                )

        if pending_claims:
            stats = Claim.objects.bulk_assert_claims(source, pending_claims)
            self.stdout.write(
                f"  Claims: {stats['unchanged']} unchanged, "
                f"{stats['created']} created, {stats['superseded']} superseded"
            )
            touched_ids = {o.pk for o in objs}
            _resolve_bulk(
                Manufacturer, MANUFACTURER_DIRECT_FIELDS, object_ids=touched_ids
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
        existing_keys = set(
            CorporateEntity.objects.values_list("manufacturer_id", "name")
        )

        objs = []
        valid_entries = []
        missing_mfr: list[str] = []
        seen_keys: set[tuple[int, str]] = set()

        for entry in entries:
            mfr_slug = entry["manufacturer_slug"]
            mfr = mfr_by_slug.get(mfr_slug)
            if mfr is None:
                missing_mfr.append(mfr_slug)
                logger.warning(
                    "Manufacturer slug %r not found for CE %r", mfr_slug, entry["name"]
                )
                continue

            # Skip duplicates by (manufacturer, name) — data quality issue.
            key = (mfr.pk, entry["name"])
            if key in seen_keys:
                logger.warning(
                    "Duplicate corporate entity %r for %r — skipping",
                    entry["name"],
                    mfr_slug,
                )
                continue
            seen_keys.add(key)

            objs.append(
                CorporateEntity(
                    manufacturer=mfr,
                    name=entry["name"],
                    slug=entry.get("slug", ""),
                    year_start=entry.get("year_start"),
                    year_end=entry.get("year_end"),
                )
            )
            valid_entries.append(entry)

        objs = CorporateEntity.objects.bulk_create(
            objs,
            update_conflicts=True,
            unique_fields=["slug"],
            update_fields=["name", "year_start", "year_end"],
        )

        created = sum(
            1 for o in objs if (o.manufacturer_id, o.name) not in existing_keys
        )
        self.stdout.write(
            f"  Corporate entities: {created} created, {len(objs) - created} updated"
        )

        # Create Address records.
        addresses_created = 0
        for obj, entry in zip(objs, valid_entries):
            city = entry.get("headquarters_city", "")
            state = entry.get("headquarters_state", "")
            country = entry.get("headquarters_country", "")
            if city or state or country:
                _, addr_created = Address.objects.get_or_create(
                    corporate_entity=obj, city=city, state=state, country=country
                )
                if addr_created:
                    addresses_created += 1

        if addresses_created:
            self.stdout.write(f"  Addresses: {addresses_created} created")
        if missing_mfr:
            self.stderr.write(
                f"  Warning: {len(missing_mfr)} missing manufacturer slug(s)"
            )

        # Assert claims and resolve.
        pending_claims: list[Claim] = []
        for obj in objs:
            pending_claims.append(
                Claim(
                    content_type_id=ct_id,
                    object_id=obj.pk,
                    field_name="name",
                    value=obj.name,
                )
            )
            if obj.year_start is not None:
                pending_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=obj.pk,
                        field_name="year_start",
                        value=obj.year_start,
                    )
                )
            if obj.year_end is not None:
                pending_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=obj.pk,
                        field_name="year_end",
                        value=obj.year_end,
                    )
                )

        if pending_claims:
            stats = Claim.objects.bulk_assert_claims(source, pending_claims)
            self.stdout.write(
                f"  Claims: {stats['unchanged']} unchanged, "
                f"{stats['created']} created, {stats['superseded']} superseded"
            )
            for ce in objs:
                resolve_corporate_entity(ce)

    # ------------------------------------------------------------------
    # Phase 4: Systems
    # ------------------------------------------------------------------

    def _ingest_systems(self):
        entries = self._load("system.json")
        if not entries:
            return

        source = self.pinbase_source
        ct_id = ContentType.objects.get_for_model(System).pk
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

        objs = System.objects.bulk_create(
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
        for obj, entry in zip(objs, entries):
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
            stats = Claim.objects.bulk_assert_claims(source, pending_claims)
            self.stdout.write(
                f"  Claims: {stats['created']} created, {stats['unchanged']} unchanged"
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
        objs = Person.objects.bulk_create(
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
            stats = Claim.objects.bulk_assert_claims(source, pending_claims)
            self.stdout.write(
                f"  Claims: {stats['created']} created, {stats['unchanged']} unchanged"
            )

        # Sync PersonAlias rows.
        desired: dict[int, dict[str, str]] = {}
        for entry in entries:
            person = persons_by_slug.get(entry["slug"])
            if not person:
                continue
            aliases = entry.get("aliases", [])
            if aliases:
                desired[person.pk] = {a.lower(): a for a in aliases}

        all_person_pks = {p.pk for p in objs}
        existing_aliases = list(
            PersonAlias.objects.filter(person_id__in=all_person_pks).values_list(
                "pk", "person_id", "value"
            )
        )

        existing_by_person: dict[int, dict[str, int]] = {}
        for pk, person_id, value in existing_aliases:
            existing_by_person.setdefault(person_id, {})[value.lower()] = pk

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

        if stale_pks:
            PersonAlias.objects.filter(pk__in=stale_pks).delete()
        if to_create:
            PersonAlias.objects.bulk_create(to_create)

        self.stdout.write(
            f"  Aliases: {len(to_create)} created, {len(stale_pks)} deleted"
        )

    # ------------------------------------------------------------------
    # Phase 6: Series
    # ------------------------------------------------------------------

    def _ingest_series(self):
        series_entries = self._load("series.json")
        if not series_entries:
            return

        source = self.pinbase_source
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
        objs = Series.objects.bulk_create(
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
        for obj, entry in zip(objs, series_entries):
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
            stats = Claim.objects.bulk_assert_claims(source, pending_claims)
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
            created_credits = Credit.objects.bulk_create(
                credits_to_create, ignore_conflicts=True
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

        source = self.titles_source
        ct_id = ContentType.objects.get_for_model(Title).pk

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
            opdb_id = opdb_group_id or f"pinbase:{slug}"
            new_titles.append(
                Title(opdb_id=opdb_id, name=entry.get("name", ""), slug=slug)
            )
            existing_slugs.add(slug)

        titles_created = len(new_titles)
        if new_titles:
            Title.objects.bulk_create(new_titles)

        # Re-fetch lookups after creation.
        titles_by_opdb_id = {t.opdb_id: t for t in Title.objects.all()}
        titles_by_slug = {t.slug: t for t in Title.objects.all()}

        membership_set = slug_set = skipped = 0
        pending_claims: list[Claim] = []
        pending_slugs: dict[int, str] = {}
        series_memberships: dict[Series, list[Title]] = defaultdict(list)
        touched_ids: set[int] = set()

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

            # Slug override (direct write, not claim-controlled).
            if slug and title.slug != slug:
                pending_slugs[title.pk] = slug

            # Name claim.
            name = entry.get("name")
            if name:
                touched_ids.add(title.pk)
                pending_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=title.pk,
                        field_name="name",
                        value=name,
                    )
                )

            # Franchise claim.
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
                        Claim(
                            content_type_id=ct_id,
                            object_id=title.pk,
                            field_name="franchise",
                            value=franchise_slug,
                        )
                    )

            # Abbreviation claims.
            for abbr in entry.get("abbreviations", []):
                claim_key, value = build_relationship_claim(
                    "abbreviation", {"value": abbr}
                )
                touched_ids.add(title.pk)
                pending_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=title.pk,
                        field_name="abbreviation",
                        claim_key=claim_key,
                        value=value,
                    )
                )

            # Series membership (M2M, not claim-controlled).
            series_slug = entry.get("series_slug")
            if series_slug:
                series = series_by_slug.get(series_slug)
                if series is None:
                    logger.warning("Series slug %r not found — skipping", series_slug)
                else:
                    series_memberships[series].append(title)
                    membership_set += 1

        # Assert claims.
        claim_stats: dict = {}
        if pending_claims:
            claim_stats = Claim.objects.bulk_assert_claims(source, pending_claims)

        # Resolve touched titles.
        if touched_ids:
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

        # Two-pass slug rename.
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

        # Batch M2M adds per series.
        for series, titles in series_memberships.items():
            series.titles.add(*titles)

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
        "is_conversion": "is_conversion",
        "converted_from": "converted_from",
        "variant_of": "variant_of",
        "is_remake": "is_remake",
        "remake_of": "remake_of",
    }

    def _ingest_models(self):
        entries = self._load("model.json")
        if not entries:
            return

        source = self.pinbase_source
        ct_id = ContentType.objects.get_for_model(MachineModel).pk

        by_opdb_id: dict[str, MachineModel] = {
            mm.opdb_id: mm for mm in MachineModel.objects.filter(opdb_id__isnull=False)
        }
        by_ipdb_id: dict[int, MachineModel] = {
            mm.ipdb_id: mm for mm in MachineModel.objects.filter(ipdb_id__isnull=False)
        }
        existing_slugs: set[str] = set(
            MachineModel.objects.values_list("slug", flat=True)
        )

        by_slug: dict[str, MachineModel] = {
            mm.slug: mm for mm in MachineModel.objects.all()
        }

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
                slug = slug or generate_unique_slug(
                    entry.get("name", ""), existing_slugs
                )
                mm = MachineModel(
                    name=entry.get("name", ""),
                    slug=slug,
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
            MachineModel.objects.bulk_create(new_models)
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

        # Pass 2: assert scalar + relationship claims.
        pending_claims: list[Claim] = []
        credit_claims: list[Claim] = []
        tag_claims: list[Claim] = []
        matched_pks: set[int] = set()
        matched = 0
        skipped = 0

        for entry, mm in zip(entries, entry_models):
            if mm is None or not mm.pk:
                skipped += 1
                continue

            matched += 1
            matched_pks.add(mm.pk)

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
                if person_slug and role:
                    claim_key, value = build_relationship_claim(
                        "credit", {"person_slug": person_slug, "role": role}
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
                claim_key, value = build_relationship_claim(
                    "tag", {"tag_slug": tag_slug}
                )
                tag_claims.append(
                    Claim(
                        content_type_id=ct_id,
                        object_id=mm.pk,
                        field_name="tag",
                        claim_key=claim_key,
                        value=value,
                    )
                )

        self.stdout.write(
            f"  Models: {models_created} created, {matched} matched, {skipped} skipped"
        )

        # Assert scalar claims.
        claim_stats = Claim.objects.bulk_assert_claims(source, pending_claims)
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
            resolve_all_credits([], model_ids=matched_pks)

        if tag_claims or matched_pks:
            tag_stats = Claim.objects.bulk_assert_claims(
                source, tag_claims, sweep_field="tag", authoritative_scope=scope
            )
            self.stdout.write(
                f"  Tags: {tag_stats['created']} created, "
                f"{tag_stats['unchanged']} unchanged, "
                f"{tag_stats['swept']} swept"
            )
            resolve_all_tags([], model_ids=matched_pks)
