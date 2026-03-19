# DuckDB Explore Database

The best way to explore the data in Pinbase is via DuckDB.

The project contains a read-only DuckDB database for validating pinbase data, comparing it against
external sources (OPDB, IPDB, Fandom), and finding gaps.

DuckDB is purely an audit and exploration tool; Pinbase markdown is the source of truth.

## Using it

```bash
make explore                        # rebuild (runs JSON export + SQL layers)
duckdb data/explore/explore.duckdb  # query interactively
```

The database is a build artifact (gitignored). Rebuild whenever pinbase markdown
or source dumps change. The build **fails** if integrity checks don't pass —
query `SELECT * FROM _violations` for details.

## SQL layers

Files in `data/explore/` load in numeric order:

| File               | Purpose                                              |
| ------------------ | ---------------------------------------------------- |
| `01_reference.sql` | Hand-maintained reference tables, macros, exceptions |
| `02_raw.sql`       | Turn pinbase & external JSON into tables             |
| `03_staging.sql`   | Per-source normalization (no cross-source joins)     |
| `04_checks.sql`    | Integrity checks. Hard violations abort the build    |
| `05_compare.sql`   | Cross-source comparison: do sources agree?           |
| `06_gaps.sql`      | Gap analysis: what's missing from pinbase?           |
| `07_quality.sql`   | Slug quality, media audit, backfill proposals        |

## Remote data (Cloudflare R2)

Ingest source files are stored in Cloudflare R2 for access by cloud-based tools
and the Railway production environment.

```bash
make pull-ingest   # download R2 → local data/ingest_sources/
make push-ingest   # upload local data/ingest_sources/ → R2 (requires credentials)
```

### Rebuilding from R2

```bash
./scripts/rebuild_explore.sh --remote   # reads JSON from R2 instead of local files
```

### MotherDuck

To query against remote data in MotherDuck, override `ingest_base` before
loading the SQL layers:

```sql
INSTALL httpfs; LOAD httpfs;
SET VARIABLE ingest_base = 'https://pub-8f33ea1ac628450298edd0d3243ecf5a.r2.dev';
-- Then run 02_raw.sql etc. as usual
```

## Related scripts

- `scripts/apply_markdown_updates.py` — applies backfills to markdown files
- `scripts/generate_missing_ipdb_data.py` — creates markdown for missing IPDB entities
