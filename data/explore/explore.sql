-- View definitions for data/explore/explore.duckdb
-- Rebuild: rm -f data/explore/explore.duckdb && duckdb data/explore/explore.duckdb < data/explore/explore.sql

.read 'data/explore/01_raw.sql'
.read 'data/explore/02_staging.sql'
.read 'data/explore/03_catalog.sql'
.read 'data/explore/04_checks.sql'
