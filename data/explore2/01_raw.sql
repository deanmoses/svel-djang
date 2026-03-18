-- 01_raw.sql — Raw tables from all JSON data files.
-- No transforms, no joins. Just flatten top-level wrappers where needed.
-- Tables (not views) so JSON is parsed once at build time.

------------------------------------------------------------
-- Pinbase Markdown-sourced data (via pinbase_export)
------------------------------------------------------------

CREATE OR REPLACE TABLE cabinets AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/cabinet.json');

CREATE OR REPLACE TABLE corporate_entities AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/corporate_entity.json');

CREATE OR REPLACE TABLE credit_roles AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/credit_role.json');

CREATE OR REPLACE TABLE display_subtypes AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/display_subtype.json');

CREATE OR REPLACE TABLE display_types AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/display_type.json');

CREATE OR REPLACE TABLE franchises AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/franchise.json');

CREATE OR REPLACE TABLE game_formats AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/game_format.json');

CREATE OR REPLACE TABLE gameplay_features AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/gameplay_feature.json');

CREATE OR REPLACE TABLE manufacturers AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/manufacturer.json');

CREATE OR REPLACE TABLE models AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/model.json', (union_by_name = CAST('t' AS BOOLEAN)));

CREATE OR REPLACE TABLE people AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/person.json', (union_by_name = CAST('t' AS BOOLEAN)));

CREATE OR REPLACE TABLE series AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/series.json');

CREATE OR REPLACE TABLE systems AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/system.json');

CREATE OR REPLACE TABLE tags AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/tag.json');

CREATE OR REPLACE TABLE technology_generations AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/technology_generation.json');

CREATE OR REPLACE TABLE technology_subgenerations AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/technology_subgeneration.json');

CREATE OR REPLACE TABLE themes AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/theme.json');

CREATE OR REPLACE TABLE titles AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/title.json', (union_by_name = CAST('t' AS BOOLEAN)));

------------------------------------------------------------
-- Reference lookup tables
------------------------------------------------------------

-- US states: canonical name + aliases for IPDB typos/variants
CREATE OR REPLACE VIEW ref_us_states AS
SELECT * FROM (VALUES
  ('Alabama',        'Alabama'),
  ('Alaska',         'Alaska'),
  ('Arizona',        'Arizona'),
  ('Arkansas',       'Arkansas'),
  ('California',     'California'),
  ('Colorado',       'Colorado'),
  ('Connecticut',    'Connecticut'),
  ('Delaware',       'Delaware'),
  ('Florida',        'Florida'),
  ('Georgia',        'Georgia'),
  ('Hawaii',         'Hawaii'),
  ('Idaho',          'Idaho'),
  ('Illinois',       'Illinois'),
  ('Indiana',        'Indiana'),
  ('Iowa',           'Iowa'),
  ('Kansas',         'Kansas'),
  ('Kentucky',       'Kentucky'),
  ('Louisiana',      'Louisiana'),
  ('Maine',          'Maine'),
  ('Maryland',       'Maryland'),
  ('Massachusetts',  'Massachusetts'),
  ('Michigan',       'Michigan'),
  ('Minnesota',      'Minnesota'),
  ('Mississippi',    'Mississippi'),
  ('Missouri',       'Missouri'),
  ('Montana',        'Montana'),
  ('Nebraska',       'Nebraska'),
  ('Nevada',         'Nevada'),
  ('New Hampshire',  'New Hampshire'),
  ('New Jersey',     'New Jersey'),
  ('New Mexico',     'New Mexico'),
  ('New York',       'New York'),
  ('North Carolina', 'North Carolina'),
  ('North Dakota',   'North Dakota'),
  ('Ohio',           'Ohio'),
  ('Oklahoma',       'Oklahoma'),
  ('Oregon',         'Oregon'),
  ('Pennsylvania',   'Pennsylvania'),
  ('Rhode Island',   'Rhode Island'),
  ('South Carolina', 'South Carolina'),
  ('South Dakota',   'South Dakota'),
  ('Tennessee',      'Tennessee'),
  ('Texas',          'Texas'),
  ('Utah',           'Utah'),
  ('Vermont',        'Vermont'),
  ('Virginia',       'Virginia'),
  ('Washington',     'Washington'),
  ('West Virginia',  'West Virginia'),
  ('Wisconsin',      'Wisconsin'),
  ('Wyoming',        'Wyoming'),
  -- IPDB typos
  ('NewYork',        'New York'),
  ('SouthCarolina',  'South Carolina')
) AS t(state_name, canonical_name);

