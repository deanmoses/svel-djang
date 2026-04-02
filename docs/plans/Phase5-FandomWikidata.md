# Phase 5: Fandom & Wikidata Adapter Conversion

Convert `ingest_fandom`, `ingest_wikidata`, and `ingest_wikidata_manufacturers` from legacy imperative commands to plan/apply adapters.

## Context

Phases 1–4 of [ClaimsNextGen.md](ClaimsNextGen.md) are complete. The apply layer, OPDB adapter, IPDB adapter, entity lifecycle, DB-level validation, and relationship claim PK migration are all implemented. Two adapters remain before `ingest_pinbase` (the compound plan).

Reference implementations:

- **IPDB** (`catalog/ingestion/ipdb/adapter.py`) — multi-entity, `identity_refs`, most complex
- **OPDB** (`catalog/ingestion/opdb/adapter.py`) — single-entity, simpler

## Design Decisions

### Three separate plans for Fandom (not one combined plan)

The Fandom command currently processes three independent data streams (games/credits, persons, manufacturers) from separate source pages with separate dump files. Rather than combining them into one `IngestPlan`, each becomes its own `build_fandom_*_plan()` → `apply_plan()` cycle.

**Why three plans wins:**

1. **Fixes the credit gap bug.** The current command processes credits first (only matching existing persons), then creates new persons — so newly-created persons never get credit claims in the same run. With three plans applied in order (persons → credits → manufacturers), person creation commits before the credits plan runs. The credits plan sees the freshly-created persons and emits their credit claims. No `identity_refs` needed, no second run required.

2. **Simpler to reason about.** Each plan has one entity type or one concern. No coordinating three unrelated datasets in a single plan.

3. **Independent failure.** If the manufacturer phase fails, credits and persons already committed. These are independent data streams, so partial success is acceptable.

**Drawback:** Three `IngestRun` audit records instead of one. Three transactions instead of one (but partial success is fine for independent streams).

### Plan ordering within the command

The management command applies plans in this order:

1. **Persons plan** — parse games data to learn which person names appear in credits. Create missing Person records. Assert name/slug/bio claims on all matched+created persons. Apply. Persons now exist in DB.
2. **Credits plan** — all persons (including freshly created ones) are findable. Build credit claims on MachineModel for matched (game, person, role) triples. Apply.
3. **Manufacturers plan** — match manufacturers, assert scalar claims. Independent of 1 and 2. Apply.

### Sweep removal (additive-only)

