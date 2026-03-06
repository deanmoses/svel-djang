-- 01_raw.sql — Raw JSON reads and reference lookup tables
-- No business logic: just read_json_auto pass-throughs and static mappings.

------------------------------------------------------------
-- Canonical key macro (used in 02_staging and 03_catalog)
------------------------------------------------------------

CREATE OR REPLACE MACRO model_key(opdb_id, ipdb_id) AS
  COALESCE(opdb_id, 'ipdb:' || CAST(ipdb_id AS VARCHAR));

------------------------------------------------------------
-- External source dumps (data/dump1/)
------------------------------------------------------------

-- Fandom wiki exports
CREATE OR REPLACE VIEW fandom_games AS
SELECT d.*
FROM (SELECT unnest(games) AS d FROM read_json_auto('data/dump1/fandom_games.json'));

CREATE OR REPLACE VIEW fandom_manufacturers AS
SELECT d.*
FROM (SELECT unnest(manufacturers) AS d FROM read_json_auto('data/dump1/fandom_manufacturers.json'));

CREATE OR REPLACE VIEW fandom_persons AS
SELECT d.*
FROM (SELECT unnest(persons) AS d FROM read_json_auto('data/dump1/fandom_persons.json'));

-- Pinball Map API exports
CREATE OR REPLACE VIEW pinballmap_machines AS
SELECT
  d.id,
  d."name",
  d.is_active,
  d.created_at,
  d.updated_at,
  d.ipdb_link,
  d."year",
  d.manufacturer,
  d.machine_group_id,
  d.ipdb_id,
  d.opdb_id,
  d.opdb_img,
  d.opdb_img_height,
  d.opdb_img_width,
  d.machine_type,
  d.machine_display,
  d.ic_eligible,
  d.kineticist_url
FROM (SELECT unnest(machines) AS d FROM read_json_auto('data/dump1/pinballmap_machines.json'));

CREATE OR REPLACE VIEW pinballmap_machine_groups AS
SELECT d.id, d."name", d.created_at, d.updated_at
FROM (SELECT unnest(machine_groups) AS d FROM read_json_auto('data/dump1/pinballmap_machine_groups.json'));

-- OPDB (Open Pinball Database) exports
CREATE OR REPLACE VIEW opdb_groups AS
SELECT * FROM read_json_auto('data/dump1/opdb_export_groups.json');

CREATE OR REPLACE VIEW opdb_machines_raw AS
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
CREATE OR REPLACE VIEW ipdb_machines_raw AS
SELECT d.*
FROM (
  SELECT unnest("Data") AS d
  FROM read_json_auto('data/dump1/ipdbdatabase.json', (maximum_object_size = 67108864))
);

