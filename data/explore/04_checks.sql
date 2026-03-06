-- 04_checks.sql — Contract assertions
-- Depends on: 03_catalog.sql
-- Aborts with non-zero exit code if any violations are found.

CREATE TEMP TABLE IF NOT EXISTS _violations (check_name VARCHAR, detail VARCHAR);
CREATE TEMP TABLE IF NOT EXISTS _warnings (check_name VARCHAR, cnt BIGINT);

------------------------------------------------------------
-- Hard failures (structural integrity)
------------------------------------------------------------

-- Duplicate model keys
INSERT INTO _violations
SELECT 'duplicate_model_key', k FROM (
  SELECT model_key(opdb_id, ipdb_id) AS k
  FROM catalog_models
  GROUP BY k HAVING count(*) > 1
);

-- Duplicate tier keys
INSERT INTO _violations
SELECT 'duplicate_tier_key', k FROM (
  SELECT model_key(opdb_id, ipdb_id) AS k
  FROM catalog_tiers
  GROUP BY k HAVING count(*) > 1
);

-- Orphan tier_productions: tier references a production slug that doesn't exist
INSERT INTO _violations
SELECT 'orphan_tier_production', tp.tier_opdb_id
FROM catalog_tier_productions AS tp
LEFT JOIN catalog_productions AS p
  ON tp.production_slug = p.slug
  AND tp.opdb_group_id = p.opdb_group_id
  AND tp.manufacturer = p.manufacturer
  AND tp.technology_generation_slug IS NOT DISTINCT FROM p.technology_generation_slug
WHERE p.slug IS NULL AND tp.production_slug IS NOT NULL;

------------------------------------------------------------
-- Soft warnings (data quality, not regressions)
------------------------------------------------------------

INSERT INTO _warnings
SELECT 'null_manufacturer', count(*)
FROM catalog_models
WHERE manufacturer IS NULL;

-- Print warnings
SELECT 'WARNING: ' || check_name || ' (' || cnt || ' rows)'
FROM _warnings
WHERE cnt > 0;

-- Fail loudly on hard violations only
SELECT CASE
  WHEN count(*) > 0
  THEN error(count(*) || ' contract violation(s) found. Run: SELECT * FROM _violations')
  ELSE 'All checks passed'
END FROM _violations;
