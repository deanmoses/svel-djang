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

-- opdb_tiers: one row per OPDB machine (non-alias), with combo-label detection
CREATE OR REPLACE VIEW opdb_tiers AS
SELECT
  opdb_id,
  group_id AS opdb_group_id,
  machine_id,
  (manufacturer ->> 'name') AS manufacturer,
  "name",
  common_name,
  shortname,
  manufacture_date,
  ipdb_id,
  images,
  (
    (regexp_matches("name", '\([^)]+/[^)]+\)') OR ("name" ~~ '% / %'))
    AND EXISTS(
      SELECT 1 FROM opdb_machines AS a
      WHERE a.group_id = opdb_machines.group_id
        AND a.machine_id = opdb_machines.machine_id
        AND a.is_alias = 't'
    )
  ) AS is_combo_label,
  technology_generation_slug,
  display_type_slug,
  system_slug
FROM opdb_machines
WHERE is_machine = 't';

-- opdb_models: alias models + tier defaults + synthetic (no-alias) models
CREATE OR REPLACE VIEW opdb_models AS
WITH
  combo_labels AS (
    SELECT opdb_group_id, machine_id
    FROM opdb_tiers
    WHERE is_combo_label
  ),
  alias_models AS (
    SELECT
      a.opdb_id,
      a.group_id AS opdb_group_id,
      a.machine_id,
      a.alias_id,
      (a.group_id || '-' || a.machine_id) AS tier_opdb_id,
      (a.manufacturer ->> 'name') AS manufacturer,
      a."name",
      a.common_name,
      a.shortname,
      a.manufacture_date,
      a.ipdb_id,
      a.images,
      CASE
        WHEN cl.machine_id IS NOT NULL
        THEN (row_number() OVER (PARTITION BY a.group_id, a.machine_id ORDER BY a.opdb_id) = 1)
        ELSE CAST('f' AS BOOLEAN)
      END AS is_default,
      CAST('f' AS BOOLEAN) AS is_synthetic
    FROM opdb_machines AS a
    LEFT JOIN combo_labels AS cl
      ON cl.opdb_group_id = a.group_id AND cl.machine_id = a.machine_id
    WHERE a.is_alias = 't'
  ),
  tier_default_models AS (
    SELECT
      opdb_id,
      group_id AS opdb_group_id,
      machine_id,
      CAST(NULL AS VARCHAR) AS alias_id,
      opdb_id AS tier_opdb_id,
      (manufacturer ->> 'name') AS manufacturer,
      "name",
      common_name,
      shortname,
      manufacture_date,
      ipdb_id,
      images,
      CAST('t' AS BOOLEAN) AS is_default,
      CAST('f' AS BOOLEAN) AS is_synthetic
    FROM opdb_machines AS m
    WHERE m.is_machine = 't'
      AND NOT EXISTS(
        SELECT 1 FROM combo_labels AS cl
        WHERE cl.opdb_group_id = m.group_id AND cl.machine_id = m.machine_id
      )
      AND EXISTS(
        SELECT 1 FROM opdb_machines AS a
        WHERE a.group_id = m.group_id
          AND a.machine_id = m.machine_id
          AND a.is_alias = 't'
      )
  ),
  synthetic_models AS (
    SELECT
      opdb_id,
      group_id AS opdb_group_id,
      machine_id,
      CAST(NULL AS VARCHAR) AS alias_id,
      opdb_id AS tier_opdb_id,
      (manufacturer ->> 'name') AS manufacturer,
      "name",
      common_name,
      shortname,
      manufacture_date,
      ipdb_id,
      images,
      CAST('t' AS BOOLEAN) AS is_default,
      CAST('t' AS BOOLEAN) AS is_synthetic
    FROM opdb_machines AS m
    WHERE m.is_machine = 't'
      AND NOT EXISTS(
        SELECT 1 FROM opdb_machines AS a
        WHERE a.group_id = m.group_id
          AND a.machine_id = m.machine_id
          AND a.is_alias = 't'
      )
  )
(SELECT * FROM alias_models)
UNION ALL (SELECT * FROM tier_default_models)
UNION ALL (SELECT * FROM synthetic_models);

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
-- Cross-source merge views
------------------------------------------------------------

