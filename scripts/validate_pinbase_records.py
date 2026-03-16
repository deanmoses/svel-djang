#!/usr/bin/env python3
"""Validate data/pinbase/**/*.md records against JSON schemas.

Checks:
- YAML frontmatter parses correctly
- Frontmatter validates against the entity's JSON schema
- Slug in frontmatter matches the filename
- Cross-entity reference integrity (model→title, title→model, etc.)

Usage:
    uv run python scripts/validate_pinbase_records.py
    uv run python scripts/validate_pinbase_records.py --quiet
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add backend to path so we can import the loader.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from apps.catalog.ingestion.pinbase_loader import (  # noqa: E402
    PinbaseRecord,
    iter_all,
)


def _collect_records(pinbase_dir: Path | None) -> list[PinbaseRecord]:
    """Collect all records, printing parse/validation warnings to stderr."""
    return list(iter_all(pinbase_dir=pinbase_dir, validate=True))


def _check_slug_filename_match(records: list[PinbaseRecord]) -> list[str]:
    """Check that each record's slug matches its filename."""
    errors = []
    for r in records:
        expected = r.file_path.stem
        if r.slug != expected:
            errors.append(
                f"{r.file_path}: slug '{r.slug}' does not match filename '{expected}'"
            )
    return errors


def _check_uniqueness(records: list[PinbaseRecord]) -> list[str]:
    """Check slug uniqueness within each entity type."""
    errors = []
    by_type: dict[str, dict[str, Path]] = {}
    for r in records:
        bucket = by_type.setdefault(r.entity_type, {})
        if r.slug in bucket:
            errors.append(
                f"Duplicate {r.entity_type} slug '{r.slug}': "
                f"{bucket[r.slug]} and {r.file_path}"
            )
        else:
            bucket[r.slug] = r.file_path
    return errors


def _check_opdb_id_uniqueness(records: list[PinbaseRecord]) -> list[str]:
    """Check OPDB IDs are unique across model files."""
    errors = []
    seen: dict[str, Path] = {}
    for r in records:
        if r.entity_type != "model":
            continue
        opdb_id = r.frontmatter.get("opdb_id")
        if opdb_id is None:
            continue
        if opdb_id in seen:
            errors.append(
                f"Duplicate opdb_id '{opdb_id}': {seen[opdb_id]} and {r.file_path}"
            )
        else:
            seen[opdb_id] = r.file_path
    return errors


def _check_cross_references(records: list[PinbaseRecord]) -> list[str]:
    """Check that slug references resolve to existing records."""
    errors = []

    # Build lookup sets.
    slugs_by_type: dict[str, set[str]] = {}
    for r in records:
        slugs_by_type.setdefault(r.entity_type, set()).add(r.slug)

    # Reference checks.
    ref_checks: list[tuple[str, str, str]] = [
        # (source_entity_type, frontmatter_field, target_entity_type)
        ("model", "title_slug", "title"),
        ("model", "manufacturer_slug", "manufacturer"),
        ("model", "variant_of", "model"),
        ("model", "converted_from", "model"),
        ("model", "remake_of", "model"),
        ("model", "display_type_slug", "display_type"),
        ("model", "display_subtype_slug", "display_subtype"),
        ("model", "technology_generation_slug", "technology_generation"),
        ("model", "technology_subgeneration_slug", "technology_subgeneration"),
        ("model", "system_slug", "system"),
        ("model", "cabinet_slug", "cabinet"),
        ("model", "game_format_slug", "game_format"),
        ("title", "franchise_slug", "franchise"),
        ("title", "series_slug", "series"),
        ("system", "manufacturer_slug", "manufacturer"),
        ("system", "technology_subgeneration_slug", "technology_subgeneration"),
        ("corporate_entity", "manufacturer_slug", "manufacturer"),
        ("display_subtype", "display_type_slug", "display_type"),
        ("technology_subgeneration", "technology_generation_slug", "technology_generation"),
    ]

    for src_type, field, target_type in ref_checks:
        target_slugs = slugs_by_type.get(target_type, set())
        for r in records:
            if r.entity_type != src_type:
                continue
            value = r.frontmatter.get(field)
            if value is None:
                continue
            if value not in target_slugs:
                errors.append(
                    f"{r.file_path}: {field} '{value}' not found in {target_type}/"
                )

    # Check model tag_slugs → tag.
    tag_slugs = slugs_by_type.get("tag", set())
    for r in records:
        if r.entity_type != "model":
            continue
        for ts in r.frontmatter.get("tag_slugs", []):
            if ts not in tag_slugs:
                errors.append(f"{r.file_path}: tag_slug '{ts}' not found in tags/")

    # Check title model_slugs → model.
    model_slugs = slugs_by_type.get("model", set())
    for r in records:
        if r.entity_type != "title":
            continue
        for ms in r.frontmatter.get("model_slugs", []):
            if ms not in model_slugs:
                errors.append(
                    f"{r.file_path}: model_slug '{ms}' not found in models/"
                )

    # Check credit_refs person_slug → person.
    person_slugs = slugs_by_type.get("person", set())
    for r in records:
        if r.entity_type not in ("model", "series"):
            continue
        for cr in r.frontmatter.get("credit_refs", []):
            ps = cr.get("person_slug")
            if ps and ps not in person_slugs:
                errors.append(
                    f"{r.file_path}: credit person_slug '{ps}' not found in people/"
                )

    return errors


def _check_self_referential(records: list[PinbaseRecord]) -> list[str]:
    """Check for self-referential or chained variant_of relationships."""
    errors = []

    model_variant: dict[str, str | None] = {}
    for r in records:
        if r.entity_type != "model":
            continue
        model_variant[r.slug] = r.frontmatter.get("variant_of")

    for slug, variant_of in model_variant.items():
        if variant_of is None:
            continue
        if variant_of == slug:
            errors.append(f"models/{slug}.md: self-referential variant_of")
            continue
        # Check for chains (variant_of pointing to another variant).
        parent_variant = model_variant.get(variant_of)
        if parent_variant is not None:
            errors.append(
                f"models/{slug}.md: chained variant_of "
                f"('{slug}' → '{variant_of}' → '{parent_variant}')"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate data/pinbase/ Markdown records")
    parser.add_argument(
        "--pinbase-dir",
        type=Path,
        default=None,
        help="Override the data/pinbase/ directory path",
    )
    parser.add_argument("--quiet", action="store_true", help="Only print errors")
    args = parser.parse_args()

    records = _collect_records(args.pinbase_dir)

    if not args.quiet:
        # Summary by type.
        counts: dict[str, int] = {}
        for r in records:
            counts[r.entity_type] = counts.get(r.entity_type, 0) + 1
        print(f"Loaded {len(records)} records:")
        for etype, count in sorted(counts.items()):
            print(f"  {etype}: {count}")

    all_errors: list[str] = []
    all_errors.extend(_check_slug_filename_match(records))
    all_errors.extend(_check_uniqueness(records))
    all_errors.extend(_check_opdb_id_uniqueness(records))
    all_errors.extend(_check_cross_references(records))
    all_errors.extend(_check_self_referential(records))

    if all_errors:
        print(f"\n{len(all_errors)} error(s):", file=sys.stderr)
        for err in all_errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    if not args.quiet:
        print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
