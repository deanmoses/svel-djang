-- 03_compare.sql — Cross-source comparison views and slug quality analysis.
-- Depends on: 01_raw.sql, 02_staging.sql

------------------------------------------------------------
-- Cross-source: models vs OPDB (by opdb_id)
------------------------------------------------------------

CREATE OR REPLACE VIEW compare_models_opdb AS
SELECT
  m.slug,
  m.name AS pinbase_name,
  o.name AS opdb_name,
  m.name <> o.name AS name_differs,
  m.manufacturer_slug AS pinbase_manufacturer,
  o.manufacturer_name AS opdb_manufacturer,
  m.year AS pinbase_year,
  year(o.manufacture_date) AS opdb_year,
  m.year <> year(o.manufacture_date) AS year_differs,
  m.technology_generation_slug AS pinbase_tech_gen,
  o.technology_generation_slug AS opdb_tech_gen,
  m.technology_generation_slug <> o.technology_generation_slug AS tech_gen_differs,
  m.display_type_slug AS pinbase_display,
  o.display_type_slug AS opdb_display,
  m.display_type_slug <> o.display_type_slug AS display_differs,
  m.player_count AS pinbase_players,
  o.player_count AS opdb_players,
  m.opdb_id
FROM models AS m
INNER JOIN opdb_machines_staged AS o ON m.opdb_id = o.opdb_id;

------------------------------------------------------------
-- Cross-source: models vs IPDB (by ipdb_id)
------------------------------------------------------------

CREATE OR REPLACE VIEW compare_models_ipdb AS
SELECT
  m.slug,
  m.name AS pinbase_name,
  i.Title AS ipdb_name,
  m.name <> i.Title AS name_differs,
  m.manufacturer_slug AS pinbase_manufacturer,
  i.ManufacturerShortName AS ipdb_manufacturer,
  m.year AS pinbase_year,
  TRY_CAST(i.DateOfManufacture AS INTEGER) AS ipdb_year,
  m.year <> TRY_CAST(i.DateOfManufacture AS INTEGER) AS year_differs,
  m.technology_generation_slug AS pinbase_tech_gen,
  i.technology_generation_slug AS ipdb_tech_gen,
  m.player_count AS pinbase_players,
  i.Players AS ipdb_players,
  i.AverageFunRating AS ipdb_rating,
  i.ProductionNumber AS ipdb_production,
  m.ipdb_id
FROM models AS m
INNER JOIN ipdb_machines_staged AS i ON m.ipdb_id = i.IpdbId;

------------------------------------------------------------
-- Cross-source: titles vs OPDB groups (by opdb_group_id)
------------------------------------------------------------

CREATE OR REPLACE VIEW compare_titles_opdb AS
SELECT
  t.slug,
  t.name AS pinbase_name,
  g.name AS opdb_name,
  t.name <> g.name AS name_differs,
  t.opdb_group_id
FROM titles AS t
INNER JOIN opdb_groups AS g ON t.opdb_group_id = g.opdb_id;

------------------------------------------------------------
-- Model → Corporate Entity resolution
-- Derives the corporate_entity_slug each model should have.
-- 1. IPDB models: match via ManufacturerId → corporate_entity.ipdb_manufacturer_id
-- 2. OPDB-only models: match via manufacturer_slug → corporate_entity with same manufacturer_slug
--    (picks the one with no ipdb_manufacturer_id if multiple exist, else arbitrary)
------------------------------------------------------------

CREATE OR REPLACE VIEW model_corporate_entity AS
SELECT
  m.slug AS model_slug,
  m.manufacturer_slug,
  COALESCE(
    ce_ipdb.slug,
    ce_mfr.slug
  ) AS corporate_entity_slug,
  CASE
    WHEN ce_ipdb.slug IS NOT NULL THEN 'ipdb'
    WHEN ce_mfr.slug IS NOT NULL THEN 'manufacturer'
    ELSE 'unresolved'
  END AS resolution_method