-- unified_models: OPDB models + IPDB-only fallback, with taxonomy resolution
CREATE OR REPLACE VIEW unified_models AS
WITH
  opdb AS (
    SELECT
      opdb_id, opdb_group_id, machine_id, alias_id, tier_opdb_id,
      manufacturer, "name", common_name, shortname,
      manufacture_date, ipdb_id, images, is_default, is_synthetic,
      'opdb' AS "source"
    FROM opdb_models
  ),
  ipdb_only AS (
    SELECT
      CAST(NULL AS VARCHAR) AS opdb_id,
      CAST(NULL AS VARCHAR) AS opdb_group_id,
      CAST(NULL AS VARCHAR) AS machine_id,
      CAST(NULL AS VARCHAR) AS alias_id,
      CAST(NULL AS VARCHAR) AS tier_opdb_id,
      COALESCE(
        imr_mfr."name",
        NULLIF(imr.trade_name, ''),
        imr.company_name,
        im.ManufacturerShortName
      ) AS manufacturer,
      im.Title AS "name",
      CAST(NULL AS VARCHAR) AS common_name,
      CAST(NULL AS VARCHAR) AS shortname,
      CASE
        WHEN im.DateOfManufacture IS NOT NULL
        THEN TRY_CAST(CAST(im.DateOfManufacture AS VARCHAR) AS DATE)
        ELSE NULL
      END AS manufacture_date,
      im.IpdbId AS ipdb_id,
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
      CAST('t' AS BOOLEAN) AS is_default,
      CAST('f' AS BOOLEAN) AS is_synthetic,
      'ipdb' AS "source"
    FROM ipdb_machines AS im
    LEFT JOIN opdb_machines AS om ON im.IpdbId = om.ipdb_id
    LEFT JOIN ipdb_manufacturer_resolution AS imr ON im.Manufacturer = imr.raw_manufacturer
    LEFT JOIN pinbase_manufacturers AS imr_mfr ON imr.manufacturer_slug = imr_mfr.slug
    WHERE om.opdb_id IS NULL
  ),
  all_models AS (
    (SELECT * FROM opdb)
    UNION ALL
    (SELECT * FROM ipdb_only)
  )
SELECT
  m.*,
  COALESCE(om.technology_generation_slug, im.technology_generation_slug) AS technology_generation_slug,
  COALESCE(pm.display_type_slug, om.display_type_slug, im.display_type_slug) AS display_type_slug,
  COALESCE(om.system_slug, im.system_slug) AS system_slug
FROM all_models AS m
LEFT JOIN pinbase_models AS pm ON m.opdb_id = pm.opdb_id
LEFT JOIN opdb_machines AS om ON m.opdb_id = om.opdb_id
LEFT JOIN ipdb_machines AS im ON m.ipdb_id = im.IpdbId;

-- unified_tiers: OPDB tiers + IPDB-only fallback, with taxonomy resolution
CREATE OR REPLACE VIEW unified_tiers AS
WITH
  opdb AS (
    SELECT
      opdb_id, opdb_group_id, machine_id,
      "name", common_name, shortname,
      manufacture_date, ipdb_id, images, is_combo_label,
      'opdb' AS "source"
    FROM opdb_tiers
  ),
  ipdb_only AS (
    SELECT
      CAST(NULL AS VARCHAR) AS opdb_id,
      CAST(NULL AS VARCHAR) AS opdb_group_id,
      CAST(NULL AS VARCHAR) AS machine_id,
      im.Title AS "name",
      CAST(NULL AS VARCHAR) AS common_name,
      CAST(NULL AS VARCHAR) AS shortname,
      CASE
        WHEN im.DateOfManufacture IS NOT NULL
        THEN TRY_CAST(CAST(im.DateOfManufacture AS VARCHAR) AS DATE)
        ELSE NULL
      END AS manufacture_date,
      im.IpdbId AS ipdb_id,
      CAST(list_value() AS STRUCT(
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
      CAST('f' AS BOOLEAN) AS is_combo_label,
      'ipdb' AS "source"
    FROM ipdb_machines AS im
    LEFT JOIN opdb_machines AS om ON im.IpdbId = om.ipdb_id
    WHERE om.opdb_id IS NULL
  ),
  all_tiers AS (
    (SELECT * FROM opdb)
    UNION ALL
    (SELECT * FROM ipdb_only)
  )
SELECT
  e.*,
  COALESCE(oe.technology_generation_slug, im.technology_generation_slug) AS technology_generation_slug,
  COALESCE(pm.display_type_slug, oe.display_type_slug, im.display_type_slug) AS display_type_slug,
  COALESCE(oe.system_slug, im.system_slug) AS system_slug
FROM all_tiers AS e
LEFT JOIN pinbase_models AS pm ON e.opdb_id = pm.opdb_id
LEFT JOIN opdb_tiers AS oe ON e.opdb_id = oe.opdb_id
LEFT JOIN ipdb_machines AS im ON e.ipdb_id = im.IpdbId;
