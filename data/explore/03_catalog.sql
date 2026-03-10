-- 03_catalog.sql — Final presentation views
-- Depends on: 01_raw.sql, 02_staging.sql

------------------------------------------------------------
-- Simple pass-throughs from pinbase curated data
------------------------------------------------------------

CREATE OR REPLACE VIEW catalog_cabinets AS
SELECT slug, "name", display_order, description
FROM pinbase_cabinets
ORDER BY display_order;

CREATE OR REPLACE VIEW catalog_corporate_entities AS
SELECT ce."name", ce.manufacturer_slug, ce.year_start, ce.year_end
FROM pinbase_corporate_entities AS ce;

CREATE OR REPLACE VIEW catalog_credits AS
SELECT
  pc.series_slug,
  ps."name" AS series_name,
  pc.person_slug,
  pp."name" AS person_name,
  pc."role"
FROM pinbase_credits AS pc
LEFT JOIN pinbase_series AS ps ON pc.series_slug = ps.slug
LEFT JOIN pinbase_people AS pp ON pc.person_slug = pp.slug;

CREATE OR REPLACE VIEW catalog_display_subtypes AS
SELECT
  ds.slug,
  ds."name",
  ds.display_order,
  ds.description,
  ds.display_type_slug,
  dt.title AS display_type_name
FROM pinbase_display_subtypes AS ds
LEFT JOIN pinbase_display_types AS dt ON ds.display_type_slug = dt.slug
ORDER BY ds.display_order;

CREATE OR REPLACE VIEW catalog_game_formats AS
SELECT slug, "name", display_order, description
FROM pinbase_game_formats
ORDER BY display_order;

CREATE OR REPLACE VIEW catalog_gameplay_features AS
SELECT slug, "name", display_order, description
FROM pinbase_gameplay_features
ORDER BY display_order;

CREATE OR REPLACE VIEW catalog_technology_subgenerations AS
SELECT
  tsg.slug,
  tsg."name",
  tsg.display_order,
  tsg.description,
  tsg.technology_generation_slug,
  tg.title AS technology_generation_name
FROM pinbase_technology_subgenerations AS tsg
LEFT JOIN pinbase_technology_generations AS tg
  ON tsg.technology_generation_slug = tg.slug
ORDER BY tsg.display_order;

------------------------------------------------------------
-- Views joining pinbase + external sources
------------------------------------------------------------

CREATE OR REPLACE VIEW catalog_manufacturers AS
SELECT
  p."name",
  p.slug,
  p.description,
  f.page_id AS fandom_page_id,
  f.wikitext AS fandom_wikitext
FROM pinbase_manufacturers AS p
LEFT JOIN fandom_manufacturers AS f ON p."name" = f.title;

-- catalog_titles: pinbase-primary, OPDB-enriched.
-- Mirrors Django's Title model after claims resolution.
CREATE OR REPLACE VIEW catalog_titles AS
SELECT * FROM merged_titles;

------------------------------------------------------------
-- Tag-related views
------------------------------------------------------------

CREATE OR REPLACE VIEW catalog_model_tags AS
SELECT
  om.opdb_id,
  rft.slug AS tag_slug
FROM opdb_machines AS om, unnest(om.features) AS t(f)
INNER JOIN ref_feature_tag AS rft ON f = rft.feature;

CREATE OR REPLACE VIEW catalog_tags AS
SELECT
  t.slug,
  t."name",
  t.display_order,
  t.description,
  count(DISTINCT mt.opdb_id) AS model_count
FROM pinbase_tags AS t
LEFT JOIN catalog_model_tags AS mt ON t.slug = mt.tag_slug
GROUP BY t.slug, t."name", t.display_order, t.description
ORDER BY t.display_order;

------------------------------------------------------------
-- Core catalog views (from merged staging layer)
------------------------------------------------------------

-- catalog_models: the resolved machine model view.
-- Mirrors Django's MachineModel after claims resolution.
CREATE OR REPLACE VIEW catalog_models AS
SELECT * FROM merged_models;

------------------------------------------------------------
-- IPDB cross-reference
------------------------------------------------------------

