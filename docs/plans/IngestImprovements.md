# Ingest Pipeline Improvements

## Problem

The ingest commands work reliably today, but they're fragile against upstream
drift and harder to maintain than they need to be. Specific issues:

1. **No structured parsing layer.** Raw JSON dicts (`rec.get("field")`) flow
   directly into claim-building logic. If IPDB renames a field or changes a
   type, the result is silent `None` values — not errors.

2. **Duplicated patterns.** IPDB and OPDB commands each implement their own
   manufacturer resolution, model matching, slug generation, and claim
   collection. The logic is similar but not shared.

3. **Monolithic commands.** `ingest_ipdb` and `ingest_opdb` each do parsing,
   matching, claim building, person/credit creation, and resolution in one
   800+ line file. Testing any piece in isolation requires running the whole
   command.

4. **Catch-all error handling.** Broad `except Exception` around per-record
   processing means a type error in one field silently skips the whole record
   and logs a stack trace. There's no distinction between "bad data I should
   skip" and "bug in my code."

5. **No preview mode.** You can't see what an ingest run *would* change
   without actually writing to the database.

## Approach

Use `dataclasses` (not pydantic) to define typed record shapes for each
source. Add explicit validation in `__post_init__` where needed. Keep the
dependency footprint unchanged.

## Plan

### Phase 1: Typed record dataclasses

Create `backend/apps/catalog/ingestion/records.py` with dataclasses for each
external source's raw record shape:

```python
@dataclass
class IpdbRecord:
    ipdb_id: int
    title: str
    manufacturer_id: int | None = None
    manufacturer: str = ""
    date_of_manufacture: str = ""
    mpu: str = ""
    type_short_name: str = ""
    type_full: str = ""
    players: int | None = None
    production_number: str = ""
    # ... remaining fields

    def __post_init__(self):
        if not self.ipdb_id:
            raise ValueError("IpdbRecord requires ipdb_id")
        self.title = unescape(self.title)

@dataclass
class OpdbRecord:
    opdb_id: str
    name: str = "Unknown"
    ipdb_id: int | None = None
    manufacturer_name: str = ""
    manufacture_date: str = ""
    # ... remaining fields
```

Each dataclass handles its own field normalization (HTML unescape, string
stripping, type coercion) in `__post_init__`. A `@classmethod from_raw(cls, d: dict)` factory maps raw JSON keys to Python field names, so the key
mapping lives in exactly one place.

**Benefit:** If a source renames or removes a field, you get a clear
`KeyError` or `ValueError` at parse time, not a silent `None` deep in claim
building.

### Phase 2: Extract shared utilities

Factor out patterns duplicated between IPDB and OPDB commands:

- **`ManufacturerResolver`** — Encapsulates the entity-name → slug,
  trade-name → slug, and auto-create-on-miss logic that both commands
  implement independently. Single class, initialized once per ingest run.

- **`ModelMatcher`** — The match-by-ipdb-id → match-by-opdb-id →
  create-new cascade, including the in-memory slug/id tracking dicts.
  Both commands do this; OPDB adds alias handling on top.

- **`ClaimCollector`** — A lightweight accumulator that replaces the raw
  `pending_claims: list[Claim]` + `_add()` closures. Knows the
  `content_type_id` and current `object_id`, provides typed methods like
  `scalar("year", 1992)`, `relationship("credit", {...})`, and
  `sweep("credit")`.

These live in `backend/apps/catalog/ingestion/` alongside the existing
`parsers.py` and `bulk_utils.py`.

### Phase 3: Separate parsing from persistence

Restructure each ingest command into two clear phases:

1. **Parse phase** — Read the raw file, produce a list of typed dataclass
   records. No database access. This is independently testable.

2. **Persist phase** — Take parsed records, match/create models, build
   claims, bulk-assert. This is where the `ManufacturerResolver`,
   `ModelMatcher`, and `ClaimCollector` do their work.

The management command's `handle()` becomes a thin orchestrator:

```python
def handle(self, *args, **options):
    records = IpdbRecord.load(options["ipdb"])  # parse phase
    self.persist(records)                        # persist phase
```

### Phase 4: Structured error reporting

Replace the catch-all `except Exception` with specific error categories:

- **`ParseError`** — Source data doesn't match expected shape. Logged with
  source record ID and field name. Record is skipped, ingest continues.

- **`MatchError`** — Can't resolve a foreign reference (unknown MPU string,
  unresolvable manufacturer). Currently these are collected into sets like
  `unknown_mpu_strings` — formalize this pattern.

- **`DataConflict`** — Two sources assert incompatible values for the same
  field. Already handled by the claims system, but currently invisible
  during ingest. Surface these as warnings.

Collect all errors per-run and emit a structured summary at the end, rather
than interleaving stack traces with progress output.

### Phase 5: Dry-run / diff mode

Add `--dry-run` to `ingest_all` and each sub-command. In dry-run mode:

- Parse phase runs normally (validates the data).
- Persist phase runs inside a transaction that is rolled back.
- `bulk_assert_claims` stats are captured and reported but not committed.
- Output shows: N models would be created, N claims would change, N persons
  would be created.

This makes it safe to preview an ingest against production data without
writing anything.

## Non-goals

- **Pydantic.** Dataclasses + explicit validation is sufficient. The ingest
  sources are stable and under our control. Adding pydantic would shift the
  project's style for marginal benefit.

- **Async / streaming.** The full ingest runs in under 60 seconds. There's
  no performance problem to solve.

- **Generic "ingest framework."** Each source has enough unique logic
  (OPDB aliases, IPDB title fixes, non-physical group promotion) that
  forcing them into a shared base class would create more abstraction than
  it removes duplication. Shared utilities yes, shared base class no.

## Sequencing

Phases are independent and can be done in any order. Phase 1 (typed records)
gives the most immediate value — it's where upstream drift detection lives.
Phase 5 (dry-run) is the most useful operationally. Phases 2-3 are
refactoring that pays off as the number of sources grows.

Recommended order: 1 → 4 → 5 → 2 → 3.
