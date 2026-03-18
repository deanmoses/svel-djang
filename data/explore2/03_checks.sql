-- 04_checks.sql — Integrity checks on pinbase data.
-- Depends on: 01_raw.sql, 02_staging.sql
-- Aborts with non-zero exit code if any hard violations are found.

CREATE TEMP TABLE IF NOT EXISTS _violations (check_name VARCHAR, detail VARCHAR);
CREATE TEMP TABLE IF NOT EXISTS _warnings (check_name VARCHAR, cnt BIGINT);

------------------------------------------------------------
-- Hard failures (structural integrity)
------------------------------------------------------------

-- Duplicate slugs
INSERT INTO _violations
SELECT 'duplicate_model_slug', slug
FROM models GROUP BY slug HAVING count(*) > 1;

INSERT INTO _violations
SELECT 'duplicate_title_slug', slug
FROM titles GROUP BY slug HAVING count(*) > 1;

INSERT INTO _violations
SELECT 'duplicate_manufacturer_slug', slug
FROM manufacturers GROUP BY slug HAVING count(*) > 1;

-- Duplicate external IDs
INSERT INTO _violations
SELECT 'duplicate_model_opdb_id', opdb_id
FROM models WHERE opdb_id IS NOT NULL
GROUP BY opdb_id HAVING count(*) > 1;

INSERT INTO _violations
SELECT 'duplicate_model_ipdb_id', CAST(ipdb_id AS VARCHAR)
FROM models WHERE ipdb_id IS NOT NULL
GROUP BY ipdb_id HAVING count(*) > 1;

INSERT INTO _violations
SELECT 'duplicate_title_opdb_group_id', opdb_group_id
FROM titles WHERE opdb_group_id IS NOT NULL
GROUP BY opdb_group_id HAVING count(*) > 1;

-- Orphan references: model -> title
INSERT INTO _violations
SELECT 'orphan_model_title', m.slug || ' -> ' || m.title_slug
FROM models AS m
WHERE m.title_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM titles AS t WHERE t.slug = m.title_slug);

-- Orphan references: title -> franchise
INSERT INTO _violations
SELECT 'orphan_title_franchise', t.slug || ' -> ' || t.franchise_slug
FROM titles AS t
WHERE t.franchise_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM franchises AS f WHERE f.slug = t.franchise_slug);

-- Orphan references: title -> series
INSERT INTO _violations
SELECT 'orphan_title_series', t.slug || ' -> ' || t.series_slug
FROM titles AS t
WHERE t.series_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM series AS s WHERE s.slug = t.series_slug);

-- Orphan references: model -> manufacturer
INSERT INTO _violations
SELECT 'orphan_model_manufacturer', m.slug || ' -> ' || m.manufacturer_slug
FROM models AS m
WHERE m.manufacturer_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM manufacturers AS mfr WHERE mfr.slug = m.manufacturer_slug);

-- Orphan references: model -> cabinet
INSERT INTO _violations
SELECT 'orphan_model_cabinet', m.slug || ' -> ' || m.cabinet_slug
FROM models AS m
WHERE m.cabinet_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cabinets AS c WHERE c.slug = m.cabinet_slug);

-- Orphan references: model -> technology_generation
INSERT INTO _violations
SELECT 'orphan_model_technology_generation', m.slug || ' -> ' || m.technology_generation_slug
FROM models AS m
WHERE m.technology_generation_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM technology_generations AS tg WHERE tg.slug = m.technology_generation_slug);

-- Orphan references: model -> display_type
INSERT INTO _violations
SELECT 'orphan_model_display_type', m.slug || ' -> ' || m.display_type_slug
FROM models AS m
WHERE m.display_type_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM display_types AS dt WHERE dt.slug = m.display_type_slug);

-- Orphan references: model -> system
INSERT INTO _violations
SELECT 'orphan_model_system', m.slug || ' -> ' || m.system_slug
FROM models AS m
WHERE m.system_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM systems AS s WHERE s.slug = m.system_slug);

-- Orphan references: variant_of -> model
INSERT INTO _violations
SELECT 'orphan_variant_of', m.slug || ' -> ' || m.variant_of
FROM models AS m
WHERE m.variant_of IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM models AS m2 WHERE m2.slug = m.variant_of);

-- Orphan references: converted_from -> model
INSERT INTO _violations
SELECT 'orphan_converted_from', m.slug || ' -> ' || m.converted_from
FROM models AS m
WHERE m.converted_from IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM models AS m2 WHERE m2.slug = m.converted_from);

-- Orphan references: remake_of -> model
INSERT INTO _violations
SELECT 'orphan_remake_of', m.slug || ' -> ' || m.remake_of
FROM models AS m
WHERE m.remake_of IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM models AS m2 WHERE m2.slug = m.remake_of);

-- Orphan references: credit person_slug -> people
INSERT INTO _violations
SELECT 'orphan_credit_person', c.model_slug || ' -> ' || c.person_slug
FROM pinbase_credits AS c
WHERE NOT EXISTS (SELECT 1 FROM people AS p WHERE p.slug = c.person_slug);