CREATE OR REPLACE VIEW catalog_ipdb_models AS
WITH
  opdb_link AS (
    (SELECT
      ipdb_id,
      opdb_id AS opdb_machine_id,
      group_id AS opdb_group_id,
      opdb_id AS tier_opdb_id
    FROM opdb_machines
    WHERE is_machine = 't' AND ipdb_id IS NOT NULL)
    UNION ALL
    (SELECT
      ipdb_id,
      opdb_id AS opdb_machine_id,
      group_id AS opdb_group_id,
      (group_id || '-' || machine_id) AS tier_opdb_id
    FROM opdb_machines
    WHERE is_alias = 't' AND ipdb_id IS NOT NULL)
  ),
  best_link AS (
    SELECT DISTINCT ON (ipdb_id) *
    FROM opdb_link
    ORDER BY ipdb_id, tier_opdb_id
  )
SELECT i.*, o.opdb_machine_id, o.opdb_group_id, o.tier_opdb_id
FROM ipdb_machines AS i
LEFT JOIN best_link AS o ON i.IpdbId = o.ipdb_id;

------------------------------------------------------------
-- File/media views
------------------------------------------------------------

CREATE OR REPLACE VIEW catalog_model_files AS
(SELECT
  cm.opdb_id,
  cm.ipdb_id,
  'image' AS category,
  oi.image_type,
  oi.is_primary,
  oi.image_title AS file_name,
  CAST(NULL AS VARCHAR) AS file_url,
  oi.url_small,
  oi.url_medium,
  oi.url_large,
  oi.small_width,
  oi.small_height,
  oi.medium_width,
  oi.medium_height,
  oi.large_width,
  oi.large_height,
  'opdb' AS "source"
FROM opdb_machine_images AS oi
INNER JOIN catalog_models AS cm ON oi.opdb_id = cm.opdb_id)
UNION ALL
(SELECT
  cm.opdb_id,
  cm.ipdb_id,
  imf.category,
  CAST(NULL AS VARCHAR) AS image_type,
  CAST(NULL AS BOOLEAN) AS is_primary,
  imf.file_name,
  imf.file_url,
  CAST(NULL AS VARCHAR) AS url_small,
  CAST(NULL AS VARCHAR) AS url_medium,
  CAST(NULL AS VARCHAR) AS url_large,
  CAST(NULL AS BIGINT) AS small_width,
  CAST(NULL AS BIGINT) AS small_height,
  CAST(NULL AS BIGINT) AS medium_width,
  CAST(NULL AS BIGINT) AS medium_height,
  CAST(NULL AS BIGINT) AS large_width,
  CAST(NULL AS BIGINT) AS large_height,
  'ipdb' AS "source"
FROM ipdb_machine_files AS imf
INNER JOIN catalog_models AS cm ON imf.ipdb_id = cm.ipdb_id);

------------------------------------------------------------
-- People (cross-source: IPDB + Fandom, with alias resolution)
------------------------------------------------------------

CREATE OR REPLACE VIEW catalog_people AS
WITH
  alias_map AS (
    SELECT unnest(aliases) AS alias_name, "name" AS canonical_name
    FROM pinbase_people
  ),
  ipdb_names AS (
    SELECT DISTINCT COALESCE(am.canonical_name, ip."name") AS "name"
    FROM ipdb_people AS ip
    LEFT JOIN alias_map AS am ON ip."name" = am.alias_name
  ),
  fandom_names AS (
    SELECT
      COALESCE(am.canonical_name, fp.title) AS "name",
      fp.page_id AS fandom_page_id,
      fp.wikitext AS fandom_wikitext
    FROM fandom_persons AS fp
    LEFT JOIN alias_map AS am ON fp.title = am.alias_name
  ),
  all_names AS (
    (SELECT "name" FROM ipdb_names)
    UNION
    (SELECT "name" FROM fandom_names)
  )
SELECT
  a."name",
  f.fandom_page_id,
  f.fandom_wikitext,
  (i."name" IS NOT NULL) AS in_ipdb,
  (f."name" IS NOT NULL) AS in_fandom
FROM all_names AS a
LEFT JOIN ipdb_names AS i ON a."name" = i."name"
LEFT JOIN fandom_names AS f ON a."name" = f."name";

------------------------------------------------------------
-- Aggregation views (counts using model_key macro)
------------------------------------------------------------

CREATE OR REPLACE VIEW catalog_franchises AS
SELECT
  f.slug,
  f."name",
  f.description,
  count(ct.opdb_group_id) AS title_count
FROM pinbase_franchises AS f
LEFT JOIN catalog_titles AS ct ON f.slug = ct.franchise_slug
GROUP BY f.slug, f."name", f.description
ORDER BY title_count DESC;

