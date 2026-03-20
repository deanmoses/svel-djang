# Data Ingestion

Pinbase is populated via Django management commands. The main pipeline
(`ingest_all`) seeds internal data then imports external sources. Optional
enrichment commands (Fandom, Wikidata) run separately.

## Data sources

Catalog data and external source files are maintained in the
[pindata](https://github.com/deanmoses/pindata) repo and published to
Cloudflare R2. Pinbase pulls them locally before running the ingest pipeline:

```bash
make pull-ingest   # download R2 → local data/ingest_sources/
```

## Pipeline overview

`ingest_all` runs these steps in order:

| Step                                | What it does                                    |
| ----------------------------------- | ----------------------------------------------- |
| `ingest_pinbase_taxonomy`           | Seeds themes, display types, and other taxonomy |
| `ingest_pinbase_manufacturers`      | Seeds Manufacturer records from curated JSON    |
| `ingest_pinbase_corporate_entities` | Seeds CorporateEntity records from curated JSON |
| `ingest_pinbase_systems`            | Seeds System records from curated JSON          |
| `ingest_ipdb`                       | Imports IPDB machine data                       |
| `ingest_opdb`                       | Imports OPDB machines, groups, and changelog    |
| `ingest_ipdb_titles`                | Creates Title records for IPDB-only machines    |
| `ingest_pinbase_series`             | Seeds Series and credits from curated JSON      |
| `ingest_pinbase_titles`             | Sets Title franchise and Series memberships     |
| `ingest_pinbase_signs`              | Imports museum sign copy from CSV               |
| `resolve_claims`                    | Re-resolves all catalog entities from claims    |

## External data sources

| Source           | File                        | Used by                |
| ---------------- | --------------------------- | ---------------------- |
| IPDB             | `ipdbdatabase.json`         | `ingest_ipdb`          |
| OPDB machines    | `opdb_export_machines.json` | `ingest_opdb`          |
| OPDB groups      | `opdb_export_groups.json`   | `ingest_opdb`          |
| OPDB changelog   | `opdb_changelog.json`       | `ingest_opdb`          |
| Museum sign copy | `machine_sign_copy.csv`     | `ingest_pinbase_signs` |

## Optional enrichment commands

These are **not** part of `ingest_all` and are run separately after the main
pipeline:

| Command                         | Source      | What it does                                   |
| ------------------------------- | ----------- | ---------------------------------------------- |
| `ingest_fandom`                 | Fandom wiki | Imports design credits, persons, manufacturers |
| `ingest_wikidata`               | Wikidata    | Enriches Person records via SPARQL             |
| `ingest_wikidata_manufacturers` | Wikidata    | Enriches Manufacturer records via SPARQL       |

All three support `--dump` / `--from-dump` flags to cache raw data locally and
replay without network calls.

**Fandom data files** (stored in R2 with the other ingest sources):

- `fandom_games.json`
- `fandom_persons.json`
- `fandom_manufacturers.json`

## Running locally

```bash
make pull-ingest   # download data from R2
make ingest        # run the full pipeline
```

Or as a single command:

```bash
cd backend
uv run python manage.py pull_and_ingest --dest ../data/ingest_sources
```

## Running against production (Railway)

### Prerequisites

- Railway CLI installed and logged in (`railway login`)
- Project linked (`railway link`)

### 1. Pull data and run ingest

```bash
railway ssh --service pinbase
.venv/bin/python manage.py pull_and_ingest
```

This pulls ingest sources from R2 (with SHA-256 verification, skipping
unchanged files), then runs the full `ingest_all` pipeline. Add `--dry-run`
to verify without committing changes.

### 2. Run optional enrichment (if needed)

```bash
.venv/bin/python manage.py ingest_fandom \
  --from-dump /tmp/ingest_sources/fandom_games.json \
  --from-dump-persons /tmp/ingest_sources/fandom_persons.json \
  --from-dump-manufacturers /tmp/ingest_sources/fandom_manufacturers.json

.venv/bin/python manage.py ingest_wikidata
.venv/bin/python manage.py ingest_wikidata_manufacturers
```

## Resetting the production database

Required when migrations have been collapsed (e.g. all apps reset to `0001`).

### 1. Wipe the database

In the Railway dashboard, open the **Postgres** service and use the query
runner, or connect via `railway connect Postgres` (requires `psql` locally):

```sql
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO public;
```

Alternatively, delete and recreate the Postgres service in the Railway
dashboard (you will need to re-link `DATABASE_URL` to the app service).

### 2. Merge and deploy

Merge the branch into `main`. Railway auto-deploys and the `preDeployCommand`
runs `manage.py migrate`, rebuilding the schema from scratch.

### 3. Re-create the superuser

Get the public `DATABASE_URL` from the Postgres service variables in the
Railway dashboard, then run locally:

```bash
cd backend
DJANGO_SUPERUSER_USERNAME=<user> \
DJANGO_SUPERUSER_PASSWORD=<pass> \
DJANGO_SUPERUSER_EMAIL="" \
DATABASE_URL=<public-url> \
uv run python manage.py createsuperuser --noinput
```

### 4. Re-run ingest

Follow the [Running against production](#running-against-production-railway)
steps above.
