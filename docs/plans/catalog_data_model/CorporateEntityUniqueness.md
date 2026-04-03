# CorporateEntity Uniqueness

## Background

`CorporateEntity.name` is currently not unique. The code and prior planning docs explicitly treat `CorporateEntity` as a non-unique-name entity type, similar to `Person` and `Location`.

That assumption is no longer a good fit for the product direction. `CorporateEntity` is not just a search target; it is the canonical producer identity attached to `MachineModel`, exposed in APIs, rendered in the UI, and edited editorially. Ambiguous names make admin views, API payloads, ingest reconciliation, and user-facing pages harder to reason about.

The current populated database contains a real duplicate:

- `Shyvers Manufacturing Company`
  - `shyvers-manufacturing-company` — Seattle, WA `ipdb_manufacturer_id=452`
  - `shyvers-manufacturing-company-2` — Chicago, IL `ipdb_manufacturer_id=285`

These are distinct `CorporateEntity` rows under the same `Manufacturer`, but they are not usefully distinguishable by name alone.

## Decision

Treat `CorporateEntity.name` as the canonical, editorial, user-facing label and require it to be unique.

When two historically distinct corporate entities share the same bare legal name, the catalog will disambiguate the canonical name editorially. Qualifiers such as location, years, or parent organization are acceptable when they are the clearest stable distinction for users.

For the known conflict, rename:

- `Shyvers Manufacturing Company` → `Shyvers Manufacturing Company (Seattle)`
- `Shyvers Manufacturing Company` → `Shyvers Manufacturing Company (Chicago)`

The undisambiguated historical form should remain representable via provenance and aliases. In other words, uniqueness applies to the resolved canonical `name`, not to every asserted source string.

## Why This Direction

### 1. `CorporateEntity` is a catalog identity, not just a raw source echo

Unlike a legal-registry system, Pinbase is an editorial catalog. The important invariant is that the primary label shown to users and used by APIs resolves to exactly one entity.

### 2. Unique names simplify the whole stack

Unique `CorporateEntity.name` improves:

- API/admin clarity
- search result disambiguation
- ingest matching behavior
- debugging and manual data inspection
- future validation rules around names and aliases

### 3. The tradeoff is acceptable

The cost is that `name` becomes a canonical disambiguated label rather than a strictly raw legal name in every case. That is acceptable as long as we are explicit about it and preserve the bare historical/legal form through aliases or source claims.

## Non-Goals

- Do not redesign the claims/provenance model.
- Do not introduce a second display-name field in this tranche.
- Do not attempt to solve every possible cross-entity name collision in the catalog.
- Do not treat this as permission to bypass claims for editorial renames.

## Current-State Constraints

Today the model allows duplicate `CorporateEntity.name` values:

- no `unique=True` on `CorporateEntity.name`
- no DB `UniqueConstraint` on `name`
- existing docs classify `CorporateEntity` as a non-unique-name entity type
- IPDB adapter builds `ce_by_name` as a plain `dict[str, CorporateEntity]`, which silently keeps only one row per lowercased name if duplicates exist

That last point is important: duplicate names are not merely a UX problem. They also weaken ingest determinism because name-based reconciliation can silently collapse multiple entities to one winner.

## Proposed Changes

### 1. Make `CorporateEntity.name` unique at the database level

Update the model so that the invariant is enforced structurally, not by convention.

Preferred implementation:

- add `unique=True` to `CorporateEntity.name`

Alternative:

- add an explicit `UniqueConstraint(Lower("name"))` if case-insensitive uniqueness is desired

The implementation must make a deliberate choice here. If the project wants `Acme` and `ACME` to collide, enforce that now at the DB level rather than leaving it ambiguous.

## Recommendation on case sensitivity

Use case-insensitive uniqueness for canonical names.

Reasoning:

- users will interpret `Foo Corp` and `FOO CORP` as the same entity
- alias tables already enforce case-insensitive uniqueness via `Lower("value")`
- case-sensitive uniqueness would allow low-value duplicates that still create ambiguity in search and ingest

If that direction is chosen, use a DB constraint on `Lower("name")` rather than relying solely on `unique=True`.

### 2. Rename the existing conflicting rows before adding the constraint

The known duplicate pair must be updated in seed/editorial data and in the current database migration path.

Target names:

- `Shyvers Manufacturing Company (Seattle)`
- `Shyvers Manufacturing Company (Chicago)`

Use the current location associations as the basis for the qualifier. Parentheses are preferable to hyphen suffixes because they read as editorial disambiguators rather than as part of the legal name.

### 3. Preserve the undisambiguated form as aliases/claims

After the rename, both entities should still preserve `Shyvers Manufacturing Company` as a source-originating name in provenance and, if needed for resolution/search, in alias data.

This needs a concrete rule:

- if alias uniqueness rules permit only one entity to own a given alias string, do not assign the exact same alias to both rows
- instead, rely on the per-source `name` claims as the historical record of the bare string

This is the most likely place where the implementation will need care. The plan should not assume alias duplication is allowed if the schema forbids it.

