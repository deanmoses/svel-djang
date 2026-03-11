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
  SELECT model_key AS k
  FROM catalog_models
  GROUP BY k HAVING count(*) > 1
);

-- Pinbase model references nonexistent opdb_id
INSERT INTO _violations
SELECT 'orphan_pinbase_model', pm.opdb_id
FROM pinbase_models AS pm
LEFT JOIN opdb_machines AS om ON pm.opdb_id = om.opdb_id
WHERE om.opdb_id IS NULL;

-- Pinbase variant_of references nonexistent slug
INSERT INTO _violations
SELECT 'orphan_variant_of', pm.slug || ' -> ' || pm.variant_of
FROM pinbase_models AS pm
WHERE pm.variant_of IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM pinbase_models AS pm2 WHERE pm2.slug = pm.variant_of
  );

-- Pinbase converted_from references nonexistent slug
INSERT INTO _violations
SELECT 'orphan_converted_from', pm.slug || ' -> ' || pm.converted_from
FROM pinbase_models AS pm
WHERE pm.converted_from IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM pinbase_models AS pm2 WHERE pm2.slug = pm.converted_from
  );

-- Pinbase title references nonexistent opdb_group_id
INSERT INTO _violations
SELECT 'orphan_pinbase_title', pt.opdb_group_id
FROM pinbase_titles AS pt
LEFT JOIN opdb_groups AS og ON pt.opdb_group_id = og.opdb_id
WHERE pt.opdb_group_id IS NOT NULL AND og.opdb_id IS NULL;

-- Pinbase title franchise_slug references nonexistent franchise
INSERT INTO _violations
SELECT 'orphan_franchise_slug', pt.slug || ' -> ' || pt.franchise_slug
FROM pinbase_titles AS pt
WHERE pt.franchise_slug IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM pinbase_franchises AS f WHERE f.slug = pt.franchise_slug
  );

-- Pinbase title series_slug references nonexistent series
INSERT INTO _violations
SELECT 'orphan_series_slug', pt.slug || ' -> ' || pt.series_slug
FROM pinbase_titles AS pt
WHERE pt.series_slug IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM pinbase_series AS s WHERE s.slug = pt.series_slug
  );

-- Duplicate slugs in pinbase_models
INSERT INTO _violations
SELECT 'duplicate_model_slug', slug
FROM pinbase_models
GROUP BY slug HAVING count(*) > 1;

-- Duplicate opdb_ids in pinbase_models
INSERT INTO _violations
SELECT 'duplicate_model_opdb_id', opdb_id
FROM pinbase_models
GROUP BY opdb_id HAVING count(*) > 1;

-- Self-referential variant_of
INSERT INTO _violations
SELECT 'self_variant_of', slug
FROM pinbase_models
WHERE variant_of = slug;

-- variant_of chains (A→B where B also has variant_of)
INSERT INTO _violations
SELECT 'chained_variant_of', a.slug || ' -> ' || a.variant_of || ' -> ' || b.variant_of
FROM pinbase_models AS a
JOIN pinbase_models AS b ON a.variant_of = b.slug
WHERE b.variant_of IS NOT NULL;

-- Pinbase model title references nonexistent title slug
INSERT INTO _violations
SELECT 'orphan_model_title', pm.slug || ' -> ' || pm.title
FROM pinbase_models AS pm
WHERE pm.title IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM pinbase_titles AS pt WHERE pt.slug = pm.title
  );

-- Duplicate slugs in pinbase_titles
INSERT INTO _violations
SELECT 'duplicate_title_slug', slug
FROM pinbase_titles
GROUP BY slug HAVING count(*) > 1;

-- Duplicate opdb_group_ids in pinbase_titles
INSERT INTO _violations
SELECT 'duplicate_title_opdb_group_id', opdb_group_id
FROM pinbase_titles
WHERE opdb_group_id IS NOT NULL
GROUP BY opdb_group_id HAVING count(*) > 1;

-- Pinbase model references a combo_label (physical_machine=0)
INSERT INTO _violations
SELECT 'combo_label_model', pm.slug || ' (' || pm.opdb_id || ')'
FROM pinbase_models AS pm
JOIN opdb_machines AS om ON pm.opdb_id = om.opdb_id
WHERE om.is_machine = 't' AND om.physical_machine = 0;

-- Self-referential variant_of in resolved catalog
-- (variant_of is a slug; resolve it to opdb_id to compare with model_key)
INSERT INTO _violations
SELECT 'catalog_self_variant_of', a.model_key
FROM catalog_models AS a
JOIN pinbase_models AS pm ON a.variant_of = pm.slug
JOIN catalog_models AS b ON pm.opdb_id = b.opdb_id
WHERE a.model_key = b.model_key;

-- Circular variant_of in resolved catalog (A→B and B→A)
INSERT INTO _violations
SELECT 'catalog_circular_variant_of', a.model_key || ' <-> ' || b.model_key
FROM catalog_models AS a
JOIN pinbase_models AS pm_a ON a.variant_of = pm_a.slug
JOIN catalog_models AS b ON pm_a.opdb_id = b.opdb_id
JOIN pinbase_models AS pm_b ON b.variant_of = pm_b.slug
JOIN catalog_models AS a2 ON pm_b.opdb_id = a2.opdb_id
WHERE a.model_key = a2.model_key
  AND a.model_key < b.model_key;

-- Chained variant_of in resolved catalog (A→B→C)
INSERT INTO _violations
SELECT 'catalog_chained_variant_of',
  a.model_key || ' -> ' || a.variant_of || ' -> ' || b.variant_of
FROM catalog_models AS a
JOIN pinbase_models AS pm_a ON a.variant_of = pm_a.slug
JOIN catalog_models AS b ON pm_a.opdb_id = b.opdb_id
WHERE b.variant_of IS NOT NULL
  AND b.variant_of <> a.variant_of;

------------------------------------------------------------
-- Soft warnings (data quality, not regressions)
------------------------------------------------------------

INSERT INTO _warnings
SELECT 'null_manufacturer', count(*)
FROM catalog_models
WHERE manufacturer IS NULL;

INSERT INTO _warnings
SELECT 'titles_without_pinbase_claims', count(*)
FROM catalog_titles
WHERE NOT has_pinbase_claims;

INSERT INTO _warnings
SELECT 'models_with_pinbase_claims', count(*)
FROM catalog_models
WHERE has_pinbase_claims;

-- Conversions missing converted_from (we know the source but haven't recorded it)
INSERT INTO _warnings
SELECT 'conversion_without_source', count(*)
FROM pinbase_models
WHERE is_conversion AND converted_from IS NULL;

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
