#!/bin/sh
# Export pinbase Markdown to JSON, then rebuild data/explore/explore.duckdb.
# Usage: scripts/rebuild_explore.sh [--remote] [timeout_seconds]
# Default timeout: 20 seconds
#
# --remote  Read ingest sources from R2 instead of local files.
#           Requires R2_PUBLIC_URL in .env or environment.

set -e

REMOTE=""
if [ "$1" = "--remote" ]; then
  REMOTE=1
  shift
fi

TIMEOUT="${1:-20}"
DB="data/explore/explore.duckdb"
DIR="data/explore"

pkill -9 -f duckdb 2>/dev/null || true
rm -f "$DB" "$DB.wal"

if [ -n "$REMOTE" ]; then
  # Load .env for R2_PUBLIC_URL
  if [ -f .env ]; then
    set -a
    . ./.env
    set +a
  fi
  : "${R2_PUBLIC_URL:?Set R2_PUBLIC_URL in .env for --remote mode}"
  RAW_PREAMBLE="INSTALL httpfs; LOAD httpfs; SET VARIABLE ingest_base = '${R2_PUBLIC_URL}';"
  echo "Remote mode: reading ingest sources from $R2_PUBLIC_URL"
else
  RAW_PREAMBLE="SET VARIABLE ingest_base = 'data/ingest_sources';"
  echo "Exporting pinbase Markdown to JSON..."
  EXPORT_START=$(date +%s)
  uv run --directory backend python ../scripts/export_pinbase_json.py
  EXPORT_ELAPSED=$(( $(date +%s) - EXPORT_START ))
  echo "  export ${EXPORT_ELAPSED}s"
fi

echo "Rebuilding $DB (timeout: ${TIMEOUT}s)..."
TOTAL_START=$(date +%s)

for sql in "$DIR"/[0-9]*.sql; do
  LAYER=$(basename "$sql")
  LAYER_START=$(date +%s)

  # Prepend ingest_base variable (and httpfs for remote) to the raw layer
  if [ "$LAYER" = "02_raw.sql" ]; then
    if ! { echo "$RAW_PREAMBLE"; cat "$sql"; } | perl -e "alarm($TIMEOUT); exec @ARGV" duckdb "$DB"; then
      ELAPSED=$(( $(date +%s) - LAYER_START ))
      echo "  FAILED $LAYER after ${ELAPSED}s" >&2
      exit 1
    fi
  else
    if ! perl -e "alarm($TIMEOUT); exec @ARGV" duckdb "$DB" < "$sql"; then
      ELAPSED=$(( $(date +%s) - LAYER_START ))
      echo "  FAILED $LAYER after ${ELAPSED}s" >&2
      exit 1
    fi
  fi

  ELAPSED=$(( $(date +%s) - LAYER_START ))
  echo "  $LAYER ${ELAPSED}s"
done

TOTAL=$(( $(date +%s) - TOTAL_START ))
if [ -n "$REMOTE" ]; then
  echo "OK in ${TOTAL}s build (remote)"
else
  echo "OK in ${EXPORT_ELAPSED}s export + ${TOTAL}s build"
fi
