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

CREATE OR REPLACE VIEW catalog_titles AS
SELECT
  g.opdb_id AS opdb_group_id,
  g."name",
  g.shortname,
  g.description,
  t.slug AS title_slug,
  t.franchise_slug,
  t.series_slug
FROM opdb_groups AS g
LEFT JOIN pinbase_titles AS t ON g.opdb_id = t.opdb_group_id;

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
-- Platform view (OPDB-only, picks representative machine per group)
------------------------------------------------------------

CREATE OR REPLACE VIEW catalog_platforms AS
WITH
  non_alias AS (
    SELECT
      *,
      manufacturer."name" AS mfr_name,
      manufacturer.full_name AS mfr_full_name
    FROM opdb_machines
    WHERE is_machine = CAST('t' AS BOOLEAN)
  ),
  ranked AS (
    SELECT
      *,
      row_number() OVER (
        PARTITION BY group_id, mfr_name
        ORDER BY physical_machine ASC, manufacture_date ASC, opdb_id ASC
      ) AS rn
    FROM non_alias
  )
SELECT
  group_id AS opdb_group_id,
  mfr_name AS manufacturer,
  mfr_full_name AS manufacturer_full_name,
  (group_id || '-' || machine_id) AS platform_opdb_id,
  "name",
  manufacture_date,
  "type",
  display,
  player_count,
  description
FROM ranked
WHERE rn = 1;

------------------------------------------------------------
-- Production views (override + auto-generated)
------------------------------------------------------------

CREATE OR REPLACE VIEW catalog_productions AS
WITH
  overridden_tiers AS (
    SELECT
      pt.opdb_id AS tier_opdb_id,
      pt.production_slug,
      pp.title_slug,
      pp.slug AS production_slug,
      pp."name" AS production_name,
      pp.description AS production_description
    FROM pinbase_tiers AS pt
    INNER JOIN pinbase_productions AS pp ON pt.production_slug = pp.slug
    WHERE pt.production_slug IS NOT NULL
  ),
  override_productions AS (
    SELECT
      ot.production_slug AS slug,
      ot.production_name AS "name",
      ot.production_description AS description,
      oe.opdb_group_id,
      oe.manufacturer,
      oe.technology_generation_slug,
      oe.manufacture_date,
      oe.opdb_id AS representative_opdb_id,
      CAST('t' AS BOOLEAN) AS is_override
    FROM overridden_tiers AS ot
    INNER JOIN opdb_tiers AS oe ON ot.tier_opdb_id = oe.opdb_id
  ),
  adjusted_base AS (
    SELECT
      t.opdb_group_id,
      t.manufacturer,
      t.technology_generation_slug,
      min(t.manufacture_date) AS manufacture_date,
      min(t.opdb_id) AS representative_opdb_id
    FROM opdb_tiers AS t
    LEFT JOIN overridden_tiers AS ot ON t.opdb_id = ot.tier_opdb_id
    WHERE ot.tier_opdb_id IS NULL
    GROUP BY t.opdb_group_id, t.manufacturer, t.technology_generation_slug
  ),
  auto_productions AS (
    SELECT
      CAST(NULL AS VARCHAR) AS slug,
      CAST(NULL AS VARCHAR) AS "name",
      CAST(NULL AS VARCHAR) AS description,
      ab.opdb_group_id,
      ab.manufacturer,
      ab.technology_generation_slug,
      ab.manufacture_date,
      ab.representative_opdb_id,
      CAST('f' AS BOOLEAN) AS is_override
    FROM adjusted_base AS ab
  )
(SELECT * FROM auto_productions)
UNION ALL
(SELECT * FROM override_productions);

CREATE OR REPLACE VIEW catalog_tier_productions AS
WITH
  overridden_tiers AS (
    SELECT pt.opdb_id AS tier_opdb_id, pt.production_slug
    FROM pinbase_tiers AS pt
    WHERE pt.production_slug IS NOT NULL
  )
(SELECT
  t.opdb_id AS tier_opdb_id,
  p.slug AS production_slug,
  p.opdb_group_id,
  p.manufacturer,
  p.technology_generation_slug,
  p.is_override
FROM opdb_tiers AS t
INNER JOIN overridden_tiers AS ot ON t.opdb_id = ot.tier_opdb_id
INNER JOIN catalog_productions AS p
  ON ot.production_slug = p.slug AND p.is_override = CAST('t' AS BOOLEAN))
UNION ALL
(SELECT
  t.opdb_id AS tier_opdb_id,
  p.slug AS production_slug,
  p.opdb_group_id,
  p.manufacturer,
  p.technology_generation_slug,
  p.is_override
FROM opdb_tiers AS t
LEFT JOIN overridden_tiers AS ot ON t.opdb_id = ot.tier_opdb_id
INNER JOIN catalog_productions AS p
  ON t.opdb_group_id = p.opdb_group_id
  AND t.manufacturer = p.manufacturer
  AND t.technology_generation_slug IS NOT DISTINCT FROM p.technology_generation_slug
  AND p.is_override = CAST('f' AS BOOLEAN)
WHERE ot.tier_opdb_id IS NULL);

------------------------------------------------------------
-- Thin wrappers on unified merge views
------------------------------------------------------------

CREATE OR REPLACE VIEW catalog_models AS
SELECT * FROM unified_models;

CREATE OR REPLACE VIEW catalog_tiers AS
SELECT * FROM unified_tiers;

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
  count(DISTINCT model_key(cm.opdb_id, cm.ipdb_id)) AS model_count
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
  count(DISTINCT model_key(cm.opdb_id, cm.ipdb_id)) AS model_count
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
  count(DISTINCT model_key(cm.opdb_id, cm.ipdb_id)) AS model_count
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
-- Conversions
------------------------------------------------------------

CREATE OR REPLACE VIEW catalog_conversions AS
SELECT
  pc.converted_opdb_id,
  pc.converted_name,
  cm_conv.manufacturer AS converted_manufacturer,
  cm_conv.manufacture_date AS converted_date,
  pc.source_opdb_id,
  pc.source_name,
  cm_src.manufacturer AS source_manufacturer,
  cm_src.manufacture_date AS source_date
FROM pinbase_conversions AS pc
LEFT JOIN catalog_models AS cm_conv ON pc.converted_opdb_id = cm_conv.opdb_id
LEFT JOIN catalog_models AS cm_src ON pc.source_opdb_id = cm_src.opdb_id;
