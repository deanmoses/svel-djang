"""Shared loader for data/pinbase/**/*.md Markdown records.

Parses YAML frontmatter and Markdown body from per-entity files.
Validates frontmatter against JSON schemas in data/schemas/pinbase/.
Exposes entity iterators for titles, models, people, manufacturers,
series, systems, franchises, themes, and taxonomy records.

This module is the single read path for:
- Django ingestion commands
- Validation checks
- Generation tools
- Export commands
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import yaml

logger = logging.getLogger(__name__)

# Resolve paths relative to the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PINBASE_DIR = _REPO_ROOT / "data" / "pinbase"
_SCHEMA_DIR = _REPO_ROOT / "data" / "schemas" / "pinbase"


@dataclass(frozen=True)
class PinbaseRecord:
    """A single parsed Markdown record."""

    entity_type: str
    slug: str
    frontmatter: dict
    description: str
    file_path: Path


# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------

_schema_cache: dict[str, dict] = {}


def _load_schema(schema_name: str) -> dict | None:
    """Load and cache a JSON schema by name."""
    if schema_name in _schema_cache:
        return _schema_cache[schema_name]
    schema_path = _SCHEMA_DIR / f"{schema_name}.schema.json"
    if not schema_path.exists():
        return None
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    _schema_cache[schema_name] = schema
    return schema


# ---------------------------------------------------------------------------
# Frontmatter validation
# ---------------------------------------------------------------------------

# Optional dependency: jsonschema is used if installed but not required
# at import time so the module can be loaded in lightweight contexts.
try:
    import jsonschema

    _HAS_JSONSCHEMA = True
except ModuleNotFoundError:  # pragma: no cover
    _HAS_JSONSCHEMA = False


def validate_frontmatter(
    frontmatter: dict, schema_name: str, file_path: Path
) -> list[str]:
    """Validate frontmatter against a JSON schema.

    Returns a list of error messages (empty if valid).
    """
    if not _HAS_JSONSCHEMA:
        return []

    schema = _load_schema(schema_name)
    if schema is None:
        return [f"No schema found: {schema_name}.schema.json"]

    errors: list[str] = []
    validator = jsonschema.Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(frontmatter), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"{file_path}: {path}: {error.message}")
    return errors


# ---------------------------------------------------------------------------
# Markdown parsing
# ---------------------------------------------------------------------------


def _parse_markdown_file(file_path: Path) -> tuple[dict, str] | None:
    """Parse a Markdown file with YAML frontmatter.

    Returns (frontmatter_dict, body_text) or None on parse failure.
    """
    text = file_path.read_text(encoding="utf-8")

    if not text.startswith("---"):
        logger.warning("No frontmatter delimiter in %s", file_path)
        return None

    # Find the closing --- delimiter.
    end = text.find("\n---", 3)
    if end == -1:
        logger.warning("Unclosed frontmatter in %s", file_path)
        return None

    frontmatter_text = text[3:end].strip()
    body = text[end + 4 :].strip()

    try:
        frontmatter = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as exc:
        logger.warning("YAML parse error in %s: %s", file_path, exc)
        return None

    if not isinstance(frontmatter, dict):
        logger.warning("Frontmatter is not a mapping in %s", file_path)
        return None

    return frontmatter, body


# ---------------------------------------------------------------------------
# Directory → schema mapping
# ---------------------------------------------------------------------------

# Maps directory names under data/pinbase/ to their schema file names.
_DIR_SCHEMA_MAP: dict[str, str] = {
    "titles": "title",
    "models": "model",
    "people": "person",
    "manufacturers": "manufacturer",
    "series": "series",
    "systems": "system",
    "franchises": "franchise",
    "themes": "theme",
    "corporate_entities": "corporate_entity",
    # Taxonomy directories that share the generic taxonomy schema:
    "cabinets": "taxonomy",
    "credit_roles": "taxonomy",
    "display_types": "taxonomy",
    "game_formats": "taxonomy",
    "gameplay_features": "taxonomy",
    "tags": "taxonomy",
    # Taxonomy directories with parent-child schemas:
    "display_subtypes": "display_subtype",
    "technology_generations": "technology_generation",
    "technology_subgenerations": "technology_subgeneration",
}

# The entity_type value for each directory.
_DIR_ENTITY_TYPE: dict[str, str] = {
    "titles": "title",
    "models": "model",
    "people": "person",
    "manufacturers": "manufacturer",
    "series": "series",
    "systems": "system",
    "franchises": "franchise",
    "themes": "theme",
    "corporate_entities": "corporate_entity",
    "cabinets": "cabinet",
    "credit_roles": "credit_role",
    "display_types": "display_type",
    "display_subtypes": "display_subtype",
    "game_formats": "game_format",
    "gameplay_features": "gameplay_feature",
    "tags": "tag",
    "technology_generations": "technology_generation",
    "technology_subgenerations": "technology_subgeneration",
}


# ---------------------------------------------------------------------------
# Entity iterators
# ---------------------------------------------------------------------------


def _iter_directory(
    dir_name: str,
    *,
    pinbase_dir: Path | None = None,
    validate: bool = True,
) -> Iterator[PinbaseRecord]:
    """Iterate over all .md files in a pinbase subdirectory.

    Yields PinbaseRecord instances. Logs warnings for parse/validation
    failures but does not raise.
    """
    base = pinbase_dir or _PINBASE_DIR
    directory = base / dir_name
    if not directory.is_dir():
        return

    schema_name = _DIR_SCHEMA_MAP.get(dir_name)
    entity_type = _DIR_ENTITY_TYPE.get(dir_name, dir_name)

    for md_file in sorted(directory.glob("*.md")):
        result = _parse_markdown_file(md_file)
        if result is None:
            continue

        frontmatter, body = result

        # Validate slug matches filename.
        expected_slug = md_file.stem
        actual_slug = frontmatter.get("slug")
        if actual_slug and actual_slug != expected_slug:
            logger.warning(
                "%s: slug %r does not match filename %r",
                md_file,
                actual_slug,
                expected_slug,
            )

        if validate and schema_name:
            errors = validate_frontmatter(frontmatter, schema_name, md_file)
            for err in errors:
                logger.warning(err)

        yield PinbaseRecord(
            entity_type=entity_type,
            slug=frontmatter.get("slug", expected_slug),
            frontmatter=frontmatter,
            description=body,
            file_path=md_file,
        )


def iter_titles(
    *, pinbase_dir: Path | None = None, validate: bool = True
) -> Iterator[PinbaseRecord]:
    """Iterate over all title records."""
    return _iter_directory("titles", pinbase_dir=pinbase_dir, validate=validate)


def iter_models(
    *, pinbase_dir: Path | None = None, validate: bool = True
) -> Iterator[PinbaseRecord]:
    """Iterate over all model records."""
    return _iter_directory("models", pinbase_dir=pinbase_dir, validate=validate)


def iter_people(
    *, pinbase_dir: Path | None = None, validate: bool = True
) -> Iterator[PinbaseRecord]:
    """Iterate over all person records."""
    return _iter_directory("people", pinbase_dir=pinbase_dir, validate=validate)


def iter_manufacturers(
    *, pinbase_dir: Path | None = None, validate: bool = True
) -> Iterator[PinbaseRecord]:
    """Iterate over all manufacturer records."""
    return _iter_directory("manufacturers", pinbase_dir=pinbase_dir, validate=validate)


def iter_corporate_entities(
    *, pinbase_dir: Path | None = None, validate: bool = True
) -> Iterator[PinbaseRecord]:
    """Iterate over all corporate entity records."""
    return _iter_directory(
        "corporate_entities", pinbase_dir=pinbase_dir, validate=validate
    )


def iter_series(
    *, pinbase_dir: Path | None = None, validate: bool = True
) -> Iterator[PinbaseRecord]:
    """Iterate over all series records."""
    return _iter_directory("series", pinbase_dir=pinbase_dir, validate=validate)


def iter_systems(
    *, pinbase_dir: Path | None = None, validate: bool = True
) -> Iterator[PinbaseRecord]:
    """Iterate over all system records."""
    return _iter_directory("systems", pinbase_dir=pinbase_dir, validate=validate)


def iter_franchises(
    *, pinbase_dir: Path | None = None, validate: bool = True
) -> Iterator[PinbaseRecord]:
    """Iterate over all franchise records."""
    return _iter_directory("franchises", pinbase_dir=pinbase_dir, validate=validate)


def iter_themes(
    *, pinbase_dir: Path | None = None, validate: bool = True
) -> Iterator[PinbaseRecord]:
    """Iterate over all theme records."""
    return _iter_directory("themes", pinbase_dir=pinbase_dir, validate=validate)


def iter_taxonomy(
    entity_dir: str,
    *,
    pinbase_dir: Path | None = None,
    validate: bool = True,
) -> Iterator[PinbaseRecord]:
    """Iterate over a specific taxonomy directory."""
    return _iter_directory(entity_dir, pinbase_dir=pinbase_dir, validate=validate)


# Convenience: all taxonomy directory names.
TAXONOMY_DIRS = [
    "cabinets",
    "credit_roles",
    "display_types",
    "display_subtypes",
    "game_formats",
    "gameplay_features",
    "tags",
    "technology_generations",
    "technology_subgenerations",
]


def iter_all_taxonomy(
    *, pinbase_dir: Path | None = None, validate: bool = True
) -> Iterator[PinbaseRecord]:
    """Iterate over all taxonomy records across all taxonomy directories."""
    for dir_name in TAXONOMY_DIRS:
        yield from _iter_directory(dir_name, pinbase_dir=pinbase_dir, validate=validate)


def iter_all(
    *, pinbase_dir: Path | None = None, validate: bool = True
) -> Iterator[PinbaseRecord]:
    """Iterate over every Pinbase record across all entity types."""
    for dir_name in _DIR_ENTITY_TYPE:
        yield from _iter_directory(dir_name, pinbase_dir=pinbase_dir, validate=validate)


# ---------------------------------------------------------------------------
# JSON-compatible adapters
# ---------------------------------------------------------------------------
# These functions return lists of dicts that match the field names
# used by the existing JSON-based ingest commands, allowing the
# commands to swap data sources with minimal changes.


def load_titles_as_dicts(*, pinbase_dir: Path | None = None) -> list[dict]:
    """Load title records as JSON-compatible dicts."""
    results = []
    for r in iter_titles(pinbase_dir=pinbase_dir, validate=False):
        d = dict(r.frontmatter)
        d["description"] = r.description
        results.append(d)
    return results


def load_models_as_dicts(*, pinbase_dir: Path | None = None) -> list[dict]:
    """Load model records as JSON-compatible dicts.

    Maps Markdown field names to the JSON field names expected by
    ingest_pinbase_models (e.g. title_slug → title).
    """
    results = []
    for r in iter_models(pinbase_dir=pinbase_dir, validate=False):
        fm = r.frontmatter
        d: dict = {
            "slug": fm.get("slug"),
            "name": fm.get("name"),
            "title": fm.get("title_slug"),
            "opdb_id": fm.get("opdb_id"),
            "ipdb_id": fm.get("ipdb_id"),
            "manufacturer": fm.get("manufacturer_slug"),
            "year": fm.get("year"),
            "month": fm.get("month"),
            "player_count": fm.get("player_count"),
            "flipper_count": fm.get("flipper_count"),
            "production_quantity": fm.get("production_quantity"),
            "display_type": fm.get("display_type_slug"),
            "display_subtype": fm.get("display_subtype_slug"),
            "technology_generation": fm.get("technology_generation_slug"),
            "technology_subgeneration": fm.get("technology_subgeneration_slug"),
            "system": fm.get("system_slug"),
            "cabinet": fm.get("cabinet_slug"),
            "game_format": fm.get("game_format_slug"),
            "variant_of": fm.get("variant_of"),
            "converted_from": fm.get("converted_from"),
            "is_conversion": fm.get("is_conversion", False),
            "is_remake": fm.get("is_remake", False),
            "remake_of": fm.get("remake_of"),
            "tag_slugs": fm.get("tag_slugs", []),
            "credit_refs": fm.get("credit_refs", []),
            "description": r.description,
        }
        results.append(d)
    return results


def load_people_as_dicts(*, pinbase_dir: Path | None = None) -> list[dict]:
    """Load person records as JSON-compatible dicts."""
    results = []
    for r in iter_people(pinbase_dir=pinbase_dir, validate=False):
        d = dict(r.frontmatter)
        d["description"] = r.description
        results.append(d)
    return results


def load_manufacturers_as_dicts(*, pinbase_dir: Path | None = None) -> list[dict]:
    """Load manufacturer records as JSON-compatible dicts."""
    results = []
    for r in iter_manufacturers(pinbase_dir=pinbase_dir, validate=False):
        d = dict(r.frontmatter)
        d["description"] = r.description
        results.append(d)
    return results


def load_corporate_entities_as_dicts(*, pinbase_dir: Path | None = None) -> list[dict]:
    """Load corporate entity records as JSON-compatible dicts.

    Returns dicts matching the corporate_entities.json format
    (with manufacturer_slug, name, year_start, year_end, etc.).
    """
    results = []
    for r in iter_corporate_entities(pinbase_dir=pinbase_dir, validate=False):
        fm = r.frontmatter
        d: dict = {
            "manufacturer_slug": fm.get("manufacturer_slug"),
            "name": fm.get("name"),
            "year_start": fm.get("year_start"),
            "year_end": fm.get("year_end"),
            "headquarters_city": fm.get("headquarters_city"),
            "headquarters_state": fm.get("headquarters_state"),
            "headquarters_country": fm.get("headquarters_country"),
        }
        results.append(d)
    return results


def load_series_as_dicts(
    *, pinbase_dir: Path | None = None
) -> tuple[list[dict], list[dict]]:
    """Load series records as JSON-compatible dicts.

    Returns (series_dicts, credit_dicts) to match the separate
    series.json + credits.json format.
    """
    series_list = []
    credit_list = []
    for r in iter_series(pinbase_dir=pinbase_dir, validate=False):
        fm = r.frontmatter
        series_list.append(
            {
                "slug": fm.get("slug"),
                "name": fm.get("name"),
                "description": r.description,
            }
        )
        for cr in fm.get("credit_refs", []):
            credit_list.append(
                {
                    "series_slug": fm.get("slug"),
                    "person_slug": cr.get("person_slug"),
                    "role": cr.get("role"),
                }
            )
    return series_list, credit_list


def load_systems_as_dicts(*, pinbase_dir: Path | None = None) -> list[dict]:
    """Load system records as JSON-compatible dicts.

    Maps manufacturer_slug → manufacturer to match systems.json format.
    """
    results = []
    for r in iter_systems(pinbase_dir=pinbase_dir, validate=False):
        fm = r.frontmatter
        d: dict = {
            "slug": fm.get("slug"),
            "name": fm.get("name"),
            "manufacturer": fm.get("manufacturer_slug"),
            "technology_subgeneration_slug": fm.get("technology_subgeneration_slug"),
            "mpu_strings": fm.get("mpu_strings", []),
            "description": r.description,
        }
        results.append(d)
    return results


def load_taxonomy_as_dicts(
    entity_dir: str, *, pinbase_dir: Path | None = None
) -> list[dict]:
    """Load taxonomy records as JSON-compatible dicts."""
    results = []
    for r in iter_taxonomy(entity_dir, pinbase_dir=pinbase_dir, validate=False):
        d = dict(r.frontmatter)
        d["description"] = r.description
        results.append(d)
    return results


def load_franchises_as_dicts(*, pinbase_dir: Path | None = None) -> list[dict]:
    """Load franchise records as JSON-compatible dicts."""
    results = []
    for r in iter_franchises(pinbase_dir=pinbase_dir, validate=False):
        d = dict(r.frontmatter)
        d["description"] = r.description
        results.append(d)
    return results