Both Fandom and Wikidata currently use `sweep_field="credit"` + `authoritative_scope` for credit claims. Per the [additive-only design principle](ClaimsNextGen.md#additive-only-ingest-near-term), sweep is dropped. Stale credits from these sources won't be automatically deactivated. This matches the IPDB conversion.

### `wikidata_id` via claims only (no direct writes)

Both Wikidata commands currently do a dual write: assert a `wikidata_id` claim AND set `person.wikidata_id` / `mfr.wikidata_id` directly. The Person model even comments "direct field, not a claim" — but `wikidata_id` is NOT in `claims_exempt`, so `get_claim_fields()` treats it as claim-controlled.

The plan/apply conversion drops the direct write. `wikidata_id` is asserted as a claim; the resolver materialises it. This is consistent with the "one write path" principle and eliminates the dual-write inconsistency. Remove the misleading comment on `Person.wikidata_id`.

### Wikidata person + manufacturer share a source

Both `ingest_wikidata` and `ingest_wikidata_manufacturers` use the same `Source(slug="wikidata")`. They become two build functions in the same adapter module (`catalog/ingestion/wikidata/adapter.py`), each producing its own `IngestPlan`.

## File Layout

```text
catalog/ingestion/
  fandom/
    __init__.py
    adapter.py          # build_fandom_persons_plan(), build_fandom_credits_plan(), build_fandom_manufacturers_plan()
  wikidata/
    __init__.py
    adapter.py          # build_wikidata_persons_plan(), build_wikidata_manufacturers_plan()
  fandom_wiki.py        # Existing parsing code — untouched
  wikidata_sparql.py    # Existing parsing code — untouched

catalog/management/commands/
  ingest_fandom.py      # Thin wrapper: fetch/dump, parse, build plans → apply_plan(), print report
  ingest_wikidata.py    # Thin wrapper: fetch/dump, parse, build plan → apply_plan(), print report
  ingest_wikidata_manufacturers.py  # Thin wrapper: fetch/dump, parse, build plan → apply_plan(), print report

catalog/tests/
  test_fandom_adapter.py              # NEW: plan-boundary tests
  test_wikidata_adapter.py            # NEW: plan-boundary tests
  test_wikidata_manufacturers_adapter.py  # NEW: plan-boundary tests
  test_ingest_fandom.py               # Existing integration tests — updated
  test_ingest_wikidata.py             # Existing integration tests — updated
  test_ingest_wikidata_manufacturers.py  # Existing integration tests — updated
```

## Adapter Details

### 1. `ingest_wikidata_manufacturers` (simplest — implement first)

**Entity types:** Manufacturer (match-only, no creation)

**Reconciliation:** `ManufacturerResolver` chain: QID match → exact name → corporate entity → normalized name. Same as current.

**Claims asserted on Manufacturer:**

- `wikidata_id` (scalar)
- `wikidata.description` (extra-data)
- `logo_url` (scalar)
- `website` (scalar)
- `name` (scalar — needed so resolver doesn't blank it)

**What changes from current:**

- No direct `mfr.wikidata_id = wm.qid` write — claim-only
- No `resolve_all_entities()` call — apply layer handles resolution
- `IngestRun` audit trail created automatically
- `--dry-run` flag added

**`build_wikidata_manufacturers_plan()` signature:**

```python
def build_wikidata_manufacturers_plan(
    wikidata_manufacturers: list[WikidataManufacturer],
    source: Source,
    input_fingerprint: str,
) -> IngestPlan:
```

### 2. `ingest_wikidata` (persons + credits)

**Entity types:** Person (match-only, no creation), MachineModel (match-only for credits)

**Reconciliation:** `build_person_lookup()` for exact name match. Same as current. Confidence scoring is logging-only — not used for claim decisions.

**Claims asserted on Person:**

- `wikidata_id`, `name` (scalar)
- `wikidata.description` (extra-data)
- `birth_year`, `birth_month`, `birth_day` (scalar, precision-gated)
- `death_year`, `death_month`, `death_day` (scalar, precision-gated)
- `birth_place`, `nationality`, `photo_url` (scalar)

**Claims asserted on MachineModel:**

- `credit` (relationship: `{person: PK, role: PK}`)

**What changes from current:**

- No direct `person.wikidata_id = wp.qid` write — claim-only
- No `resolve_all_entities()` / `resolve_all_credits()` calls — apply layer handles resolution
- Sweep dropped for credit claims (additive-only)
- `IngestRun` audit trail created automatically
- `--dry-run` flag added

**Resolve hooks:** The plan registers `resolve_all_credits` as a resolve hook for `MachineModel` content type, so credit claims get materialised into `Credit` rows.

**`build_wikidata_persons_plan()` signature:**

```python
def build_wikidata_persons_plan(
    wikidata_persons: list[WikidataPerson],
    source: Source,
    input_fingerprint: str,
) -> IngestPlan:
```

Credit claims are included in the same plan as person claims (they share a source and apply atomically). This is one plan, not two — the person claims and credit claims reference existing entities only (no `identity_refs` needed).

### 3. `ingest_fandom` (most complex — three plans)

#### Plan A: Persons

**Entity types:** Person (match + create)

**Reconciliation:**

1. Parse games data to build `fandom_credits_by_name` (which person names appear in credits)
2. Skip persons with no game credits (not useful to create)
3. Exact name match via `build_person_lookup()`
4. Near-duplicate detection (same last name + shared game credit) — skip with warning
5. Safe to create → `PlannedEntityCreate`

**Claims asserted on Person (new + matched):**

- `name` (scalar)
- `slug` (scalar)
- `status` (for new entities: `active`)
- `fandom.bio` (extra-data, if non-empty)

**`build_fandom_persons_plan()` signature:**

```python
def build_fandom_persons_plan(
    fandom_persons: list[FandomPerson],
    fandom_credits_by_name: dict[str, set[str]],
    source: Source,
    input_fingerprint: str,
) -> IngestPlan:
```

The games data is parsed first by the management command to derive `fandom_credits_by_name`, then passed to this function. The adapter itself doesn't parse games.

#### Plan B: Credits

**Entity types:** MachineModel (match-only), Person (match-only via lookup), CreditRole (match-only)

Runs after Plan A is applied, so freshly-created persons are findable.

**Claims asserted on MachineModel:**

- `credit` (relationship: `{person: PK, role: PK}`)

**Reconciliation:**

- Games matched by `name.lower()` against `MachineModel.objects.all()`
- Persons matched by `build_person_lookup()` (refreshed after Plan A apply)
- CreditRoles matched by slug

**`build_fandom_credits_plan()` signature:**

```python
def build_fandom_credits_plan(
    games: list[FandomGame],
    source: Source,
    input_fingerprint: str,
) -> IngestPlan:
```

**Resolve hooks:** Registers `resolve_all_credits` for MachineModel content type.

#### Plan C: Manufacturers

**Entity types:** Manufacturer (match-only, no creation)

**Reconciliation:** `ManufacturerResolver` chain (same as current).

**Claims asserted on Manufacturer:**

- `name` (scalar)
- `fandom.description` (extra-data)
- `website` (scalar)

**`build_fandom_manufacturers_plan()` signature:**

```python
def build_fandom_manufacturers_plan(
    fandom_manufacturers: list[FandomManufacturer],
    source: Source,
    input_fingerprint: str,
) -> IngestPlan:
```

### Management Command Structure

Each command becomes a thin wrapper. Example for `ingest_fandom`:

```python
def handle(self, *args, **options):
    # 1. Fetch/dump (unchanged — same CLI flags)
    # 2. Parse all three datasets
    games = parse_game_pages(raw_games)
    fandom_persons = parse_person_pages(raw_persons)
    fandom_mfrs = parse_manufacturer_pages(raw_mfrs)

    # 3. Source setup
    source = get_or_create_source()

    # 4. Compute fingerprints (hash of each dataset)

    # 5. Derive credits-by-name from games (needed by persons plan)
    fandom_credits_by_name = _build_credits_by_name(games)

    # 6. Apply plans in order
    persons_plan = build_fandom_persons_plan(fandom_persons, fandom_credits_by_name, source, fp1)
    persons_report = apply_plan(persons_plan, dry_run=options["dry_run"])

    credits_plan = build_fandom_credits_plan(games, source, fp2)
    credits_report = apply_plan(credits_plan, dry_run=options["dry_run"])

    mfrs_plan = build_fandom_manufacturers_plan(fandom_mfrs, source, fp3)
    mfrs_report = apply_plan(mfrs_plan, dry_run=options["dry_run"])

    # 7. Print combined report
```

## Testing Strategy

### Plan-boundary tests (new)

One test file per adapter module. Test `build_*_plan()` directly: given parsed records and specific DB state, assert the plan contains the expected entities, assertions, and warnings. No `apply_plan()` calls.

**Pattern (from IPDB):**

```python
class TestWikidataManufacturerPlan:
    def test_matched_manufacturer_gets_claims(self, ...):
        plan = build_wikidata_manufacturers_plan(records, source, "fp")
        fields = _assertion_fields(plan, object_id=mfr.pk)
        assert fields >= {"wikidata_id", "name", "logo_url", "website"}

    def test_unmatched_manufacturer_skipped(self, ...):
        plan = build_wikidata_manufacturers_plan(records, source, "fp")
        assert len(plan.assertions) == 0

    def test_wikidata_description_is_extra_data(self, ...):
        plan = build_wikidata_manufacturers_plan(records, source, "fp")
        value = _assertion_value(plan, "wikidata.description", object_id=mfr.pk)
        assert value == "American manufacturer..."
```

**Fandom persons plan tests should cover:**

- Matched person gets name/slug/bio claims
- Person with no credits skipped (no entity create, no claims)
- Near-duplicate detected → warning, no entity create
- New person gets `PlannedEntityCreate` + name/slug/status claims
- Records parsed/matched counts are correct

**Fandom credits plan tests should cover:**

- Matched game + matched person + known role → credit assertion
- Unmatched game → skipped (no assertion, counted in warnings or records_parsed)
- Unmatched person → skipped
- Unknown role slug → warning

### Integration tests (updated)

Existing integration tests in `test_ingest_fandom.py`, `test_ingest_wikidata.py`, `test_ingest_wikidata_manufacturers.py` are updated to:

- Add `--dry-run` test (creates nothing)
- Verify `IngestRun` audit records exist after a real run
- Remove any assertions about sweep behavior
- Keep all existing correctness assertions (credits created, idempotency, etc.)

### Dry-run tests

Each command gets a dry-run integration test:

```python
def test_dry_run_creates_nothing(self, ...):
    call_command("ingest_wikidata_manufacturers", from_dump=SAMPLE, dry_run=True)
    assert Claim.objects.count() == initial_claims
    assert IngestRun.objects.count() == 0
```

## Implementation Order

Three commits, simplest first:

### Commit 1: `ingest_wikidata_manufacturers`

1. Create `catalog/ingestion/wikidata/__init__.py` and `adapter.py`
2. Implement `build_wikidata_manufacturers_plan()` + `get_or_create_source()` + `compute_fingerprint()`
3. Slim down management command to thin wrapper
4. Write plan-boundary tests (`test_wikidata_manufacturers_adapter.py`)
5. Update integration tests (`test_ingest_wikidata_manufacturers.py`)
6. Remove the misleading "direct field, not a claim" comment on `Manufacturer.wikidata_id` if present
7. Run tests: `make test`

### Commit 2: `ingest_wikidata`

1. Add `build_wikidata_persons_plan()` to `catalog/ingestion/wikidata/adapter.py`
2. Register `resolve_all_credits` as resolve hook for credit claims
3. Slim down management command
4. Write plan-boundary tests (`test_wikidata_adapter.py`)
5. Update integration tests (`test_ingest_wikidata.py`)
6. Remove the "direct field, not a claim" comment on `Person.wikidata_id`
7. Run tests: `make test`

### Commit 3: `ingest_fandom`

1. Create `catalog/ingestion/fandom/__init__.py` and `adapter.py`
2. Implement three build functions: persons, credits, manufacturers
3. Slim down management command (three `apply_plan()` calls in order)
4. Write plan-boundary tests (`test_fandom_adapter.py`)
5. Update integration tests (`test_ingest_fandom.py`)
6. Run tests: `make test`

## What Does NOT Change

- Parsing code: `fandom_wiki.py`, `wikidata_sparql.py` — untouched
- Source priorities: Fandom=20, Wikidata=75
- Reconciliation strategies: same matching logic, same resolver chains
- CLI flags: `--dump`, `--from-dump`, `--dump-persons`, etc. all preserved
- Test fixtures: same JSON sample files

## Risks

- **Resolve hook for credits.** The IPDB adapter registers `resolve_all_credits` as a resolve hook. Wikidata and Fandom credits need the same. Verify the resolve hook mechanism works for claims on existing entities (not just planned entities). If `apply.py._resolve()` only runs hooks for content types that had claims created, this should work — but verify.

- **`wikidata_id` via resolver.** Dropping the direct write means `wikidata_id` must be handled by the resolver. Verify that `resolve_all_entities(Person, ...)` and `resolve_all_entities(Manufacturer, ...)` correctly materialise `wikidata_id` from claims. If the resolver skips it or resets it, the integration tests will catch it.
