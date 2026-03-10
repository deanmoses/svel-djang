-- 02_staging.sql — Source-specific transforms and cross-source merge logic
-- Depends on: 01_raw.sql

------------------------------------------------------------
-- OPDB-derived views
------------------------------------------------------------

-- opdb_machines: raw + technology/display slug lookups
CREATE OR REPLACE VIEW opdb_machines AS
SELECT
  r.*,
  tg.slug AS technology_generation_slug,
  dt.slug AS display_type_slug,
  CAST(NULL AS VARCHAR) AS system_slug
FROM opdb_machines_raw AS r
LEFT JOIN ref_opdb_technology_generation AS tg ON r."type" = tg.opdb_type
LEFT JOIN ref_opdb_display_type AS dt ON r.display = dt.opdb_display;

-- opdb_manufacturers: distinct manufacturers from OPDB
CREATE OR REPLACE VIEW opdb_manufacturers AS
SELECT DISTINCT
  manufacturer.manufacturer_id AS opdb_manufacturer_id,
  manufacturer."name" AS "name",
  manufacturer.full_name AS full_name
FROM opdb_machines
WHERE manufacturer IS NOT NULL
ORDER BY "name";

-- opdb_keywords: unnested keyword list per machine
CREATE OR REPLACE VIEW opdb_keywords AS
SELECT opdb_id, "name", unnest(keywords) AS keyword
FROM opdb_machines
WHERE len(keywords) > 0;

-- opdb_machine_images: flattened image metadata per machine
CREATE OR REPLACE VIEW opdb_machine_images AS
SELECT
  opdb_id,
  "name",
  img.title AS image_title,
  img."primary" AS is_primary,
  img."type" AS image_type,
  img.urls.small AS url_small,
  img.urls.medium AS url_medium,
  img.urls."large" AS url_large,
  img.sizes.small.width AS small_width,
  img.sizes.small.height AS small_height,
  img.sizes.medium.width AS medium_width,
  img.sizes.medium.height AS medium_height,
  img.sizes."large".width AS large_width,
  img.sizes."large".height AS large_height
FROM opdb_machines, unnest(images) AS t(img)
WHERE len(images) > 0;

------------------------------------------------------------
-- IPDB-derived views
------------------------------------------------------------

-- ipdb_machines: raw + technology generation + system slug lookups
CREATE OR REPLACE VIEW ipdb_machines AS
SELECT
  r.*,
  COALESCE(tg1.slug, tg2.slug) AS technology_generation_slug,
  CAST(NULL AS VARCHAR) AS display_type_slug,
  ps.slug AS system_slug
FROM ipdb_machines_raw AS r
LEFT JOIN ref_ipdb_technology_generation AS tg1
  ON r.TypeShortName = tg1.type_short_name AND tg1.type_short_name IS NOT NULL
LEFT JOIN ref_ipdb_technology_generation AS tg2
  ON r."Type" = tg2.type_full AND tg2.type_full IS NOT NULL
LEFT JOIN pinbase_systems AS ps
  ON list_contains(ps.mpu_strings, r.MPU);

-- ipdb_manufacturers: distinct manufacturer entries from IPDB
CREATE OR REPLACE VIEW ipdb_manufacturers AS
SELECT DISTINCT
  ManufacturerId AS ipdb_manufacturer_id,
  Manufacturer AS "name",
  ManufacturerShortName AS short_name
FROM ipdb_machines
WHERE Manufacturer IS NOT NULL
ORDER BY "name";

-- ipdb_people: credits unpivoted and split into individual names
CREATE OR REPLACE VIEW ipdb_people AS
WITH
  credits_unpivoted AS (
    SELECT IpdbId, Title, credit_role, credit_names
    FROM ipdb_machines
    UNPIVOT (
      credit_names FOR credit_role IN (
        'DesignBy', 'ArtBy', 'MusicBy', 'SoundBy',
        'SoftwareBy', 'MechanicsBy', 'DotsAnimationBy'
      )
    )
    WHERE credit_names IS NOT NULL
  ),
  split_names AS (
    SELECT
      IpdbId,
      Title,
      credit_role,
      main."trim"(unnest(string_split(credit_names, ','))) AS "name"
    FROM credits_unpivoted
  )
SELECT
  sn."name",
  rcr.role_name AS "role",
  sn.IpdbId,
  sn.Title AS machine_title
FROM split_names AS sn
JOIN ref_credit_role AS rcr ON sn.credit_role = rcr.column_name
WHERE sn."name" != '';

