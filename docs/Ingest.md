# Data Ingestion

Pinbase is populated from several external data sources via Django management commands.

## Data sources

| Source           | File                        | Command                |
| ---------------- | --------------------------- | ---------------------- |
| IPDB             | `ipdbdatabase.json`         | `ingest_ipdb`          |
| OPDB machines    | `opdb_export_machines.json` | `ingest_opdb`          |
| OPDB groups      | `opdb_export_groups.json`   | `ingest_opdb`          |
| OPDB changelog   | `opdb_changelog.json`       | `ingest_opdb`          |
| Museum sign copy | `machine_sign_copy.csv`     | `ingest_pinbase_signs` |

All source files live in `data/dump1/` and are **not committed** to the repo.
They are stored in a private GitHub Gist:
`https://gist.github.com/deanmoses/03aaee1bc83da6d7db8030d40538ed2d`

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
