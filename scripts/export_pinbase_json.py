#!/usr/bin/env python3
"""Export data/pinbase/**/*.md to JSON files for DuckDB consumption.

Reads all Markdown records via the shared loader and writes normalized
JSON arrays to data/explore/pinbase_export/. DuckDB views in 01_raw.sql
read these files alongside the existing data/*.json and dump1/ files.

Usage:
    python scripts/export_pinbase_json.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from apps.catalog.ingestion.pinbase_loader import iter_all  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPORT_DIR = REPO_ROOT / "data" / "explore" / "pinbase_export"


def main() -> int:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Group records by entity type.
    by_type: dict[str, list[dict]] = {}
    for r in iter_all(validate=False):
        entry = dict(r.frontmatter)
        if r.description:
            entry["description"] = r.description
        by_type.setdefault(r.entity_type, []).append(entry)

    for entity_type, records in sorted(by_type.items()):
        out_path = EXPORT_DIR / f"{entity_type}.json"
        out_path.write_text(
            json.dumps(records, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"  {entity_type}: {len(records)} records → {out_path.name}")

    total = sum(len(r) for r in by_type.values())
    print(f"\nExported {total} records across {len(by_type)} entity types.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