-- ipdb_machine_files: all file types from IPDB machines
CREATE OR REPLACE VIEW ipdb_machine_files AS
SELECT
  IpdbId AS ipdb_id,
  Title AS machine_name,
  f.Url AS file_url,
  f."Name" AS file_name,
  category
FROM ipdb_machines, (
  SELECT unnest(ImageFiles) AS f, 'image' AS category
  UNION ALL SELECT unnest(Documentation), 'documentation'
  UNION ALL SELECT unnest(Files), 'file'
  UNION ALL SELECT unnest(RuleSheetUrls), 'rule_sheet'
  UNION ALL SELECT unnest(ROMs), 'rom'
  UNION ALL SELECT unnest(ServiceBulletins), 'service_bulletin'
  UNION ALL SELECT unnest(MultimediaFiles), 'multimedia'
);

-- ipdb_manufacturer_resolution: maps each distinct IPDB Manufacturer string
-- to a resolved manufacturer slug.
-- Priority: 1) corporate entity lookup on parsed company name,
--           2) manufacturer name match on trade name,
--           3) manufacturer name match on company name.
-- Also parses headquarters location into city/state/country.
CREATE OR REPLACE VIEW ipdb_manufacturer_resolution AS
WITH
  parsed AS (
    SELECT DISTINCT
      Manufacturer AS raw_manufacturer,
      regexp_extract(Manufacturer, '\[Trade Name:\s*(.+?)\]', 1) AS trade_name,
      regexp_replace(
        regexp_replace(
          regexp_replace(
            regexp_replace(Manufacturer, '\s*\[Trade Name:.*?\]', ''),
            '\s*\(\d{4}.*?\)', ''),
          ',\s*of\s+.*$', ''),
        ',\s*$', '') AS company_name,
      regexp_extract(Manufacturer, ',\s*of\s+(.+?)(?:\s*\(\d{4}|\s*\[Trade|\s*$)', 1) AS location_raw
    FROM ipdb_machines
    WHERE Manufacturer IS NOT NULL
  ),
  ce_match AS (
    SELECT DISTINCT ON (p.raw_manufacturer)
      p.raw_manufacturer, p.company_name, p.trade_name, p.location_raw,
      ce.manufacturer_slug, 'corporate_entity' AS resolution_method,
      ce.headquarters_city AS ce_hq_city,
      ce.headquarters_state AS ce_hq_state,
      ce.headquarters_country AS ce_hq_country
    FROM parsed AS p
    INNER JOIN pinbase_corporate_entities AS ce
      ON lower(p.company_name) = lower(ce.name)
  ),
  unresolved_after_ce AS (
    SELECT * FROM parsed
    WHERE raw_manufacturer NOT IN (SELECT raw_manufacturer FROM ce_match)
  ),
  trade_match AS (
    SELECT DISTINCT ON (p.raw_manufacturer)
      p.raw_manufacturer, p.company_name, p.trade_name, p.location_raw,
      m.slug AS manufacturer_slug, 'trade_name' AS resolution_method
    FROM unresolved_after_ce AS p
    INNER JOIN pinbase_manufacturers AS m
      ON lower(p.trade_name) = lower(m.name)
    WHERE p.trade_name <> ''
  ),
  unresolved_after_trade AS (
    SELECT * FROM unresolved_after_ce
    WHERE raw_manufacturer NOT IN (SELECT raw_manufacturer FROM trade_match)
  ),
  name_match AS (
    SELECT DISTINCT ON (p.raw_manufacturer)
      p.raw_manufacturer, p.company_name, p.trade_name, p.location_raw,
      m.slug AS manufacturer_slug, 'name_match' AS resolution_method
    FROM unresolved_after_trade AS p
    INNER JOIN pinbase_manufacturers AS m
      ON lower(p.company_name) = lower(m.name)
  ),
  resolved AS (
    (SELECT raw_manufacturer, company_name, trade_name, location_raw,
            manufacturer_slug, resolution_method,
            ce_hq_city, ce_hq_state, ce_hq_country
     FROM ce_match)
    UNION ALL
    (SELECT raw_manufacturer, company_name, trade_name, location_raw,
            manufacturer_slug, resolution_method,
            NULL, NULL, NULL
     FROM trade_match)
    UNION ALL
    (SELECT raw_manufacturer, company_name, trade_name, location_raw,
            manufacturer_slug, resolution_method,
            NULL, NULL, NULL
     FROM name_match)
  )