-- Normalize manufacturer names by stripping business suffixes.
-- Mirrors normalize_manufacturer_name() in bulk_utils.py.
-- Applied repeatedly to handle compound suffixes like "Sega Enterprises, Ltd."
CREATE OR REPLACE MACRO normalize_mfr_name(name) AS (
  lower(trim(
    regexp_replace(
      regexp_replace(
        regexp_replace(name,
          ',?\s+(?:Manufacturing|Electronics|Industries|Enterprises|Games|Pinball|Technologies|Company|Corporation|Inc\.?|Ltd\.?|Co\.?|LLC|GmbH|S\.?A\.?|s\.?p\.?a\.?|Kabushikigaisha|Automaten)\s*$',
          '', 'i'),
        ',?\s+(?:Manufacturing|Electronics|Industries|Enterprises|Games|Pinball|Technologies|Company|Corporation|Inc\.?|Ltd\.?|Co\.?|LLC|GmbH|S\.?A\.?|s\.?p\.?a\.?|Kabushikigaisha|Automaten)\s*$',
        '', 'i'),
      ',?\s+(?:Manufacturing|Electronics|Industries|Enterprises|Games|Pinball|Technologies|Company|Corporation|Inc\.?|Ltd\.?|Co\.?|LLC|GmbH|S\.?A\.?|s\.?p\.?a\.?|Kabushikigaisha|Automaten)\s*$',
      '', 'i')
  ))
);

-- Country name normalization (IPDB inconsistencies)
CREATE OR REPLACE VIEW ref_country_normalization AS
SELECT * FROM (VALUES
  ('England',        'United Kingdom'),
  ('Britain',        'United Kingdom'),
  ('UK',             'United Kingdom'),
  ('U.K.',           'United Kingdom'),
  ('West Germany',   'Germany'),
  ('Holland',        'Netherlands'),
  ('The Netherlands','Netherlands'),
  ('R.O.C.',         'Taiwan')
) AS t(raw_country, normalized_country);

-- IPDB location overrides for misformatted manufacturer strings.
-- These have missing commas, semicolons, multi-city HQs, etc.
CREATE OR REPLACE VIEW ref_ipdb_location_overrides AS
SELECT * FROM (VALUES
  -- "Chicago Illinois" — missing comma
  (532, 'Chicago',          'Illinois',  'USA'),
  -- "Long Island City, Queens, New York" — Queens is a borough, not a state
  (607, 'Long Island City',  'New York',  'USA'),
  -- "Lincoln, Nebraska; Des Moines, Iowa" — two cities
  (764, 'Lincoln',           'Nebraska',  'USA'),
  -- "Youngstown, Ohio and New York City" — two cities
  (696, 'Youngstown',        'Ohio',      'USA'),
  -- "Madrid" — just a city, no country
  (439, 'Madrid',            NULL,        'Spain'),
  -- "Marcoussis and Paris, France" — dual city, use primary (Marcoussis is a Paris suburb)
  (364, 'Marcoussis',        NULL,        'France'),
  -- "Avenza, Massa-Carrera, Toscana, Italy" — Massa-Carrara is an Italian province, not a state
  (135, 'Avenza',            NULL,        'Italy')
) AS t(ipdb_manufacturer_id, headquarters_city, headquarters_state, headquarters_country);

------------------------------------------------------------
-- External source dumps (data/dump1/)
------------------------------------------------------------

-- Fandom wiki exports
CREATE OR REPLACE TABLE fandom_games AS
SELECT d.*
FROM (SELECT unnest(games) AS d FROM read_json_auto('data/dump1/fandom_games.json'));

CREATE OR REPLACE TABLE fandom_manufacturers AS
SELECT d.*
FROM (SELECT unnest(manufacturers) AS d FROM read_json_auto('data/dump1/fandom_manufacturers.json'));

CREATE OR REPLACE TABLE fandom_persons AS
SELECT d.*
FROM (SELECT unnest(persons) AS d FROM read_json_auto('data/dump1/fandom_persons.json'));

-- Pinball Map API exports
CREATE OR REPLACE TABLE pinballmap_machines AS
SELECT d.*
FROM (SELECT unnest(machines) AS d FROM read_json_auto('data/dump1/pinballmap_machines.json'));

CREATE OR REPLACE TABLE pinballmap_machine_groups AS
SELECT d.*
FROM (SELECT unnest(machine_groups) AS d FROM read_json_auto('data/dump1/pinballmap_machine_groups.json'));

-- OPDB (Open Pinball Database) exports
CREATE OR REPLACE TABLE opdb_groups AS
SELECT * FROM read_json_auto('data/dump1/opdb_export_groups.json');

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
FROM read_json_auto('data/dump1/opdb_export_machines.json');

-- IPDB (Internet Pinball Database) export
CREATE OR REPLACE TABLE ipdb_machines AS
SELECT d.*
FROM (
  SELECT unnest("Data") AS d
  FROM read_json_auto('data/dump1/ipdbdatabase.json', (maximum_object_size = 67108864))
);