CREATE OR REPLACE VIEW catalog_series AS
SELECT
  s.slug,
  s."name",
  s.description,
  count(ct.opdb_group_id) AS title_count
FROM pinbase_series AS s
LEFT JOIN catalog_titles AS ct ON s.slug = ct.series_slug
GROUP BY s.slug, s."name", s.description
ORDER BY title_count DESC;

CREATE OR REPLACE VIEW catalog_systems AS
SELECT
  ps.slug,
  ps."name",
  ps.manufacturer_slug,
  count(DISTINCT cm.model_key) AS model_count
FROM pinbase_systems AS ps
LEFT JOIN catalog_models AS cm ON ps.slug = cm.system_slug
GROUP BY ps.slug, ps."name", ps.manufacturer_slug
ORDER BY model_count DESC;

CREATE OR REPLACE VIEW catalog_technology_generations AS
SELECT
  tg.slug,
  tg.title AS "name",
  tg.display_order,
  tg.description,
  count(DISTINCT cm.model_key) AS model_count
FROM pinbase_technology_generations AS tg
LEFT JOIN catalog_models AS cm ON tg.slug = cm.technology_generation_slug
GROUP BY tg.slug, tg.title, tg.display_order, tg.description
ORDER BY tg.display_order;

CREATE OR REPLACE VIEW catalog_display_types AS
SELECT
  dt.slug,
  dt.title AS "name",
  dt.display_order,
  dt.description,
  count(DISTINCT cm.model_key) AS model_count
FROM pinbase_display_types AS dt
LEFT JOIN catalog_models AS cm ON dt.slug = cm.display_type_slug
GROUP BY dt.slug, dt.title, dt.display_order, dt.description
ORDER BY dt.display_order;

------------------------------------------------------------
-- Themes (cross-source: IPDB themes + OPDB keywords)
------------------------------------------------------------

CREATE OR REPLACE VIEW catalog_themes AS
WITH
  ipdb_themes AS (
    SELECT DISTINCT Theme AS "name"
    FROM ipdb_machines
    WHERE Theme IS NOT NULL
  ),
  opdb_kw AS (
    SELECT DISTINCT keyword AS "name"
    FROM opdb_keywords
  ),
  all_themes AS (
    (SELECT "name", CAST('t' AS BOOLEAN) AS in_ipdb, CAST('f' AS BOOLEAN) AS in_opdb
     FROM ipdb_themes)
    UNION ALL
    (SELECT "name", CAST('f' AS BOOLEAN) AS in_ipdb, CAST('t' AS BOOLEAN) AS in_opdb
     FROM opdb_kw)
  )
SELECT "name", bool_or(in_ipdb) AS in_ipdb, bool_or(in_opdb) AS in_opdb
FROM all_themes
GROUP BY "name";

------------------------------------------------------------
-- Conversions (from pinbase editorial claims)
------------------------------------------------------------

CREATE OR REPLACE VIEW catalog_conversions AS
SELECT
  cm_conv.opdb_id AS converted_opdb_id,
  cm_conv."name" AS converted_name,
  cm_conv.manufacturer AS converted_manufacturer,
  cm_conv.manufacture_date AS converted_date,
  cm_conv.converted_from AS source_slug,
  cm_src.opdb_id AS source_opdb_id,
  cm_src."name" AS source_name,
  cm_src.manufacturer AS source_manufacturer,
  cm_src.manufacture_date AS source_date
FROM catalog_models AS cm_conv
LEFT JOIN pinbase_models AS pm_src ON cm_conv.converted_from = pm_src.slug
LEFT JOIN catalog_models AS cm_src ON pm_src.opdb_id = cm_src.opdb_id
WHERE cm_conv.is_conversion;

------------------------------------------------------------
-- Variant relationships (from pinbase editorial claims)
------------------------------------------------------------

CREATE OR REPLACE VIEW catalog_variants AS
SELECT
  cm.opdb_id AS variant_opdb_id,
  cm."name" AS variant_name,
  cm.manufacturer AS variant_manufacturer,
  cm.variant_of AS production_slug,
  pm_prod.opdb_id AS production_opdb_id,
  cm_prod."name" AS production_name,
  cm_prod.manufacturer AS production_manufacturer
FROM catalog_models AS cm
INNER JOIN pinbase_models AS pm_prod ON cm.variant_of = pm_prod.slug
LEFT JOIN catalog_models AS cm_prod ON pm_prod.opdb_id = cm_prod.opdb_id
WHERE cm.variant_of IS NOT NULL;
