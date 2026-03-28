# ValidationFix

## Background

Pinbase's catalog truth is claims-based: sources and users assert Claims, claim resolution picks winners, and resolved/model tables materialize the current catalog state. That architecture is sound in principle, but provenance, ingest, end user editing, admin editing, and validation were not designed together from the beginning. Validation was added later and ended up spread across multiple write paths instead of being designed into the system from the start.

Today, "validation" means several different things:

- request validation in user-facing edit APIs
- admin form validation
- ingest-specific source parsing and prechecks
- resolver guard rails and coercion
- post-hoc catalog audit via `validate_catalog`

All of those are useful, but they are not the same thing. The result is that correctness depends on _how_ data enters the system.

## Analysis

See [WritePathMatrix.md](WritePathMatrix.md) for the full inventory. The important findings are:

### 1. There is not one write path today

The current system has several distinct truth-affecting write paths:

- user-facing PATCH claim APIs
- Django admin via `ProvenanceSaveMixin`
- direct admin bypasses
- ingest bulk claim writes
- ingest direct ORM writes
- one-off management command claim writers
- resolution/materialization itself

There is no single place where "all data enters the system."

### 2. User-edit validation is the strongest path

The PATCH path validates:

- scalar field validators
- markdown cross-reference rules
- FK/slug existence
- relationship target existence
- cycle/self-reference checks for some graph relationships
- duplicate checks for submitted relationship payloads

This is the most complete validation logic in the codebase today.

### 3. Bulk ingest claim writes are under-validated

`bulk_assert_claims()` centrally validates almost nothing beyond mojibake on string values.

It does **not** currently enforce, in one place:

- field range validators
- markdown cross-reference validation
- FK existence
- relationship target existence
- cycle detection

As a result, invalid claims can enter via ingest even though the interactive PATCH path would have rejected them.

### 4. Some writes still bypass claims entirely

WritePathMatrix identifies direct ORM writes with no claim at all, including:

- direct M2M writes such as `series.titles.add(*titles)`
- direct `save(update_fields=[...])` writes in ingest
- direct `QuerySet.update()` writes
- fields hidden behind `claims_exempt`

These are not just validation gaps. They are provenance coverage gaps.

### 5. Admin is mixed, not cleanly claims-driven

Admin is not one thing:

- `ProvenanceSaveMixin` routes changed scalar fields through claims, but only after the model row is first written
- some admin screens bypass the provenance path entirely
- some relationships remain directly editable rather than claim-controlled

"The admin validates it" is not the same thing as "it went through the claims system." More importantly, trying to make admin behave exactly like the claims UI/API would add complexity to the plan for relatively little value. If admin remains a full catalog edit surface, the system still has a fundamentally different human write path.

### 6. Resolver and audit are carrying too much burden

The resolver is appropriately defensive in some cases, but it should not have to compensate for inconsistent upstream validation. Likewise, `validate_catalog` is useful as a post-hoc quality layer, but it should not be the first place correctness issues are discovered for claim-managed truth.

## Diagnosis

The system's biggest design problem is that the claims architecture is only partially being used as intended. The analysis points to two distinct problems:

**Coverage gaps** — some catalog facts enter the system without a claim, meaning no audit trail, no conflict-resolution mechanism, and no shared claim-boundary validation. These are mechanical correctness gaps in how the current architecture is used.

**Validation gaps** — even when data does go through claims, not all claim write paths validate the same rules. Bulk ingest validates almost nothing beyond mojibake; the interactive PATCH path validates everything. These are semantic consistency gaps at the claim boundary.

The two problems are related, but they do **not** require the same solution. Until coverage gaps are fixed, any attempt to centralise validation will be centralising it at a boundary that not all writes even reach.

The codebase already has everything needed to fix both: an unsaved `Claim` object that carries almost all the data needed for claim-boundary validation; concrete write helpers (`assert_claim()`, `bulk_assert_claims()`, `execute_claims()`); and strong validation logic in `validate_scalar_fields()` in the interactive PATCH path. The right fix is to close the coverage gaps first, then reuse the existing validation logic at the claim boundary. No new service abstractions are needed.

There is also an explicit product decision that simplifies the plan:

- the Django admin does **not** need to remain a catalog edit surface
- catalog models will be unregistered from admin entirely

That means admin does not need to be normalized into the same edit architecture as the claims UI/API. It is reduced to infrastructure/configuration and provenance inspection only. This is the cleanest way to eliminate the strangest human write path in the system.

Finally, there is an operational decision that also simplifies the migration:

- it is acceptable to delete the database and reset migrations back to `0001`

That removes a large class of migration/backfill complexity. The plan can optimize for achieving a coherent architecture in the codebase rather than preserving every historical intermediate state in-place.

## Remove Admin as a Catalog-Truth Writer

