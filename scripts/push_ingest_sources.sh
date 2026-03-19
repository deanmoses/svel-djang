#!/bin/sh
# Push ingest source files to Cloudflare R2.
# Thin wrapper around the Django management command.
set -e

cd "$(git rev-parse --show-toplevel)"

# Load .env if present
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

exec uv run --directory backend python manage.py push_ingest_sources "$@"