-- Orphan references: credit role -> credit_roles
INSERT INTO _violations
SELECT 'orphan_credit_role', c.model_slug || ' -> ' || c.role
FROM pinbase_credits AS c
WHERE NOT EXISTS (SELECT 1 FROM credit_roles AS cr WHERE cr.name = c.role);

-- Self-referential variant_of
INSERT INTO _violations
SELECT 'self_variant_of', slug
FROM models WHERE variant_of = slug;

-- Chained variant_of (A -> B where B also has variant_of)
INSERT INTO _violations
SELECT 'chained_variant_of', a.slug || ' -> ' || a.variant_of || ' -> ' || b.variant_of
FROM models AS a
JOIN models AS b ON a.variant_of = b.slug
WHERE b.variant_of IS NOT NULL;

-- Pinbase model references a non-physical OPDB record (physical_machine=0)
INSERT INTO _violations
SELECT 'non_physical_opdb_ref', m.slug || ' (' || m.opdb_id || ')'
FROM models AS m
JOIN opdb_machines AS om ON m.opdb_id = om.opdb_id
WHERE om.physical_machine = 0;

-- Corporate entity: manufacturer_slug is required
INSERT INTO _violations
SELECT 'ce_missing_manufacturer', slug
FROM corporate_entities WHERE manufacturer_slug IS NULL;

-- Corporate entity: duplicate slugs
INSERT INTO _violations
SELECT 'duplicate_ce_slug', slug
FROM corporate_entities GROUP BY slug HAVING count(*) > 1;

-- Orphan references: corporate entity -> manufacturer
INSERT INTO _violations
SELECT 'orphan_ce_manufacturer', ce.slug || ' -> ' || ce.manufacturer_slug
FROM corporate_entities AS ce
WHERE ce.manufacturer_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM manufacturers AS m WHERE m.slug = ce.manufacturer_slug);

-- Every manufacturer must have at least one corporate entity
INSERT INTO _violations
SELECT 'orphan_manufacturer', m.slug
FROM manufacturers AS m
WHERE NOT EXISTS (SELECT 1 FROM corporate_entities AS ce WHERE ce.manufacturer_slug = m.slug);

-- More corporate entities than manufacturers
INSERT INTO _violations
SELECT 'fewer_ces_than_manufacturers',
  'corporate_entities=' || (SELECT count(*) FROM corporate_entities)
  || ' manufacturers=' || (SELECT count(*) FROM manufacturers)
WHERE (SELECT count(*) FROM corporate_entities) <= (SELECT count(*) FROM manufacturers);

-- Every IPDB machine has a pinbase model
INSERT INTO _violations
SELECT 'ipdb_machine_missing_model', CAST(i.IpdbId AS VARCHAR) || ' ' || i.Title
FROM ipdb_machines AS i
WHERE NOT EXISTS (SELECT 1 FROM models AS m WHERE m.ipdb_id = i.IpdbId);

-- Every OPDB physical machine has a pinbase model
INSERT INTO _violations
SELECT 'opdb_machine_missing_model', om.opdb_id || ' ' || om.name
FROM opdb_machines AS om
WHERE om.is_machine = true AND om.physical_machine = 1
  AND NOT EXISTS (SELECT 1 FROM models AS m WHERE m.opdb_id = om.opdb_id);

-- No empty names on any entity
INSERT INTO _violations
SELECT 'empty_name_model', slug FROM models WHERE name IS NULL OR trim(name) = '';
INSERT INTO _violations
SELECT 'empty_name_title', slug FROM titles WHERE name IS NULL OR trim(name) = '';
INSERT INTO _violations
SELECT 'empty_name_manufacturer', slug FROM manufacturers WHERE name IS NULL OR trim(name) = '';
INSERT INTO _violations
SELECT 'empty_name_ce', slug FROM corporate_entities WHERE name IS NULL OR trim(name) = '';
INSERT INTO _violations
SELECT 'empty_name_person', slug FROM people WHERE name IS NULL OR trim(name) = '';
INSERT INTO _violations
SELECT 'empty_name_theme', slug FROM themes WHERE name IS NULL OR trim(name) = '';

-- All slugs must be valid format (lowercase, hyphens, digits only)
INSERT INTO _violations
SELECT 'invalid_slug_model', slug FROM models WHERE slug != regexp_replace(slug, '[^a-z0-9-]', '', 'g') OR slug = '';
INSERT INTO _violations
SELECT 'invalid_slug_title', slug FROM titles WHERE slug != regexp_replace(slug, '[^a-z0-9-]', '', 'g') OR slug = '';
INSERT INTO _violations
SELECT 'invalid_slug_manufacturer', slug FROM manufacturers WHERE slug != regexp_replace(slug, '[^a-z0-9-]', '', 'g') OR slug = '';
INSERT INTO _violations
SELECT 'invalid_slug_ce', slug FROM corporate_entities WHERE slug != regexp_replace(slug, '[^a-z0-9-]', '', 'g') OR slug = '';
INSERT INTO _violations
SELECT 'invalid_slug_person', slug FROM people WHERE slug != regexp_replace(slug, '[^a-z0-9-]', '', 'g') OR slug = '';