------------------------------------------------------------
-- Pinbase curated data (data/*.json)
------------------------------------------------------------

CREATE OR REPLACE VIEW pinbase_cabinets AS
SELECT * FROM read_json_auto('data/cabinets.json');

CREATE OR REPLACE VIEW pinbase_conversions AS
SELECT * FROM read_json_auto('data/conversions.json');

CREATE OR REPLACE VIEW pinbase_corporate_entities AS
SELECT * FROM read_json_auto('data/corporate_entities.json');

CREATE OR REPLACE VIEW pinbase_credits AS
SELECT * FROM read_json_auto('data/credits.json', (union_by_name = CAST('t' AS BOOLEAN)));

CREATE OR REPLACE VIEW pinbase_display_subtypes AS
SELECT * FROM read_json_auto('data/display_subtypes.json');

CREATE OR REPLACE VIEW pinbase_display_types AS
SELECT * FROM read_json_auto('data/display_types.json');

CREATE OR REPLACE VIEW pinbase_franchises AS
SELECT * FROM read_json_auto('data/franchises.json');

CREATE OR REPLACE VIEW pinbase_game_formats AS
SELECT * FROM read_json_auto('data/game_formats.json');

CREATE OR REPLACE VIEW pinbase_gameplay_features AS
SELECT * FROM read_json_auto('data/gameplay_features.json');

CREATE OR REPLACE VIEW pinbase_manufacturers AS
SELECT * FROM read_json_auto('data/manufacturers.json');

CREATE OR REPLACE VIEW pinbase_models AS
SELECT * FROM read_json_auto('data/models.json', (union_by_name = CAST('t' AS BOOLEAN)));

CREATE OR REPLACE VIEW pinbase_people AS
SELECT * FROM read_json_auto('data/people.json', (union_by_name = CAST('t' AS BOOLEAN)));

CREATE OR REPLACE VIEW pinbase_productions AS
SELECT * FROM read_json_auto('data/productions.json', (union_by_name = CAST('t' AS BOOLEAN)));

CREATE OR REPLACE VIEW pinbase_series AS
SELECT * FROM read_json_auto('data/series.json');

CREATE OR REPLACE VIEW pinbase_systems AS
SELECT * FROM read_json_auto('data/systems.json');

CREATE OR REPLACE VIEW pinbase_tags AS
SELECT * FROM read_json_auto('data/tags.json');

CREATE OR REPLACE VIEW pinbase_technology_generations AS
SELECT * FROM read_json_auto('data/technology_generations.json');

CREATE OR REPLACE VIEW pinbase_technology_subgenerations AS
SELECT * FROM read_json_auto('data/technology_subgenerations.json');

CREATE OR REPLACE VIEW pinbase_tiers AS
SELECT * FROM read_json_auto('data/tiers.json', (union_by_name = CAST('t' AS BOOLEAN)));

CREATE OR REPLACE VIEW pinbase_titles AS
SELECT * FROM read_json_auto('data/titles.json', (union_by_name = CAST('t' AS BOOLEAN)));

------------------------------------------------------------
-- Reference lookup tables (replace inline CASE blocks)
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

-- OPDB feature string -> tag slug
CREATE OR REPLACE VIEW ref_feature_tag AS
SELECT * FROM (VALUES
  ('Home model',      'home-use'),
  ('Widebody',        'widebody'),
  ('Remake',          'remake'),
  ('Conversion kit',  'conversion-kit'),
  ('Export edition',  'export')
) AS t(feature, slug);

-- IPDB credit column name -> display role
CREATE OR REPLACE VIEW ref_credit_role AS
SELECT * FROM (VALUES
  ('DesignBy',          'Design'),
  ('ArtBy',             'Art'),
  ('MusicBy',           'Music'),
  ('SoundBy',           'Sound'),
  ('SoftwareBy',        'Software'),
  ('MechanicsBy',       'Mechanics'),
  ('DotsAnimationBy',   'Dots/Animation')
) AS t(column_name, role_name);

-- US states (for IPDB manufacturer HQ location parsing)
CREATE OR REPLACE VIEW ref_us_states AS
SELECT * FROM (VALUES
  ('Alabama'), ('Alaska'), ('Arizona'), ('Arkansas'), ('California'),
  ('Colorado'), ('Connecticut'), ('Delaware'), ('Florida'), ('Georgia'),
  ('Hawaii'), ('Idaho'), ('Illinois'), ('Indiana'), ('Iowa'),
  ('Kansas'), ('Kentucky'), ('Louisiana'), ('Maine'), ('Maryland'),
  ('Massachusetts'), ('Michigan'), ('Minnesota'), ('Mississippi'), ('Missouri'),
  ('Montana'), ('Nebraska'), ('Nevada'), ('New Hampshire'), ('New Jersey'),
  ('New Mexico'), ('New York'), ('North Carolina'), ('North Dakota'), ('Ohio'),
  ('Oklahoma'), ('Oregon'), ('Pennsylvania'), ('Rhode Island'), ('South Carolina'),
  ('South Dakota'), ('Tennessee'), ('Texas'), ('Utah'), ('Vermont'),
  ('Virginia'), ('Washington'), ('West Virginia'), ('Wisconsin'), ('Wyoming'),
  -- Typos found in IPDB data
  ('NewYork'), ('SouthCarolina')
) AS t(state_name);