### 4. Update docs that currently say `CorporateEntity` names are non-unique

At minimum:

- `docs/plans/NameAliasUniqueness.md`
- any stable docs that describe `CorporateEntity` naming behavior

The new rule should be explicit: `CorporateEntity.name` is unique because it is a canonical editorial label.

### 5. Harden ingest reconciliation against ambiguity

Even after the uniqueness change, the ingest code should stop assuming duplicates are harmless.

Specifically review `backend/apps/catalog/ingestion/ipdb/adapter.py`:

- current `ce_by_name` construction silently overwrites on duplicate lowercased names
- if uniqueness is enforced case-insensitively, this becomes structurally safe after cleanup
- before the migration lands, tests should document the current ambiguity and then confirm the new invariant removes it

## Implementation Plan

### Phase 1. Write failing tests first

Because this is a bug/invariant fix, follow the repository rule exactly:

1. Add a failing test showing duplicate `CorporateEntity.name` rows are currently allowed.
2. Add a failing test for the chosen uniqueness semantics:
   - exact uniqueness if using `unique=True`
   - case-insensitive uniqueness if using `Lower("name")`
3. Add or update an ingest-focused test that demonstrates name-based CE lookup must not be ambiguous.

Likely test locations:

- `backend/apps/catalog/tests/test_db_constraints.py`
- `backend/apps/catalog/tests/test_models.py`
- `backend/apps/catalog/tests/test_ipdb_adapter.py`

### Phase 2. Change the schema

Implement the chosen DB invariant on `CorporateEntity.name`.

Requirements:

- enforce at the DB layer
- keep `field_not_blank("name")`
- ensure migration order handles existing duplicates cleanly

If case-insensitive uniqueness is chosen, use the same style already used elsewhere in the codebase for alias uniqueness.

### Phase 3. Fix data before the constraint applies

Update the conflicting `Shyvers` entries in the editorial source data and in migration/backfill logic so a fresh bootstrap does not recreate the conflict.

This step must cover the real source of truth for those rows, not only the current local DB.

Possible write paths to inspect:

- `ingest_pinbase` data source for corporate entities
- any source-specific ingest that creates or updates `CorporateEntity.name`
- existing fixtures that may create duplicate names in tests

### Phase 4. Update ingest/reconciliation code

Review all code paths that rely on `CorporateEntity.name` lookup and simplify them to the new invariant.

In particular:

- document that CE names are now unique canonical labels
- remove any defensive assumptions that duplicates may legitimately exist
- keep alias-based/source-ID-based reconciliation intact

### Phase 5. Update docs

Revise docs and planning docs that still describe `CorporateEntity` as a non-unique-name entity type.

## Testing Strategy

Minimum required coverage:

- duplicate `CorporateEntity.name` insert fails
- case-only duplicate fails if case-insensitive uniqueness is adopted
- renamed `Shyvers` entities ingest/load successfully
- IPDB CE reconciliation still resolves expected records
- any UI/API list or detail tests that assume old names are updated

Run the smallest meaningful set first, then broader checks if needed:

- targeted Django tests for model constraints and ingest adapter behavior
- optionally `make test` if the change touches many expectations

## Risks

### 1. Historical/legal-name purity

The canonical `name` becomes a disambiguated editorial label, not always a verbatim legal name. This is acceptable, but it should be treated as an intentional product rule, not an accident.

### 2. Alias collisions

If the system wants to preserve the bare duplicate form as aliases for both entities, existing alias uniqueness rules may block that. Provenance may be sufficient, but this must be verified during implementation.

### 3. Source churn

If an external source later reasserts the bare duplicate string as a winning `name` claim, the resolver may try to materialize a duplicate canonical name. The implementation needs a clear policy:

- either the source claim remains stored but does not become the resolved canonical value without editorial disambiguation
- or source-specific CE names must already be normalized/disambiguated before assertion

This policy should be made explicit during implementation, because DB uniqueness alone will surface the conflict but will not explain how to resolve it.

### 4. Existing references and snapshots

Tests, fixtures, and possibly frontend snapshots may assume the old `Shyvers` names. Those will need coordinated updates.

## Open Questions

1. Should uniqueness be exact or case-insensitive? This plan recommends case-insensitive uniqueness.
2. Should the qualifier style prefer `(Seattle)` / `(Chicago)` or year ranges such as `(Seattle, 1933)`? This plan prefers the shortest stable user-facing qualifier.
3. Should the bare historical/legal name be preserved as an alias, or is claim history alone sufficient?
4. How should resolver/materialization behave when two active claims would resolve to the same canonical CE name?

## Recommended Outcome

Adopt unique canonical `CorporateEntity.name` values, disambiguate the known `Shyvers` conflict editorially, and enforce the invariant at the database level with tests first.

That gives Pinbase a cleaner mental model:

- `Manufacturer.name` is unique
- `CorporateEntity.name` is unique
- `Person.name` and `Location.name` may still be non-unique

This is easier for users, easier for code, and more consistent with `CorporateEntity`'s role as a first-class catalog identity rather than a raw source string bucket.
