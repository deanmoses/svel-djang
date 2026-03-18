-- 02_staging.sql — Per-source transforms.
-- Makes each source independently queryable with normalized slugs.
-- No cross-source joins.
-- Depends on: 01_raw.sql

------------------------------------------------------------
-- Reference lookup tables (static mappings)
------------------------------------------------------------

-- OPDB type code -> technology generation slug
CREATE OR REPLACE VIEW ref_opdb_technology_generation AS
SELECT * FROM (VALUES
  ('em', 'electromechanical'),
  ('ss', 'solid-state'),
  ('me', 'pure-mechanical')
) AS t(opdb_type, slug);

-- OPDB display code -> display type slug
CREATE OR REPLACE VIEW ref_opdb_display_type AS
SELECT * FROM (VALUES
  ('reels',        'score-reels'),
  ('lights',       'backglass-lights'),
  ('alphanumeric', 'alphanumeric'),
  ('cga',          'cga'),
  ('dmd',          'dot-matrix'),
  ('lcd',          'lcd')
) AS t(opdb_display, slug);

-- IPDB TypeShortName/Type -> technology generation slug
CREATE OR REPLACE VIEW ref_ipdb_technology_generation AS
SELECT * FROM (VALUES
  ('EM', NULL,                    'electromechanical'),
  ('SS', NULL,                    'solid-state'),
  (NULL, 'Pure Mechanical (PM)',  'pure-mechanical')
) AS t(type_short_name, type_full, slug);

------------------------------------------------------------
-- OPDB staged
------------------------------------------------------------

-- Add technology/display slugs and extract manufacturer name
CREATE OR REPLACE VIEW opdb_machines_staged AS
SELECT
  om.*,
  (om.manufacturer ->> 'name') AS manufacturer_name,
  tg.slug AS technology_generation_slug,
  dt.slug AS display_type_slug
FROM opdb_machines AS om
LEFT JOIN ref_opdb_technology_generation AS tg ON om."type" = tg.opdb_type
LEFT JOIN ref_opdb_display_type AS dt ON om.display = dt.opdb_display;

-- Distinct manufacturers from OPDB
CREATE OR REPLACE VIEW opdb_manufacturers AS
SELECT DISTINCT
  om.manufacturer.manufacturer_id AS opdb_manufacturer_id,
  (om.manufacturer ->> 'name') AS "name",
  (om.manufacturer ->> 'full_name') AS full_name
FROM opdb_machines AS om
WHERE om.manufacturer IS NOT NULL
ORDER BY "name";

-- Unnested keywords per machine
CREATE OR REPLACE VIEW opdb_keywords AS
SELECT opdb_id, "name", unnest(keywords) AS keyword
FROM opdb_machines
WHERE len(keywords) > 0;

------------------------------------------------------------
-- IPDB staged
------------------------------------------------------------

-- Add technology generation slug and system/subgeneration via MPU match
CREATE OR REPLACE VIEW ipdb_machines_staged AS
SELECT
  im.*,
  COALESCE(tg1.slug, tg2.slug) AS technology_generation_slug,
  ps.slug AS system_slug,
  ps.technology_subgeneration_slug
FROM ipdb_machines AS im
LEFT JOIN ref_ipdb_technology_generation AS tg1
  ON im.TypeShortName = tg1.type_short_name AND tg1.type_short_name IS NOT NULL
LEFT JOIN ref_ipdb_technology_generation AS tg2
  ON im."Type" = tg2.type_full AND tg2.type_full IS NOT NULL
LEFT JOIN systems AS ps
  ON list_contains(ps.mpu_strings, im.MPU);