Catalog models should be unregistered from Django admin entirely. Read-only admin requires overriding `has_add_permission`, `has_change_permission`, and `has_delete_permission` on every `ModelAdmin` and maintaining that discipline for every new model added — it is boilerplate that leaks. Unregistering is enforced by absence with nothing to misconfigure.

Admin remains registered for:

- `Source`
- provenance inspection (`Claim`, `ChangeSet`)
- internal infrastructure/configuration models

This eliminates the strangest human write path in the system without introducing new maintenance surface.

## Component A — Fix Coverage Gaps First

Make every intended catalog fact go through claims. This is mechanical work and should be done before extracting new abstractions.

### A1. Remove non-justified `claims_exempt` declarations

Every `claims_exempt` declaration on every model was reviewed. The architectural rule is: every field set by a human or data source requires a claim. The only legitimate exemptions are fields set exclusively by the database engine: `id`/`uuid`, `created_at`, `updated_at`.

All other exemptions are wrong and must be removed:

| Model                     | Fields to migrate                                                 |
| ------------------------- | ----------------------------------------------------------------- |
| `Person`                  | `wikidata_id`                                                     |
| `Manufacturer`            | `wikidata_id`, `opdb_manufacturer_id`                             |
| `CorporateEntity`         | `ipdb_manufacturer_id`                                            |
| `Title`                   | `opdb_id`, `fandom_page_id`, `needs_review`, `needs_review_notes` |
| `TechnologySubgeneration` | `technology_generation` (parent FK)                               |
| `DisplaySubtype`          | `display_type` (parent FK)                                        |
| `System`                  | `manufacturer`, `technology_subgeneration`                        |

For each field: add claim assertions in the relevant ingest command or management command path, remove the `claims_exempt` entry, update resolution to materialise from the claim.

WritePathMatrix is the authoritative field inventory for this work.

### A2. Replace direct ORM writes to claim-controlled data

Replace direct writes such as:

- `save(update_fields=[...])` on claim-controlled fields
- `QuerySet.update(...)` on claim-controlled fields

with `bulk_assert_claims()` calls using the correct source attribution.

### A3. Bring remaining editorial relationships under claims ✓

The known case was `series.titles.add(*titles)` in `ingest_pinbase`, which wrote series-title membership directly as a M2M operation with no claim. This has been replaced with claims-based membership.

**What was done:**

1. Added `"series_title": {"title_slug": "title"}` to `RELATIONSHIP_SCHEMAS` in `claims.py`.

2. Replaced `series.titles.add()` with `bulk_assert_claims()` calls using `sweep_field="series_title"` and an authoritative scope covering all series in the DB, so titles removed from a series are retracted on subsequent runs.

3. Added a standalone `resolve_all_series_titles()` in `resolve/_relationships.py` that resolves `series_title` claims into `Series.titles` through-table rows using a single query and a diff/apply approach. It was written as a standalone function rather than using `_resolve_machine_model_m2m()` because the claim lives on `Series`, not `MachineModel` — parameterising the generic helper would have added complexity for a single non-MachineModel use case.

4. As part of this work, `_resolve_all_m2m()` was renamed to `_resolve_machine_model_m2m()` to make explicit that the generic helper is scoped to MachineModel relationships only.

If WritePathMatrix identifies further direct M2M writes for editorial relationships, apply the same treatment using the standalone resolver pattern.

### Implementation pitfalls for A1–A3

Two bug classes emerged during A3 implementation that apply to all remaining Component A work.

**Wrong content type.** Every `Claim` object must be created with the content type for the model that _owns_ the claim, not the model being iterated. When a single ingest method touches multiple model types (e.g. `_ingest_titles` creates claims on both `Title` and `Series`), each model needs its own `ct_id` captured separately. Reusing `ct_id` across model types produces claims attached to the wrong object silently — no error, wrong data.

**Claims built against unstable identity values.** When a claim value references another object's slug (or any identity value that might change later in the same ingest pass), the claim must use the effective post-operation value, not the pre-operation value. In `_ingest_titles`, series-title claims were initially built using `title.slug` before the slug rename loop ran, producing claims that referenced a slug that no longer existed in the DB after the rename.

The structural fix for `_ingest_titles` is a **two-pass refactor**: split the method into a collect phase (gather `(title, entry)` pairs, pending slug renames, pending fandom updates, series memberships) followed by the rename/transform phase, then an assert phase that builds all claims using stable post-rename slugs. This eliminates the need for the `pending_slugs.get(title.pk, title.slug)` workaround and makes the phase dependency explicit. The cost is low — the intermediate state is a list of `(title, entry)` pairs.

Do this two-pass refactor as part of A1 when `_ingest_titles` is being modified to add new claim assertions for `fandom_page_id` and `opdb_id`. It is a net clarity improvement, not just a bug fix.

The broader principle: **claims that reference another object's identity must be built after all identity updates in the same pass have been applied.**

### A4. Document acceptable bootstrap writes

