# Data Ingestion

Pinbase is populated via Django management commands. The main pipeline
(`ingest_all`) seeds internal data then imports external sources. Optional
enrichment commands (Fandom, Wikidata) run separately.

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
| `generate_ipdb_titles`              | Creates Title records for IPDB-only machines    |
| `ingest_pinbase_series`             | Seeds Series and credits from curated JSON      |
| `ingest_pinbase_titles`             | Sets Title franchise and Series memberships     |
| `ingest_pinbase_signs`              | Imports museum sign copy from CSV               |
| `resolve_claims`                    | Re-resolves all catalog entities from claims    |

Internal seed data lives in `data/*.json`. External source files live in
`data/dump1/` and are **not committed** to the repo. They are stored in a
private GitHub Gist:
`https://gist.github.com/deanmoses/03aaee1bc83da6d7db8030d40538ed2d`

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

**Fandom data files** (stored in the same Gist):

- `fandom_games.json`
- `fandom_persons.json`
- `fandom_manufacturers.json`

## Running locally

With the data files present in `data/dump1/`:

```bash
cd backend
uv run python manage.py ingest_all
```

## Running against production (Railway)

### Prerequisites

- Railway CLI installed and logged in (`railway login`)
- Project linked (`railway link`)

### 1. SSH into the Railway service

```bash
railway ssh --service pinbase
```

### 2. Download the data files from the Gist

`curl` is not available in the container; use Python:

```bash
mkdir -p /tmp/dump1
python3 -c "
import urllib.request
base = 'https://gist.githubusercontent.com/deanmoses/03aaee1bc83da6d7db8030d40538ed2d/raw/'
files = [
    'ipdbdatabase.json',
    'opdb_export_machines.json',
    'opdb_export_groups.json',
    'opdb_changelog.json',
    'machine_sign_copy.csv',
    'fandom_games.json',
    'fandom_manufacturers.json',
    'fandom_persons.json',
]
[urllib.request.urlretrieve(base + f, '/tmp/dump1/' + f) or print('Downloaded', f) for f in files]
"
```

### 3. Run the ingest pipeline

```bash
uv run python manage.py ingest_all \
  --ipdb /tmp/dump1/ipdbdatabase.json \
  --opdb /tmp/dump1/opdb_export_machines.json \
  --opdb-groups /tmp/dump1/opdb_export_groups.json \
  --opdb-changelog /tmp/dump1/opdb_changelog.json \
  --csv /tmp/dump1/machine_sign_copy.csv
```

### 4. Run optional enrichment (if needed)

```bash
uv run python manage.py ingest_fandom \
  --from-dump /tmp/dump1/fandom_games.json \
  --from-dump-persons /tmp/dump1/fandom_persons.json \
  --from-dump-manufacturers /tmp/dump1/fandom_manufacturers.json

uv run python manage.py ingest_wikidata
uv run python manage.py ingest_wikidata_manufacturers
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