-- Distinct corporate entities parsed from IPDB manufacturer strings.
-- Splits the structured string into company name, trade name, years, and location.
CREATE OR REPLACE VIEW ipdb_corporate_entities AS
WITH ice AS (
SELECT DISTINCT
  ManufacturerId AS ipdb_manufacturer_id,
  Manufacturer AS raw_name,
  ManufacturerShortName AS short_name,

  -- Company name: strip trade-name bracket, years, and ", of ..." location
  trim(trailing ',' FROM trim(
    regexp_replace(
      regexp_replace(
        regexp_replace(Manufacturer, '\s*\[Trade Name:.*?\]', ''),
        '\s*\(\d+.*?\)', ''),
      ',\s*of\s+.*$', '')
  )) AS company_name,

  -- Trade name from [Trade Name: X]
  regexp_extract(Manufacturer, '\[Trade Name:\s*(.+?)\]', 1) AS trade_name,

  -- Year range: YYYY-YYYY or YYYY-now or YYYY-present
  CASE WHEN regexp_extract(Manufacturer, '\((\d{4})-', 1) != '' THEN
    CAST(regexp_extract(Manufacturer, '\((\d{4})-', 1) AS INTEGER)
  END AS year_start,

  CASE WHEN regexp_extract(Manufacturer, '\(\d{4}-(\d{4})\)', 1) != '' THEN
    CAST(regexp_extract(Manufacturer, '\(\d{4}-(\d{4})\)', 1) AS INTEGER)
  END AS year_end,
  -- year_end is NULL when "now" or "present"

  -- Single year: (YYYY) with no hyphen — needs further analysis
  CASE WHEN regexp_extract(Manufacturer, '\((\d{4})\)', 1) != ''
        AND Manufacturer NOT LIKE '%-%(%' THEN
    CAST(regexp_extract(Manufacturer, '\((\d{4})\)', 1) AS INTEGER)
  END AS single_year,

  -- Full location string from ", of ..." (not split into city/state/country)
  COALESCE(
    trim(trailing ',' FROM
      regexp_extract(Manufacturer, ',\s*of\s+(.+?)(?:\s*\(\d|\s*\[Trade|\s*$)', 1)
    ),
    ''
  ) AS location

FROM ipdb_machines
WHERE Manufacturer IS NOT NULL
  AND Manufacturer != 'Unknown Manufacturer'
ORDER BY company_name),
-- Parse location into raw city/state/country, then apply overrides and normalization
parsed AS (
  SELECT
    ice.*,
    string_split(ice.location, ', ') AS parts,
    len(string_split(ice.location, ', ')) AS nparts
  FROM ice
),
with_raw_hq AS (
  SELECT
    p.*,
    CASE
      WHEN p.location = '' THEN NULL
      WHEN p.nparts >= 2 THEN p.parts[1]
      ELSE NULL
    END AS _raw_city,
    CASE
      WHEN p.location = '' THEN NULL
      WHEN p.nparts >= 3 THEN p.parts[2]
      WHEN p.nparts = 2 THEN st2.canonical_name
      WHEN p.nparts = 1 THEN st1.canonical_name
      ELSE NULL
    END AS _raw_state,
    CASE
      WHEN p.location = '' THEN NULL
      WHEN p.nparts >= 3 THEN p.parts[p.nparts]
      WHEN p.nparts = 2 AND st2.canonical_name IS NOT NULL THEN 'USA'
      WHEN p.nparts = 2 THEN p.parts[2]
      WHEN p.nparts = 1 AND st1.canonical_name IS NOT NULL THEN 'USA'
      ELSE p.location
    END AS _raw_country
  FROM parsed p
  LEFT JOIN ref_us_states st2
    ON p.nparts = 2 AND lower(st2.state_name) = lower(p.parts[2])
  LEFT JOIN ref_us_states st1
    ON p.nparts = 1 AND lower(st1.state_name) = lower(p.location)
)
SELECT
  h.ipdb_manufacturer_id, h.raw_name, h.short_name,
  h.company_name, h.trade_name,
  -- The brand name: trade name if given, otherwise the company name
  CASE WHEN h.trade_name != '' THEN h.trade_name ELSE h.company_name END AS manufacturer_name,
  h.year_start, h.year_end, h.single_year, h.location,

  CASE WHEN ovr.ipdb_manufacturer_id IS NOT NULL THEN ovr.headquarters_city ELSE h._raw_city END AS headquarters_city,
  CASE WHEN ovr.ipdb_manufacturer_id IS NOT NULL THEN ovr.headquarters_state ELSE h._raw_state END AS headquarters_state,
  COALESCE(cn.normalized_country,
    CASE WHEN ovr.ipdb_manufacturer_id IS NOT NULL THEN ovr.headquarters_country ELSE h._raw_country END
  ) AS headquarters_country,

  -- Manufacturer resolution — derived purely from IPDB data + pinbase manufacturers.
  -- No dependency on existing corporate_entities table.
  -- manufacturer_name = COALESCE(trade_name, company_name)
  -- 1. Exact match: manufacturer_name → manufacturer.name
  -- 2. Normalized match (unambiguous): strip business suffixes, match if unique
  -- 3. Model-based: majority manufacturer_slug from pinbase models for this IPDB manufacturer
  COALESCE(
    mfr_exact.slug,
    mfr_normalized.slug,
    mfr_from_models.manufacturer_slug
  ) AS manufacturer_slug,

  model_years.year_of_first_model,
  model_years.year_of_last_model
