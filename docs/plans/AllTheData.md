# All The Data: Scaling Pinbase to Full Catalog Coverage

## Goal

Curate every machine in the catalog (~7,000 models, ~1,000 manufacturers, ~1,000+ people) with:
- AI-generated descriptions for every entity
- All OPDB/IPDB facts surfaced as editorial claims
- Bios for people (with birth/death, hometown)
- Manufacturer descriptions with corporate entity history

## Problem

The current `data/*.json` files work well at today's scale (390 models, 59 manufacturers, 19 people) but will not survive full coverage. A single `models.json` with 7,000 fully-described records would be 200K+ lines — impossible to diff, review, or edit without blowing context windows.

## Strategy: Split Large Entities into Per-Record Files

### New file structure

```
data/
  titles/                              # ~1,000 files, one per game
    medieval-madness.json               # title metadata + all its models + credits
    ac-dc.json
    ...
  people/                              # ~1,000 files, one per person
    steve-ritchie.json                  # bio, birth/death, hometown, aliases
    brian-eddy.json
    ...
  manufacturers/                       # ~800 files, one per manufacturer
    williams.json                       # description + corporate entities
    bally.json
    ...

  # Small taxonomy files stay flat (unchanged)
  cabinets.json
  credit_roles.json
  display_types.json
  display_subtypes.json
  franchises.json
  game_formats.json
  gameplay_features.json
  golden_records.json
  series.json
  systems.json
  tags.json
  technology_generations.json
  technology_subgenerations.json

  # These flat files are RETIRED (absorbed into per-record files)
  # models.json        → data/titles/*/models[]
  # titles.json        → data/titles/*/title
  # credits.json       → data/titles/*/models[].credits[]
  # people.json        → data/people/*.json
  # manufacturers.json → data/manufacturers/*.json
  # corporate_entities.json → data/manufacturers/*.json corporate_entities[]
```

### Per-title file format

Each file in `data/titles/` is a self-contained record for one game:

```json
{
  "title": {
    "slug": "medieval-madness",
    "name": "Medieval Madness",
    "opdb_group_id": "GrB14",
    "franchise_slug": "medieval-madness",
    "abbreviations": ["MM"]
  },
  "models": [
    {
      "slug": "medieval-madness",
      "name": "Medieval Madness",
      "opdb_id": "GrB14-M0Ry6",
      "ipdb_id": 4032,
      "display_type": "dot-matrix",
      "description": "...",
      "credits": [
        { "person": "brian-eddy", "role": "Design" },
        { "person": "greg-freres", "role": "Art" },
        { "person": "loren-silber", "role": "Software" }
      ]
    },
    {
      "slug": "medieval-madness-remake",
      "name": "Medieval Madness (Remake)",
      "variant_of": "medieval-madness",
      "opdb_id": "GrB14-MnRe1",
      "is_remake": true,
      "remake_of": "medieval-madness",
      "description": "...",
      "credits": []
    }
  ]
}
```

### Per-person file format

```json
{
  "slug": "steve-ritchie",
  "name": "Steve Ritchie",
  "aliases": ["Steve Richie"],
  "born": "1951-05-05",
  "died": null,
  "hometown": "San Jose, California",
  "bio": "..."
}
```

### Per-manufacturer file format

```json
{
  "slug": "williams",
  "name": "Williams",
  "description": "...",
  "corporate_entities": [
    {
      "name": "Williams Manufacturing Company",
      "year_start": 1943,
      "year_end": 1964,
      "headquarters_city": "Chicago",
      "headquarters_state": "Illinois",
      "headquarters_country": "USA"
    },
    {
      "name": "Williams Electronics",
      "year_start": 1967,
      "year_end": 1999,
      "headquarters_city": "Chicago",
      "headquarters_state": "Illinois",
      "headquarters_country": "USA"
    }
  ]
}
```

## Implementation Plan

### Phase 1: Schema and seed generation

1. **Write new JSON schemas** for the three per-record file formats:
   - `data/schemas/title_file.schema.json` (title + models[] + credits[])
   - `data/schemas/person_file.schema.json` (person with bio, born, died, hometown)
   - `data/schemas/manufacturer_file.schema.json` (manufacturer with corporate_entities[])

2. **Write a DuckDB seed script** (`scripts/seed_title_files.sql` or Python) that:
   - Reads all existing `data/*.json` flat files
   - Reads OPDB/IPDB dumps from `data/dump1/` (when available)
   - Joins models to titles, credits to models, corporate entities to manufacturers
   - Exports one JSON file per title into `data/titles/`
   - Exports one JSON file per person into `data/people/`
   - Exports one JSON file per manufacturer into `data/manufacturers/`
   - For entities without existing pinbase claims, creates skeleton records with OPDB/IPDB facts only (no description yet)

3. **Validate the seed output** — run the existing `04_checks.sql` contract assertions against the new file structure to ensure nothing was lost.

### Phase 2: Update consumers to read from the new structure

