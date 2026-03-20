#!/bin/sh
# Pull ingest source files from Cloudflare R2 to local data/ingest_sources/.
# Thin wrapper around the Django management command.
set -e

cd "$(git rev-parse --show-toplevel)"

DEST="$(pwd)/${1:-data/ingest_sources}"

# Load .env if present
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

exec uv run --directory backend python manage.py pull_ingest_sources --dest "$DEST"
