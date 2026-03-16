#!/usr/bin/env python3
"""Export the full catalog from Django SQLite to data/pinbase/**/*.md.

Phase 3 of the AllTheData migration: generates Markdown records for
models and titles not already covered by the Phase 2 bootstrap from
data/*.json.

Reads resolved fields from the Django runtime database. Preserves
existing Pinbase-authored files — only creates new files for records
that don't already have one.

Usage:
    cd backend && uv run python manage.py runscript scripts.export_full_catalog
    cd backend && uv run python ../scripts/export_full_catalog.py
    cd backend && uv run python ../scripts/export_full_catalog.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Django setup.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

import yaml  # noqa: E402

from apps.catalog.models import (  # noqa: E402
    Credit,
    MachineModel,
    Manufacturer,
    Person,
    Theme,
    Title,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PINBASE_DIR = REPO_ROOT / "data" / "pinbase"


def _clean_value(v):
    """Recursively clean a value, stripping nulls from nested dicts/lists."""
    if isinstance(v, dict):
        return _clean_dict(v)
    if isinstance(v, list):
        return [_clean_value(item) for item in v]
    return v


def _clean_dict(d: dict, *, keep: set[str] | None = None) -> dict:
    """Remove null values, empty lists/strings, and false booleans from a dict."""
    keep = keep or set()
    return {
        k: _clean_value(v)
        for k, v in d.items()
        if k in keep or (v is not None and v != [] and v != "" and v is not False)
    }


def _clean_frontmatter(fm: dict) -> dict:
    """Clean frontmatter, keeping slug and name always."""
    return _clean_dict(fm, keep={"slug", "name"})


def _write_record(
    directory: str,
    slug: str,
    frontmatter: dict,
    description: str = "",
    *,
    dry_run: bool = False,
) -> bool:
    """Write a Markdown record. Returns True if file was created (not already existing)."""
    out_dir = PINBASE_DIR / directory
    out_path = out_dir / f"{slug}.md"

    if out_path.exists():
        return False

    frontmatter = _clean_frontmatter(frontmatter)

    fm_text = yaml.dump(
        frontmatter,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=120,
    ).rstrip()

    content = f"---\n{fm_text}\n---\n"
    if description:
        content += f"\n{description.strip()}\n"

    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")

    return True


def export_models(*, dry_run: bool) -> tuple[int, int]:
    """Export all MachineModels not already in data/pinbase/models/."""
    # Prefetch related objects to avoid N+1.
    models = (
        MachineModel.objects.select_related(
            "title",
            "manufacturer",
            "variant_of",
            "converted_from",
            "technology_generation",
            "technology_subgeneration",
            "display_type",
            "display_subtype",
            "system",
            "cabinet",
            "game_format",
        )
        .prefetch_related("tags")
        .all()
    )

    # Prefetch credits for all models in one query.
    credits_by_model: dict[int, list[dict]] = {}
    for c in Credit.objects.filter(model__isnull=False).select_related("person", "role"):
        credits_by_model.setdefault(c.model_id, []).append(
            {"person_slug": c.person.slug, "role": c.role.name}
        )

    created = 0
    skipped = 0

    for m in models:
        fm: dict = {
            "slug": m.slug,
            "name": m.name,
            "title_slug": m.title.slug if m.title else None,
        }
        fm["opdb_id"] = m.opdb_id
        fm["ipdb_id"] = m.ipdb_id
        fm["manufacturer_slug"] = m.manufacturer.slug if m.manufacturer else None
        fm["year"] = m.year
        fm["month"] = m.month
        fm["player_count"] = m.player_count
        fm["flipper_count"] = m.flipper_count
        fm["production_quantity"] = m.production_quantity or None
        fm["display_type_slug"] = m.display_type.slug if m.display_type else None
        fm["display_subtype_slug"] = m.display_subtype.slug if m.display_subtype else None
        fm["technology_generation_slug"] = (
            m.technology_generation.slug if m.technology_generation else None
        )
        fm["technology_subgeneration_slug"] = (
            m.technology_subgeneration.slug if m.technology_subgeneration else None
        )
        fm["system_slug"] = m.system.slug if m.system else None
        fm["cabinet_slug"] = m.cabinet.slug if m.cabinet else None
        fm["game_format_slug"] = m.game_format.slug if m.game_format else None
        fm["variant_of"] = m.variant_of.slug if m.variant_of else None
        fm["converted_from"] = m.converted_from.slug if m.converted_from else None
        fm["is_conversion"] = m.is_conversion
        fm["is_remake"] = False  # Not yet tracked; default to false
        fm["remake_of"] = None
        fm["tag_slugs"] = sorted(m.tags.values_list("slug", flat=True))

        model_credits = credits_by_model.get(m.pk, [])
        # Sort credits by role then person for stable output.
        fm["credit_refs"] = sorted(model_credits, key=lambda c: (c["role"], c["person_slug"]))

        description = m.description or ""
        if _write_record("models", m.slug, fm, description, dry_run=dry_run):
            created += 1
        else:
            skipped += 1

    return created, skipped


def export_titles(*, dry_run: bool) -> tuple[int, int]:
    """Export all Titles not already in data/pinbase/titles/."""
    titles = Title.objects.select_related("franchise").prefetch_related("series").all()

    # Build model_slugs lookup.
    title_model_slugs: dict[int, list[str]] = {}
    for m in MachineModel.objects.filter(title__isnull=False).values_list("title_id", "slug"):
        title_model_slugs.setdefault(m[0], []).append(m[1])

    created = 0
    skipped = 0

    for t in titles:
        fm: dict = {
            "slug": t.slug,
            "name": t.name,
            "opdb_group_id": t.opdb_id if t.opdb_id else None,
        }
        fm["franchise_slug"] = t.franchise.slug if t.franchise else None

        # Series — take the first one (titles typically belong to at most one series).
        series_list = list(t.series.all())
        fm["series_slug"] = series_list[0].slug if series_list else None

        # Abbreviations from TitleAbbreviation.
        fm["abbreviations"] = sorted(
            t.abbreviations.values_list("value", flat=True)
        )

        fm["model_slugs"] = sorted(title_model_slugs.get(t.pk, []))
        fm["split_from_opdb_group"] = None

        description = t.description or ""
        if _write_record("titles", t.slug, fm, description, dry_run=dry_run):
            created += 1
        else:
            skipped += 1

    return created, skipped


def export_manufacturers(*, dry_run: bool) -> tuple[int, int]:
    """Export manufacturers not already in data/pinbase/manufacturers/."""
    manufacturers = Manufacturer.objects.all()
    created = 0
    skipped = 0

    for m in manufacturers:
        fm: dict = {
            "slug": m.slug,
            "name": m.name,
        }
        description = m.description or ""
        if _write_record("manufacturers", m.slug, fm, description, dry_run=dry_run):
            created += 1
        else:
            skipped += 1

    return created, skipped


def export_corporate_entities(*, dry_run: bool) -> tuple[int, int]:
    """Export corporate entities not already in data/pinbase/corporate_entities/."""
    from django.utils.text import slugify as django_slugify

    from apps.catalog.models import CorporateEntity

    entities = CorporateEntity.objects.select_related("manufacturer").prefetch_related("addresses").all()
    existing_slugs: set[str] = set()
    created = 0
    skipped = 0

    for ce in entities:
        base_slug = django_slugify(ce.name) or "entity"
        slug = base_slug
        counter = 2
        while slug in existing_slugs:
            slug = f"{base_slug}-{counter}"
            counter += 1
        existing_slugs.add(slug)

        fm: dict = {
            "slug": slug,
            "name": ce.name,
            "manufacturer_slug": ce.manufacturer.slug,
        }

        if ce.years_active:
            parts = ce.years_active.split("–")
            if len(parts) == 2:
                try:
                    fm["year_start"] = int(parts[0].strip())
                except ValueError:
                    pass
                try:
                    end = parts[1].strip()
                    if end:
                        fm["year_end"] = int(end)
                except ValueError:
                    pass

        addr = ce.addresses.first()
        if addr:
            if addr.city:
                fm["headquarters_city"] = addr.city
            if addr.state:
                fm["headquarters_state"] = addr.state
            if addr.country:
                fm["headquarters_country"] = addr.country

        if _write_record("corporate_entities", slug, fm, dry_run=dry_run):
            created += 1
        else:
            skipped += 1

    return created, skipped


def export_people(*, dry_run: bool) -> tuple[int, int]:
    """Export people not already in data/pinbase/people/."""
    people = Person.objects.prefetch_related("aliases").all()
    created = 0
    skipped = 0

    for p in people:
        fm: dict = {
            "slug": p.slug,
            "name": p.name,
            "aliases": sorted(p.aliases.values_list("value", flat=True)),
            "born": None,
            "died": None,
            "hometown": None,
        }
        # Fill in birth/death if available.
        if p.birth_year:
            fm["born"] = str(p.birth_year)
        if p.death_year:
            fm["died"] = str(p.death_year)
        if p.birth_place:
            fm["hometown"] = p.birth_place

        description = p.description or ""
        if _write_record("people", p.slug, fm, description, dry_run=dry_run):
            created += 1
        else:
            skipped += 1

    return created, skipped


def export_themes(*, dry_run: bool) -> tuple[int, int]:
    """Export themes not already in data/pinbase/themes/."""
    themes = Theme.objects.all()
    created = 0
    skipped = 0

    for t in themes:
        fm: dict = {"slug": t.slug, "name": t.name}
        description = t.description or ""
        if _write_record("themes", t.slug, fm, description, dry_run=dry_run):
            created += 1
        else:
            skipped += 1

    return created, skipped


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export full catalog from Django to data/pinbase/ Markdown"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    dry_run = args.dry_run

    print("Exporting full catalog from Django SQLite to data/pinbase/...")
    if dry_run:
        print("  (dry run — no files will be written)\n")

    models_created, models_skipped = export_models(dry_run=dry_run)
    print(f"  models: {models_created} created, {models_skipped} already existed")

    titles_created, titles_skipped = export_titles(dry_run=dry_run)
    print(f"  titles: {titles_created} created, {titles_skipped} already existed")

    mfr_created, mfr_skipped = export_manufacturers(dry_run=dry_run)
    print(f"  manufacturers: {mfr_created} created, {mfr_skipped} already existed")

    ce_created, ce_skipped = export_corporate_entities(dry_run=dry_run)
    print(f"  corporate_entities: {ce_created} created, {ce_skipped} already existed")

    people_created, people_skipped = export_people(dry_run=dry_run)
    print(f"  people: {people_created} created, {people_skipped} already existed")

    themes_created, themes_skipped = export_themes(dry_run=dry_run)
    print(f"  themes: {themes_created} created, {themes_skipped} already existed")

    total_created = models_created + titles_created + mfr_created + ce_created + people_created + themes_created
    total_skipped = models_skipped + titles_skipped + mfr_skipped + ce_skipped + people_skipped + themes_skipped
    print(f"\nTotal: {total_created} created, {total_skipped} already existed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