Some ingest commands write fields directly before asserting claims for those same fields in the same pass — for example, `MachineModel.objects.bulk_update([...], ["opdb_id", "ipdb_id"])` in `ingest_pinbase` and `ingest_opdb`, followed immediately by `bulk_assert_claims()` for the same values. This pattern is acceptable: the bootstrap write and the claim assertion travel together in the same ingest run, so the claim always catches up.

No change is required for these writes. Add an inline comment making the dependency explicit, so future maintainers do not break the pairing.

## Component B — Reuse Existing Validation Logic at the Claim Boundary

Once writes actually reach the claim boundary, add shared validation there by extracting and reusing the logic that already exists in the interactive edit path. This includes one-off management command claim writers: they already route through `assert_claim()` or `bulk_assert_claims()` (so they have no coverage gap), but they currently get no more validation than any other bulk caller. Component B closes that gap for `bulk_assert_claims()` callers automatically. Single-claim writers that use `assert_claim()` directly (such as `scrape_images`) are a smaller surface but should also be audited and wired to `validate_claim_value()` once it exists.

### B1. Extract `validate_claim_value()`

The scalar/direct-field validation already implemented in `validate_scalar_fields()` should be extracted into a reusable function:

```python
def validate_claim_value(field_name: str, value, model_class) -> None:
    """Raise ValidationError if value is not valid for the given field."""
```

This should cover, for direct-field claims:

- type coercion
- Django field validator chain
- mojibake checks
- markdown cross-reference validation

### B2. Call it from `bulk_assert_claims()`

`bulk_assert_claims()` should call the extracted validation before persisting claims, rather than relying on the user-facing PATCH path to be the only place where strong validation happens.

### B3. Add batched FK and relationship validation

FK/relationship target validation should also move toward the claim boundary, but in batch-aware form:

- validate all referenced slugs in one batch
- avoid one query per claim
- collect failures efficiently for ingest

This is especially important for ingest scale.

## Enforcement Modes

User edits and ingest should not be treated as identical operational flows.

The correct model is:

- **same semantic rules**
- **different enforcement modes**

### Interactive mode

For user-facing edits and similar synchronous writes:

- fail fast
- return explicit errors
- block the write

### Batch ingest mode

For ingest:

- batch/prefetch lookups
- collect validation failures
- log and skip invalid claims where appropriate
- continue processing valid claims

We do not need one monolithic validator service with one failure behaviour. We need shared rules enforced in different modes.

## Migration Order

1. **Use WritePathMatrix as the source inventory.**
   Enumerate and confirm every remaining bypass and every field/relationship that still fails to go through claims.

2. **Remove admin as a catalog-truth writer.**
   Unregister catalog models from admin. Keep admin only for infrastructure/configuration and provenance inspection.

3. **Fix Component A.**
   Remove non-justified `claims_exempt`, migrate direct writes, and bring claim-managed facts onto claims. Use the migration reset allowance to clean up directly rather than preserving transitional states.

4. **Then fix Component B.**
   Extract `validate_claim_value()` and call it from `bulk_assert_claims()`.

5. **Then add batched FK/relationship validation at the claim boundary.**
   Do this in a way that supports ingest-scale processing.

6. **Then trim `validate_catalog` and review resolver guard rails.**
   Remove correctness checks from `validate_catalog` that are now guaranteed upstream. Review the resolver's defensive coercions and guard rails for the same reason — once upstream validation ensures only valid values reach claims, the resolver should not need to compensate for invalid data.

7. **Only after that, decide whether new abstractions are warranted.**

## Follow-ups Out of Scope for This Plan

### Taxonomy edit UIs

All taxonomy/vocabulary models (TechnologyGeneration, TechnologySubgeneration, DisplayType, DisplaySubtype, Cabinet, GameFormat, CreditRole, Franchise, RewardType, Tag, Theme, GameplayFeature) are currently fully ingest-managed from pindata JSON. Removing admin write access is safe today.

However, these models will need user-facing edit UIs. Taxonomy values are editorial decisions — adding a new technology generation, renaming a credit role, or reorganising display subtypes should go through the same claims-based edit path as other catalog truth, not require a pindata JSON edit and re-ingest.

This is a separate feature project, not a prerequisite for ValidationFix3.

## Acceptance Criteria

This plan is successful when:

- all intended catalog facts flow through claims
- catalog models are unregistered from Django admin
- remaining direct writes are either removed or explicitly documented as true bootstrap exceptions
- `bulk_assert_claims()` validates direct-field claim values using shared logic extracted from the interactive edit path
- FK and relationship existence checks run at claim-write time in ingest using batched lookups
- editorial relationships identified in WritePathMatrix are materialised from claims, not written directly
- `validate_catalog` no longer carries correctness rules that should have been enforced upstream
- resolver defensive guard rails that compensate for upstream validation gaps have been reviewed and trimmed
- the codebase can be recreated cleanly from a reset initial migration set