SELECT
  r.raw_manufacturer,
  r.company_name,
  r.trade_name,
  r.manufacturer_slug,
  r.resolution_method,
  r.location_raw,
  COALESCE(r.ce_hq_city, CASE
    WHEN r.location_raw IS NULL OR r.location_raw = '' THEN NULL
    WHEN len(string_split(r.location_raw, ', ')) >= 2
      THEN string_split(r.location_raw, ', ')[1]
    ELSE NULL
  END) AS headquarters_city,
  COALESCE(r.ce_hq_state, CASE
    WHEN r.location_raw IS NULL OR r.location_raw = '' THEN NULL
    WHEN len(string_split(r.location_raw, ', ')) >= 3
      THEN string_split(r.location_raw, ', ')[2]
    WHEN len(string_split(r.location_raw, ', ')) = 2
      AND EXISTS(SELECT 1 FROM ref_us_states WHERE lower(state_name) = lower(string_split(r.location_raw, ', ')[2]))
      THEN string_split(r.location_raw, ', ')[2]
    WHEN len(string_split(r.location_raw, ', ')) = 1
      AND EXISTS(SELECT 1 FROM ref_us_states WHERE lower(state_name) = lower(r.location_raw))
      THEN r.location_raw
    ELSE NULL
  END) AS headquarters_state,
  COALESCE(r.ce_hq_country, CASE
    WHEN r.location_raw IS NULL OR r.location_raw = '' THEN NULL
    WHEN len(string_split(r.location_raw, ', ')) >= 3
      THEN string_split(r.location_raw, ', ')[len(string_split(r.location_raw, ', '))]
    WHEN len(string_split(r.location_raw, ', ')) = 2
      AND EXISTS(SELECT 1 FROM ref_us_states WHERE lower(state_name) = lower(string_split(r.location_raw, ', ')[2]))
      THEN 'USA'
    WHEN len(string_split(r.location_raw, ', ')) = 2
      THEN string_split(r.location_raw, ', ')[2]
    WHEN len(string_split(r.location_raw, ', ')) = 1
      AND EXISTS(SELECT 1 FROM ref_us_states WHERE lower(state_name) = lower(r.location_raw))
      THEN 'USA'
    ELSE r.location_raw
  END) AS headquarters_country
FROM resolved AS r;

------------------------------------------------------------
-- Cross-source merge: models
-- Mirrors Django's MachineModel after claims resolution.
-- Priority: pinbase (300) > OPDB (200) > IPDB (100)
------------------------------------------------------------

CREATE OR REPLACE VIEW merged_models AS
WITH
  -- Every OPDB record (machine or alias) is a candidate model.
  -- Excludes combo_labels (physical_machine=0): synthetic groupings, not real
  -- machines. Django's ingest_opdb also skips these.
  opdb_base AS (
    SELECT
      om.opdb_id,
      om.group_id AS opdb_group_id,
      om.ipdb_id,
      (om.manufacturer ->> 'name') AS opdb_manufacturer,
      om."name" AS opdb_name,
      om.common_name,
      om.shortname,
      om.manufacture_date,
      om.player_count,
      om.description AS opdb_description,
      om.features,
      om.images,
      om.technology_generation_slug AS opdb_tech_gen_slug,
      om.display_type_slug AS opdb_display_type_slug,
      om.system_slug AS opdb_system_slug,
      om.is_machine,
      om.is_alias
    FROM opdb_machines AS om
    WHERE om.is_alias = 't'
       OR (om.is_machine = 't' AND om.physical_machine != 0)
  ),
  -- IPDB machines not cross-referenced from any OPDB record.
  ipdb_only AS (
    SELECT
      CAST(NULL AS VARCHAR) AS opdb_id,
      CAST(NULL AS VARCHAR) AS opdb_group_id,
      im.IpdbId AS ipdb_id,
      COALESCE(
        imr_mfr."name",
        NULLIF(imr.trade_name, ''),
        imr.company_name,
        im.ManufacturerShortName
      ) AS opdb_manufacturer,
      im.Title AS opdb_name,
      CAST(NULL AS VARCHAR) AS common_name,
      CAST(NULL AS VARCHAR) AS shortname,
      CASE
        WHEN im.DateOfManufacture IS NOT NULL
        THEN TRY_CAST(CAST(im.DateOfManufacture AS VARCHAR) AS DATE)
        ELSE NULL
      END AS manufacture_date,
      im.Players AS player_count,
      CAST(NULL AS VARCHAR) AS opdb_description,
      CAST([] AS VARCHAR[]) AS features,
      CAST(main.list_value() AS STRUCT(
        title VARCHAR,
        "primary" BOOLEAN,
        "type" VARCHAR,
        urls STRUCT(medium VARCHAR, "large" VARCHAR, small VARCHAR),
        sizes STRUCT(
          medium STRUCT(width BIGINT, height BIGINT),
          "large" STRUCT(width BIGINT, height BIGINT),
          small STRUCT(width BIGINT, height BIGINT)
        )
      )[]) AS images,
      im.technology_generation_slug AS opdb_tech_gen_slug,
      im.display_type_slug AS opdb_display_type_slug,
      im.system_slug AS opdb_system_slug,
      CAST('t' AS BOOLEAN) AS is_machine,
      CAST('f' AS BOOLEAN) AS is_alias
    FROM ipdb_machines AS im
    LEFT JOIN opdb_machines AS om ON im.IpdbId = om.ipdb_id
    LEFT JOIN ipdb_manufacturer_resolution AS imr ON im.Manufacturer = imr.raw_manufacturer
    LEFT JOIN pinbase_manufacturers AS imr_mfr ON imr.manufacturer_slug = imr_mfr.slug
    WHERE om.opdb_id IS NULL
  ),
  all_sources AS (
    (SELECT * FROM opdb_base)
    UNION ALL
    (SELECT * FROM ipdb_only)
  )