-- Model year is reasonable (1850–2030)
INSERT INTO _violations
SELECT 'model_year_out_of_range', slug || ' year=' || year
FROM models WHERE year IS NOT NULL AND (year < 1850 OR year > 2030);

-- Model month is 1–12 when present
INSERT INTO _violations
SELECT 'model_month_out_of_range', slug || ' month=' || month
FROM models WHERE month IS NOT NULL AND (month < 1 OR month > 12);

-- Production quantity is positive when present
INSERT INTO _violations
SELECT 'model_negative_production', slug || ' qty=' || production_quantity
FROM models WHERE production_quantity IS NOT NULL AND TRY_CAST(production_quantity AS INTEGER) <= 0;

-- Corporate entity ipdb_manufacturer_id is unique
INSERT INTO _violations
SELECT 'duplicate_ce_ipdb_manufacturer_id', CAST(ipdb_manufacturer_id AS VARCHAR)
FROM corporate_entities WHERE ipdb_manufacturer_id IS NOT NULL
GROUP BY ipdb_manufacturer_id HAVING count(*) > 1;

-- No two corporate entities share the same (name, manufacturer_slug) pair
-- (unless explicitly approved)
INSERT INTO _violations
SELECT 'duplicate_ce_name_manufacturer', name || ' -> ' || manufacturer_slug
FROM corporate_entities
WHERE (name, manufacturer_slug) NOT IN (
  -- Approved: two distinct companies with the same name in different cities
  ('Automatic Games Company', 'automatic-games-company'),
  ('Shyvers Manufacturing Company', 'shyvers')
)
GROUP BY name, manufacturer_slug HAVING count(*) > 1;

-- All models must point at a title (MachineModel.Title is required)
INSERT INTO _violations
SELECT 'model_missing_title', slug
FROM models WHERE title_slug IS NULL;

-- More models than titles
INSERT INTO _violations
SELECT 'fewer_models_than_titles',
  'models=' || (SELECT count(*) FROM models)
  || ' titles=' || (SELECT count(*) FROM titles)
WHERE (SELECT count(*) FROM models) <= (SELECT count(*) FROM titles);

-- Every title must have at least one model (no orphan titles)
INSERT INTO _violations
SELECT 'orphan_title', t.slug
FROM titles AS t
WHERE NOT EXISTS (SELECT 1 FROM models AS m WHERE m.title_slug = t.slug);

-- OPDB/Pinbase ipdb_id agreement: when a model has both an ipdb_id and an opdb_id,
-- and OPDB also has an ipdb_id for that machine, they must agree.
INSERT INTO _violations
SELECT 'ipdb_id_disagreement',
  m.slug || ' pinbase=' || m.ipdb_id || ' opdb=' || om.ipdb_id
FROM models AS m
JOIN opdb_machines AS om ON m.opdb_id = om.opdb_id
WHERE m.ipdb_id IS NOT NULL
  AND om.ipdb_id IS NOT NULL
  AND m.ipdb_id != om.ipdb_id;

-- Source dump integrity: every OPDB record must have an opdb_id
INSERT INTO _violations
SELECT 'opdb_record_missing_id', name
FROM opdb_machines WHERE opdb_id IS NULL;

-- Source dump integrity: every IPDB record must have an IpdbId
INSERT INTO _violations
SELECT 'ipdb_record_missing_id', Title
FROM ipdb_machines WHERE IpdbId IS NULL;

------------------------------------------------------------
-- Soft warnings (data quality)
------------------------------------------------------------

-- Pinbase references external IDs not in our (possibly stale) dumps
INSERT INTO _warnings
SELECT 'pinbase_opdb_id_not_in_dump', count(*)
FROM models AS m
WHERE m.opdb_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM opdb_machines AS o WHERE o.opdb_id = m.opdb_id);

INSERT INTO _warnings
SELECT 'pinbase_ipdb_id_not_in_dump', count(*)
FROM models AS m
WHERE m.ipdb_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM ipdb_machines AS i WHERE i.IpdbId = m.ipdb_id);

INSERT INTO _warnings
SELECT 'models_missing_manufacturer', count(*)
FROM models WHERE manufacturer_slug IS NULL;

INSERT INTO _warnings
SELECT 'titles_missing_opdb_group', count(*)
FROM titles WHERE opdb_group_id IS NULL;

INSERT INTO _warnings
SELECT 'conversion_without_source', count(*)
FROM models WHERE is_conversion AND converted_from IS NULL;

------------------------------------------------------------
-- Report
------------------------------------------------------------

SELECT 'WARNING: ' || check_name || ' (' || cnt || ' rows)'
FROM _warnings WHERE cnt > 0;

SELECT CASE
  WHEN count(*) > 0
  THEN error(count(*) || ' contract violation(s) found. Run: SELECT * FROM _violations')
  ELSE 'All checks passed'
END FROM _violations;
