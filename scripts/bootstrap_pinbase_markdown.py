#!/usr/bin/env python3
"""Generate data/pinbase/**/*.md from current data/*.json files.

Phase 2 of the AllTheData migration: converts existing Pinbase-authored
JSON records into per-entity Markdown files with YAML frontmatter.

Usage:
    python scripts/bootstrap_pinbase_markdown.py
    python scripts/bootstrap_pinbase_markdown.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
PINBASE_DIR = DATA_DIR / "pinbase"


def _load_json(filename: str) -> list[dict]:
    path = DATA_DIR / filename
    if not path.exists():
        print(f"  WARNING: {path} not found, skipping", file=sys.stderr)
        return []
    return json.loads(path.read_text(encoding="utf-8"))


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
) -> Path:
    """Write a single Markdown record file."""
    out_dir = PINBASE_DIR / directory
    out_path = out_dir / f"{slug}.md"

    frontmatter = _clean_frontmatter(frontmatter)

    # Build YAML with consistent formatting.
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

    return out_path


# ---------------------------------------------------------------------------
# Entity generators
# ---------------------------------------------------------------------------


def generate_titles(*, dry_run: bool) -> int:
    titles = _load_json("titles.json")
    count = 0
    for t in titles:
        fm: dict = {"slug": t["slug"], "name": t["name"]}
        if t.get("opdb_group_id"):
            fm["opdb_group_id"] = t["opdb_group_id"]
        else:
            fm["opdb_group_id"] = None
        fm["franchise_slug"] = t.get("franchise_slug")
        fm["series_slug"] = t.get("series_slug")
        fm["abbreviations"] = t.get("abbreviations", [])
        # model_slugs will be populated from models after generation.
        fm["model_slugs"] = []
        fm["split_from_opdb_group"] = t.get("split_from_opdb_group")
        _write_record("titles", t["slug"], fm, dry_run=dry_run)
        count += 1
    return count


def generate_models(*, dry_run: bool) -> int:
    models = _load_json("models.json")
    count = 0
    for m in models:
        fm: dict = {
            "slug": m["slug"],
            "name": m["name"],
            "title_slug": m["title"],
        }
        fm["opdb_id"] = m.get("opdb_id")
        fm["ipdb_id"] = m.get("ipdb_id")
        fm["manufacturer_slug"] = None
        fm["year"] = None
        fm["month"] = None
        fm["player_count"] = None
        fm["flipper_count"] = None
        fm["production_quantity"] = None
        fm["display_type_slug"] = m.get("display_type")
        fm["display_subtype_slug"] = None
        fm["technology_generation_slug"] = None
        fm["technology_subgeneration_slug"] = None
        fm["system_slug"] = None
        fm["cabinet_slug"] = m.get("cabinet")
        fm["game_format_slug"] = None
        fm["variant_of"] = m.get("variant_of")
        fm["converted_from"] = m.get("converted_from")
        fm["is_conversion"] = m.get("is_conversion", False)
        fm["is_remake"] = m.get("is_remake", False)
        fm["remake_of"] = m.get("remake_of")
        fm["tag_slugs"] = []
        fm["credit_refs"] = []

        description = m.get("description", "")
        _write_record("models", m["slug"], fm, description, dry_run=dry_run)
        count += 1
    return count


def generate_people(*, dry_run: bool) -> int:
    people = _load_json("people.json")
    count = 0
    for p in people:
        fm: dict = {
            "slug": p["slug"],
            "name": p["name"],
            "aliases": p.get("aliases", []),
            "born": None,
            "died": None,
            "hometown": None,
        }
        _write_record("people", p["slug"], fm, dry_run=dry_run)
        count += 1
    return count


def generate_manufacturers(*, dry_run: bool) -> int:
    manufacturers = _load_json("manufacturers.json")
    count = 0
    for m in manufacturers:
        fm: dict = {
            "slug": m["slug"],
            "name": m["name"],
            "aliases": [],
        }
        description = m.get("description", "")
        _write_record("manufacturers", m["slug"], fm, description, dry_run=dry_run)
        count += 1
    return count


def generate_corporate_entities(*, dry_run: bool) -> int:
    from django.utils.text import slugify

    corporate_entities = _load_json("corporate_entities.json")
    existing_slugs: set[str] = set()
    count = 0
    for ce in corporate_entities:
        base_slug = slugify(ce["name"]) or "entity"
        slug = base_slug
        counter = 2
        while slug in existing_slugs:
            slug = f"{base_slug}-{counter}"
            counter += 1
        existing_slugs.add(slug)

        fm: dict = {
            "slug": slug,
            "name": ce["name"],
            "manufacturer_slug": ce["manufacturer_slug"],
            "year_start": ce.get("year_start"),
            "year_end": ce.get("year_end"),
            "headquarters_city": ce.get("headquarters_city"),
            "headquarters_state": ce.get("headquarters_state"),
            "headquarters_country": ce.get("headquarters_country"),
        }
        _write_record("corporate_entities", slug, fm, dry_run=dry_run)
        count += 1
    return count


def generate_series(*, dry_run: bool) -> int:
    series_list = _load_json("series.json")
    credits = _load_json("credits.json")

    # Group credits by series slug.
    credits_by_series: dict[str, list[dict]] = {}
    for c in credits:
        slug = c["series_slug"]
        credits_by_series.setdefault(slug, []).append(
            {"person_slug": c["person_slug"], "role": c["role"]}
        )

    count = 0
    for s in series_list:
        slug = s["slug"]
        fm: dict = {
            "slug": slug,
            "name": s["name"],
            "credit_refs": credits_by_series.get(slug, []),
        }
        description = s.get("description", "")
        _write_record("series", slug, fm, description, dry_run=dry_run)
        count += 1
    return count


def generate_systems(*, dry_run: bool) -> int:
    systems = _load_json("systems.json")
    count = 0
    for s in systems:
        fm: dict = {
            "slug": s["slug"],
            "name": s["name"],
            "manufacturer_slug": s.get("manufacturer"),
            "technology_subgeneration_slug": s.get("technology_subgeneration_slug"),
            "mpu_strings": s.get("mpu_strings", []),
        }
        description = s.get("description", "")
        _write_record("systems", s["slug"], fm, description, dry_run=dry_run)
        count += 1
    return count


def generate_franchises(*, dry_run: bool) -> int:
    franchises = _load_json("franchises.json")
    count = 0
    for f in franchises:
        fm: dict = {"slug": f["slug"], "name": f["name"]}
        description = f.get("description", "")
        _write_record("franchises", f["slug"], fm, description, dry_run=dry_run)
        count += 1
    return count


def _generate_taxonomy(
    json_file: str,
    directory: str,
    *,
    name_field: str = "name",
    extra_fields: dict[str, str] | None = None,
    dry_run: bool,
) -> int:
    """Generate taxonomy Markdown files from a JSON array.

    extra_fields maps frontmatter key → JSON source key for parent refs etc.
    """
    records = _load_json(json_file)
    count = 0
    for r in records:
        fm: dict = {
            "slug": r["slug"],
            "name": r.get(name_field, r.get("name", "")),
            "display_order": r.get("display_order", 0),
        }
        if extra_fields:
            for fm_key, json_key in extra_fields.items():
                fm[fm_key] = r.get(json_key)
        description = r.get("description", "")
        _write_record(directory, r["slug"], fm, description, dry_run=dry_run)
        count += 1
    return count


# ---------------------------------------------------------------------------
# Backfill: populate title model_slugs from generated models
# ---------------------------------------------------------------------------


def _backfill_title_model_slugs(*, dry_run: bool) -> int:
    """Read generated model files to populate model_slugs in title files."""
    if dry_run:
        return 0

    # Collect model→title mapping.
    models_dir = PINBASE_DIR / "models"
    titles_dir = PINBASE_DIR / "titles"
    if not models_dir.exists() or not titles_dir.exists():
        return 0

    title_models: dict[str, list[str]] = {}
    for md_file in sorted(models_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        end = text.find("\n---", 3)
        if end == -1:
            continue
        fm = yaml.safe_load(text[3:end])
        if not isinstance(fm, dict):
            continue
        title_slug = fm.get("title_slug")
        model_slug = fm.get("slug")
        if title_slug and model_slug:
            title_models.setdefault(title_slug, []).append(model_slug)

    # Update title files.
    updated = 0
    for title_file in sorted(titles_dir.glob("*.md")):
        text = title_file.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        end = text.find("\n---", 3)
        if end == -1:
            continue
        fm = yaml.safe_load(text[3:end])
        if not isinstance(fm, dict):
            continue
        slug = fm.get("slug")
        if slug and slug in title_models:
            fm["model_slugs"] = sorted(title_models[slug])
            body = text[end + 4:].strip()
            fm_text = yaml.dump(
                fm,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                width=120,
            ).rstrip()
            content = f"---\n{fm_text}\n---\n"
            if body:
                content += f"\n{body}\n"
            title_file.write_text(content, encoding="utf-8")
            updated += 1

    return updated


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate data/pinbase/ Markdown files from data/*.json"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and count records without writing files",
    )
    args = parser.parse_args()
    dry_run = args.dry_run

    print("Generating Pinbase Markdown records from data/*.json...")
    if dry_run:
        print("  (dry run — no files will be written)\n")

    totals: dict[str, int] = {}

    # Taxonomy entities.
    totals["cabinets"] = _generate_taxonomy(
        "cabinets.json", "cabinets", dry_run=dry_run
    )
    totals["credit_roles"] = _generate_taxonomy(
        "credit_roles.json", "credit_roles", dry_run=dry_run
    )
    totals["display_types"] = _generate_taxonomy(
        "display_types.json",
        "display_types",
        name_field="title",
        dry_run=dry_run,
    )
    totals["display_subtypes"] = _generate_taxonomy(
        "display_subtypes.json",
        "display_subtypes",
        extra_fields={"display_type_slug": "display_type_slug"},
        dry_run=dry_run,
    )
    totals["game_formats"] = _generate_taxonomy(
        "game_formats.json", "game_formats", dry_run=dry_run
    )
    totals["gameplay_features"] = _generate_taxonomy(
        "gameplay_features.json", "gameplay_features", dry_run=dry_run
    )
    totals["tags"] = _generate_taxonomy("tags.json", "tags", dry_run=dry_run)
    totals["technology_generations"] = _generate_taxonomy(
        "technology_generations.json",
        "technology_generations",
        name_field="title",
        dry_run=dry_run,
    )
    totals["technology_subgenerations"] = _generate_taxonomy(
        "technology_subgenerations.json",
        "technology_subgenerations",
        extra_fields={"technology_generation_slug": "technology_generation_slug"},
        dry_run=dry_run,
    )

    # Primary entities.
    totals["franchises"] = generate_franchises(dry_run=dry_run)
    totals["people"] = generate_people(dry_run=dry_run)
    totals["manufacturers"] = generate_manufacturers(dry_run=dry_run)
    totals["corporate_entities"] = generate_corporate_entities(dry_run=dry_run)
    totals["series"] = generate_series(dry_run=dry_run)
    totals["systems"] = generate_systems(dry_run=dry_run)
    totals["titles"] = generate_titles(dry_run=dry_run)
    totals["models"] = generate_models(dry_run=dry_run)

    # Backfill title model_slugs from generated model files.
    backfilled = _backfill_title_model_slugs(dry_run=dry_run)

    total = sum(totals.values())
    print(f"\nGenerated {total} records:")
    for name, count in sorted(totals.items()):
        print(f"  {name}: {count}")
    if backfilled:
        print(f"\nBackfilled model_slugs on {backfilled} title files.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