-- Apply pinbase editorial claims (priority 300 wins over OPDB 200 / IPDB 100).
SELECT
  model_key(m.opdb_id, m.ipdb_id) AS model_key,
  m.opdb_id,
  m.opdb_group_id,
  COALESCE(m.ipdb_id, im.IpdbId) AS ipdb_id,
  -- Name: pinbase > OPDB/IPDB
  COALESCE(pm."name", m.opdb_name) AS "name",
  m.common_name,
  m.shortname,
  m.opdb_manufacturer AS manufacturer,
  m.manufacture_date,
  m.player_count,
  -- Taxonomy: pinbase > OPDB > IPDB
  m.opdb_tech_gen_slug AS technology_generation_slug,
  COALESCE(pm.display_type_slug, m.opdb_display_type_slug) AS display_type_slug,
  m.opdb_system_slug AS system_slug,
  -- Pinbase editorial claims
  COALESCE(pm.is_conversion, false) AS is_conversion,
  pm.converted_from,
  pm.variant_of,
  pm.description AS pinbase_description,
  -- OPDB metadata
  m.opdb_description,
  m.features,
  m.images,
  m.is_machine,
  m.is_alias,
  -- Source tracking
  CASE WHEN m.opdb_id IS NOT NULL THEN 'opdb' ELSE 'ipdb' END AS primary_source,
  (pm.slug IS NOT NULL) AS has_pinbase_claims
FROM all_sources AS m
LEFT JOIN pinbase_models AS pm ON m.opdb_id = pm.opdb_id
LEFT JOIN ipdb_machines AS im ON m.ipdb_id = im.IpdbId;

------------------------------------------------------------
-- Cross-source merge: titles
-- Mirrors Django's Title after claims resolution.
-- Pinbase titles are primary; OPDB groups enrich.
------------------------------------------------------------

CREATE OR REPLACE VIEW merged_titles AS
WITH
  -- Start from OPDB groups as the universe of titles.
  opdb_base AS (
    SELECT
      g.opdb_id AS opdb_group_id,
      g."name" AS opdb_name,
      g.shortname,
      g.description AS opdb_description
    FROM opdb_groups AS g
  ),
  -- Pinbase titles (may reference OPDB groups, or be standalone).
  pinbase AS (
    SELECT
      t.opdb_group_id,
      t.slug,
      t."name" AS pinbase_name,
      t.franchise_slug,
      t.series_slug,
      t.abbreviations
    FROM pinbase_titles AS t
  )
-- Full outer join: every OPDB group + every pinbase title.
SELECT
  COALESCE(o.opdb_group_id, p.opdb_group_id) AS opdb_group_id,
  p.slug AS title_slug,
  -- Name: pinbase > OPDB
  COALESCE(p.pinbase_name, o.opdb_name) AS "name",
  o.shortname,
  o.opdb_description AS description,
  p.franchise_slug,
  p.series_slug,
  p.abbreviations,
  (p.slug IS NOT NULL) AS has_pinbase_claims
FROM opdb_base AS o
FULL OUTER JOIN pinbase AS p ON o.opdb_group_id = p.opdb_group_id;