FROM models m
-- For IPDB models: model → ipdb_id → ipdb_machines.ManufacturerId → corporate_entity
LEFT JOIN ipdb_machines im ON m.ipdb_id = im.IpdbId
LEFT JOIN corporate_entities ce_ipdb
  ON ce_ipdb.ipdb_manufacturer_id = im.ManufacturerId
-- Fallback: match via manufacturer_slug (for non-IPDB models or IPDB "Unknown Manufacturer")
LEFT JOIN (
  SELECT DISTINCT ON (manufacturer_slug) slug, manufacturer_slug
  FROM corporate_entities
  ORDER BY manufacturer_slug, ipdb_manufacturer_id NULLS FIRST
) ce_mfr
  ON ce_mfr.manufacturer_slug = m.manufacturer_slug
  AND ce_ipdb.slug IS NULL;

------------------------------------------------------------
-- Slug quality: name faithfulness
-- Compares each model's slug to a mechanical slugification of its name.
-- Large edit distance or missing words signal a slug that doesn't
-- represent the name well.
------------------------------------------------------------

CREATE OR REPLACE VIEW slug_name_faithfulness AS
WITH slugified AS (
  SELECT
    slug,
    name,
    title_slug,
    -- Mechanical slug: lowercase, spaces to hyphens, strip non-alphanumeric
    regexp_replace(
      lower(replace(name, ' ', '-')),
      '[^a-z0-9\-]', '', 'g'
    ) AS name_as_slug
  FROM models
)
SELECT
  *,
  slug <> name_as_slug AS slug_differs_from_name,
  length(slug) - length(name_as_slug) AS slug_length_delta
FROM slugified
WHERE slug <> name_as_slug;

------------------------------------------------------------
-- Slug quality: prime slug conflicts
-- Finds cases where a model's slug matches another title's slug,
-- suggesting the "obvious" slug was taken by a different title group.
-- Ranks by IPDB production count and rating so you can see when
-- an obscure model holds the prime slug over a popular one.
------------------------------------------------------------

CREATE OR REPLACE VIEW slug_prime_conflicts AS
WITH
  -- Models whose slug differs from their title_slug: they didn't get the "home" slug
  displaced AS (
    SELECT
      m.slug AS model_slug,
      m.name AS model_name,
      m.title_slug,
      m.ipdb_id,
      m.manufacturer_slug,
      m.year
    FROM models AS m
    WHERE m.slug <> m.title_slug
      AND m.title_slug IS NOT NULL
  ),
  -- The model that holds the title's "prime" slug (slug = title_slug)
  prime_holders AS (
    SELECT
      m.slug AS model_slug,
      m.name AS model_name,
      m.title_slug,
      m.ipdb_id,
      m.manufacturer_slug,
      m.year
    FROM models AS m
    WHERE m.slug = m.title_slug
  )
SELECT
  d.title_slug,
  -- The displaced (potentially popular) model
  d.model_slug AS displaced_slug,
  d.model_name AS displaced_name,
  d.manufacturer_slug AS displaced_manufacturer,
  d.year AS displaced_year,
  di.ProductionNumber AS displaced_production,
  di.AverageFunRating AS displaced_rating,
  -- The model holding the prime slug
  p.model_slug AS prime_slug,
  p.model_name AS prime_name,
  p.manufacturer_slug AS prime_manufacturer,
  p.year AS prime_year,
  pi.ProductionNumber AS prime_production,
  pi.AverageFunRating AS prime_rating
FROM displaced AS d
LEFT JOIN prime_holders AS p ON d.title_slug = p.title_slug
LEFT JOIN ipdb_machines AS di ON d.ipdb_id = di.IpdbId
LEFT JOIN ipdb_machines AS pi ON p.ipdb_id = pi.IpdbId
WHERE p.model_slug IS NOT NULL
ORDER BY COALESCE(di.ProductionNumber, 0) DESC;