4. **Update DuckDB explore layer** (`data/explore/01_raw.sql`):
   - Replace `read_json_auto('data/models.json')` with glob reads:
     ```sql
     -- Title records
     CREATE OR REPLACE VIEW pinbase_titles AS
     SELECT t.* FROM (
       SELECT json_extract(content, '$.title') AS t
       FROM read_json_auto('data/titles/*.json')
     );

     -- Model records (unnested from per-title files)
     CREATE OR REPLACE VIEW pinbase_models AS
     SELECT m.* FROM (
       SELECT unnest(json_extract(content, '$.models')) AS m
       FROM read_json_auto('data/titles/*.json')
     );
     ```
   - Similarly for people, manufacturers, corporate entities
   - DuckDB handles file globs natively — no code changes needed beyond the view definitions

5. **Update Django ingestion commands**:
   - `ingest_pinbase_titles.py` — read from `data/titles/*.json`, extract `title` object from each
   - `ingest_pinbase_models.py` — read from `data/titles/*.json`, extract `models[]` from each
   - `ingest_pinbase_people.py` — read from `data/people/*.json`
   - `ingest_pinbase_manufacturers.py` — read from `data/manufacturers/*.json`
   - `ingest_pinbase_corporate_entities.py` — read from `data/manufacturers/*.json`, extract `corporate_entities[]`
   - `ingest_pinbase_series.py` — credits move from `data/credits.json` into model records; series-level credits need a migration path (perhaps a `credits` field on the title or kept as a separate small file until absorbed)
   - Pattern: replace `json.load(open('data/X.json'))` with `for path in sorted(Path('data/X/').glob('*.json')): ...`

6. **Update JSON schema validation** — if there's a CI step that validates `data/*.json` against `data/schemas/`, update it to validate the new file formats.

7. **Delete retired flat files**: `models.json`, `titles.json`, `credits.json`, `people.json`, `manufacturers.json`, `corporate_entities.json`.

### Phase 3: AI-generated content

8. **Write a generation script** (Python, using Claude API) that:
   - Reads a title file from `data/titles/`
   - Gathers context: OPDB/IPDB facts, Fandom wikitext, manufacturer info, credits
   - Calls Claude to generate a description for each model that lacks one
   - Writes the description back into the title file
   - Can run in batch mode (e.g., "generate descriptions for all titles starting with A-C")
   - Supports dry-run (print what would be written) and write mode

9. **Same pattern for people bios**: read person file, gather context (which machines they worked on, Fandom/Wikipedia info), generate bio, write back.

10. **Same for manufacturer descriptions**: gather corporate entity history, notable machines, generate description, write back.

### Phase 4: Validation and review workflow

11. **Extend `04_checks.sql`** to validate the new file structure:
    - Every model references a valid person slug in credits
    - Every title file's models[].title matches the title.slug
    - No orphan person/manufacturer files (referenced by at least one model or credit)

12. **Git-based review workflow**:
    - AI generates a batch → creates a branch → PR for review
    - Git diff shows exactly which title/person/manufacturer files changed
    - Reviewer reads individual files, not a 200K-line monolith

## What stays the same

- **DuckDB exploration layer**: same SQL, just updated view definitions
- **Django ingestion pipeline**: same commands, same claim system, just reading from directories instead of single files
- **Django models and API**: completely unchanged
- **Svelte frontend**: completely unchanged
- **Claims/provenance system**: completely unchanged — files are still the editorial source, Django still resolves claims by priority
- **Small taxonomy files**: no change at all

## Sizing estimates

| Entity | Files | Lines per file | Total lines |
|--------|-------|---------------|-------------|
| Titles (with models + credits) | ~1,000 | 50–200 | ~100K |
| People | ~1,000 | 15–30 | ~25K |
| Manufacturers | ~800 | 20–80 | ~30K |
| Taxonomy (flat files) | ~13 | 10–120 | ~1K |

Total: ~2,800 files, ~156K lines. Each individual file fits comfortably in an AI context window. Git handles this file count trivially.

## Open questions

1. **Series-level credits**: Currently `credits.json` links credits to series, not models. When credits move into model records, do series-level credits get duplicated onto every model in the series, or do we keep a `credits` field on the title object for shared credits?

2. **Titles without OPDB groups**: Some pinbase titles exist independently of OPDB. The seed script needs to handle these (they already have slugs but no `opdb_group_id`).

3. **IPDB-only machines**: ~2,000+ machines exist only in IPDB with no OPDB cross-reference. The seed script should create title files for these too, using synthetic title slugs.

4. **Generation batching**: How large should AI generation batches be? By manufacturer? By decade? Alphabetically? Probably by manufacturer or era, since that gives the AI useful context across a batch.

5. **Description style guide**: Need a consistent voice/style for AI-generated descriptions. The existing manufacturer descriptions in `manufacturers.json` (e.g., Bally, Atari, American Pinball) are excellent examples — they use wikilinks like `[[title:medieval-madness]]` and `[[person:steve-ritchie]]`, read as narrative history, and mix technical and cultural context. Document this as a prompt template.