FROM with_raw_hq h
LEFT JOIN ref_ipdb_location_overrides ovr
  ON ovr.ipdb_manufacturer_id = h.ipdb_manufacturer_id
LEFT JOIN ref_country_normalization cn
  ON cn.raw_country = COALESCE(ovr.headquarters_country, h._raw_country)
-- Priority 1: exact match on manufacturer_name
LEFT JOIN manufacturers mfr_exact
  ON lower(mfr_exact.name) = lower(
    CASE WHEN h.trade_name != '' THEN h.trade_name ELSE h.company_name END
  )
-- Priority 2: normalized match (unambiguous only)
LEFT JOIN (
  SELECT slug, normalize_mfr_name(name) AS norm_name
  FROM manufacturers
  WHERE normalize_mfr_name(name) != ''
  QUALIFY count(*) OVER (PARTITION BY normalize_mfr_name(name)) = 1
) mfr_normalized
  ON mfr_normalized.norm_name = normalize_mfr_name(
    CASE WHEN h.trade_name != '' THEN h.trade_name ELSE h.company_name END
  )
  AND mfr_exact.slug IS NULL
-- Priority 3: majority vote from models
LEFT JOIN (
  SELECT
    im.ManufacturerId,
    mod.manufacturer_slug,
    count(*) AS cnt
  FROM ipdb_machines im
  JOIN models mod ON mod.ipdb_id = im.IpdbId
  WHERE mod.manufacturer_slug IS NOT NULL
  GROUP BY im.ManufacturerId, mod.manufacturer_slug
  QUALIFY row_number() OVER (PARTITION BY im.ManufacturerId ORDER BY count(*) DESC) = 1
) mfr_from_models
  ON mfr_from_models.ManufacturerId = h.ipdb_manufacturer_id
  AND mfr_exact.slug IS NULL AND mfr_normalized.slug IS NULL
LEFT JOIN (
  SELECT
    ManufacturerId,
    MIN(EXTRACT(YEAR FROM CAST(DateOfManufacture AS DATE)))::INTEGER AS year_of_first_model,
    MAX(EXTRACT(YEAR FROM CAST(DateOfManufacture AS DATE)))::INTEGER AS year_of_last_model
  FROM ipdb_machines
  WHERE DateOfManufacture IS NOT NULL
  GROUP BY ManufacturerId
) model_years ON model_years.ManufacturerId = h.ipdb_manufacturer_id;

------------------------------------------------------------
-- Pinbase staged
------------------------------------------------------------

-- Flat credits: one row per model + person + role
CREATE OR REPLACE VIEW pinbase_credits AS
SELECT
  m.slug AS model_slug,
  m.title_slug,
  unnest(m.credit_refs).person_slug AS person_slug,
  unnest(m.credit_refs)."role" AS "role"
FROM models AS m
WHERE m.credit_refs IS NOT NULL AND len(m.credit_refs) > 0;
