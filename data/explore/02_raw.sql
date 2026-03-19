-- 02_raw.sql — Raw tables from all JSON data files.
-- No transforms, no joins. Just flatten top-level wrappers where needed.
-- Tables (not views) so JSON is parsed once at build time.
-- Depends on: nothing
--
-- Requires: SET VARIABLE ingest_base = '<path-or-url>';
-- Local default is set by rebuild_explore.sh.
-- For remote access (e.g. MotherDuck), set to R2 URL before loading:
--   SET VARIABLE ingest_base = 'https://pub-8f33ea1ac628450298edd0d3243ecf5a.r2.dev';

------------------------------------------------------------
-- Pinbase Markdown-sourced data (via pinbase_export)
------------------------------------------------------------

CREATE OR REPLACE TABLE cabinets AS
SELECT * FROM read_json_auto(getvariable('ingest_base') || '/pinbase_export/cabinet.json');

CREATE OR REPLACE TABLE corporate_entities AS
SELECT * FROM read_json_auto(getvariable('ingest_base') || '/pinbase_export/corporate_entity.json');

CREATE OR REPLACE TABLE credit_roles AS
SELECT * FROM read_json_auto(getvariable('ingest_base') || '/pinbase_export/credit_role.json');

CREATE OR REPLACE TABLE display_subtypes AS
SELECT * FROM read_json_auto(getvariable('ingest_base') || '/pinbase_export/display_subtype.json');

CREATE OR REPLACE TABLE display_types AS
SELECT * FROM read_json_auto(getvariable('ingest_base') || '/pinbase_export/display_type.json');

CREATE OR REPLACE TABLE franchises AS
SELECT * FROM read_json_auto(getvariable('ingest_base') || '/pinbase_export/franchise.json');

CREATE OR REPLACE TABLE game_formats AS
SELECT * FROM read_json_auto(getvariable('ingest_base') || '/pinbase_export/game_format.json');

CREATE OR REPLACE TABLE gameplay_features AS
SELECT * FROM read_json_auto(getvariable('ingest_base') || '/pinbase_export/gameplay_feature.json');

CREATE OR REPLACE TABLE manufacturers AS
SELECT * FROM read_json_auto(getvariable('ingest_base') || '/pinbase_export/manufacturer.json');

CREATE OR REPLACE TABLE models AS
SELECT * FROM read_json_auto(getvariable('ingest_base') || '/pinbase_export/model.json', (union_by_name = CAST('t' AS BOOLEAN)));

CREATE OR REPLACE TABLE people AS
SELECT * FROM read_json_auto(getvariable('ingest_base') || '/pinbase_export/person.json', (union_by_name = CAST('t' AS BOOLEAN)));

CREATE OR REPLACE TABLE series AS
SELECT * FROM read_json_auto(getvariable('ingest_base') || '/pinbase_export/series.json');

CREATE OR REPLACE TABLE systems AS
SELECT * FROM read_json_auto(getvariable('ingest_base') || '/pinbase_export/system.json');

CREATE OR REPLACE TABLE tags AS
SELECT * FROM read_json_auto(getvariable('ingest_base') || '/pinbase_export/tag.json');

CREATE OR REPLACE TABLE technology_generations AS
SELECT * FROM read_json_auto(getvariable('ingest_base') || '/pinbase_export/technology_generation.json');

CREATE OR REPLACE TABLE technology_subgenerations AS
SELECT * FROM read_json_auto(getvariable('ingest_base') || '/pinbase_export/technology_subgeneration.json');

CREATE OR REPLACE TABLE themes AS
SELECT * FROM read_json_auto(getvariable('ingest_base') || '/pinbase_export/theme.json');

CREATE OR REPLACE TABLE titles AS
SELECT * FROM read_json_auto(getvariable('ingest_base') || '/pinbase_export/title.json', (union_by_name = CAST('t' AS BOOLEAN)));

------------------------------------------------------------
-- External source dumps
------------------------------------------------------------

-- Fandom wiki exports
CREATE OR REPLACE TABLE fandom_games AS
SELECT d.*
FROM (SELECT unnest(games) AS d FROM read_json_auto(getvariable('ingest_base') || '/fandom_games.json'));

CREATE OR REPLACE TABLE fandom_manufacturers AS
SELECT d.*
FROM (SELECT unnest(manufacturers) AS d FROM read_json_auto(getvariable('ingest_base') || '/fandom_manufacturers.json'));

CREATE OR REPLACE TABLE fandom_persons AS
SELECT d.*
FROM (SELECT unnest(persons) AS d FROM read_json_auto(getvariable('ingest_base') || '/fandom_persons.json'));

-- Pinball Map API exports
CREATE OR REPLACE TABLE pinballmap_machines AS
SELECT d.*
FROM (SELECT unnest(machines) AS d FROM read_json_auto(getvariable('ingest_base') || '/pinballmap_machines.json'));

CREATE OR REPLACE TABLE pinballmap_machine_groups AS
SELECT d.*
FROM (SELECT unnest(machine_groups) AS d FROM read_json_auto(getvariable('ingest_base') || '/pinballmap_machine_groups.json'));

-- OPDB (Open Pinball Database) exports
CREATE OR REPLACE TABLE opdb_groups AS
SELECT * FROM read_json_auto(getvariable('ingest_base') || '/opdb_export_groups.json');

CREATE OR REPLACE TABLE opdb_machines AS
SELECT
  opdb_id,
  split_part(opdb_id, '-', 1) AS group_id,
  split_part(opdb_id, '-', 2) AS machine_id,
  CASE
    WHEN split_part(opdb_id, '-', 3) = '' THEN NULL
    ELSE split_part(opdb_id, '-', 3)
  END AS alias_id,
  is_machine,
  is_alias,
  "name",
  common_name,
  shortname,
  physical_machine,
  ipdb_id,
  manufacture_date,
  manufacturer,
  "type",
  display,
  player_count,
  features,
  keywords,
  description,
  created_at,
  updated_at,
  images
FROM read_json_auto(getvariable('ingest_base') || '/opdb_export_machines.json');

-- IPDB (Internet Pinball Database) export — xantari/Ipdb.Database scrape
CREATE OR REPLACE TABLE ipdb_machines AS
SELECT d.*
FROM (
  SELECT unnest("Data") AS d
  FROM read_json_auto(getvariable('ingest_base') || '/ipdb_xantari.json', (maximum_object_size = 67108864))
);
