# Ingest Architecture

## The Problem

Pinbase's ingest layer is a set of Django management commands that import catalog data from external sources (IPDB, OPDB, Fandom wiki, Wikidata) and from Pinbase's own editorial data (pindata JSON exports). Each command was written independently and evolved to handle its source's unique data shape.

The commands are fragile, hard to maintain, and a persistent source of bugs — especially for AI agents working on them. The root cause is not that the code is messy (though some of it is). The root cause is that the commands are imperative programs that mix several distinct responsibilities in one place: parsing, entity matching, claim-intent policy, direct ORM mutation, claim assertion, and resolver invocation. These concerns are interleaved in per-command control flow with no shared contracts or boundaries.

This makes it hard to answer basic questions about any given ingest write:

- Is this write provenance-backed?
- If the command fails halfway through, what state remains?
- If a source stops asserting a value, does the old claim get retracted?
- Should this source be asserting this field for this entity at all?

The answers are buried in per-command control flow, variable names, tuple positions, and comments. They are not represented in the type system or enforced by shared infrastructure.

### Concrete failure modes

**Non-atomic execution.** None of the individual ingest commands wrap their `handle()` in `transaction.atomic()`. (`ingest_all` wraps the full pipeline, but individual commands run without protection during development and debugging.) A command that fails after creating entity rows but before finishing claim assertion leaves partial state that is hard to diagnose and may not be safe to retry.

**Direct writes bypass claims.** Despite the project rule that all catalog fields are claims-based, ingest still has multiple direct-write paths: `QuerySet.update()` for title slugs, `save(update_fields=...)` for wikidata IDs (which are also asserted as claims — a dual-write), direct `opdb_id` rewrites in changelog processing, and `ManufacturerResolver.resolve_or_create()` which creates `Manufacturer` rows with no claim provenance at all.

**No retraction mechanism.** There is no explicit way to retract a claim or mark an entity as deleted through the claims system. The current relationship sweep machinery infers retraction from omission, but this is only meaningful during incremental re-ingest — and the project currently rebuilds from a bare DB each time, so sweep is effectively a no-op.

**Snowflake claim collection.** The same conceptual operations (match or create entities, collect scalar claims, gate slug claims on source attribution, assert relationship claims with sweep) are reimplemented with different variable names, data structures, parameter conventions, and control flow in each command. During the slug migration, this caused an agent to assert slug claims for entities a source didn't create, a human reviewer to miss the same error for two entity types, and a tuple-arity change to break an unpack site that couldn't be found by grep.

**Implicit policy.** Whether a source should assert a slug claim, whether it should assert a name claim, whether it is authoritative enough to sweep, which anomalies are warnings vs. blocking errors — all of these are encoded as if-branches and local conventions rather than as named, auditable policy.

## Design Principles

**Separate planning from application.** Parsing, matching, and claim-intent decisions should happen before any database mutation. Database mutation should happen in one place, in one transaction, with no source-specific logic.

**Additive-only ingest.** The project is pre-launch. The normal workflow is to delete the database and rebuild from scratch. Ingest is a positive assertion process: sources assert what they currently provide. Absence from a source payload has no deletion semantics. The system does not infer what a source has deleted from what it didn't include.

**Explicit operations only.** The system has three primitive write operations: `create_entity`, `assert_claim`, `retract_claim`. These are intentionally narrow and explicit. There is no omission-based retraction — if a claim needs to be retracted, the planner emits an explicit `retract_claim` operation. Retraction is available from day one as a primitive (entity lifecycle needs it), but near-term ingest adapters will rarely use it.

**One write path.** Every catalog fact enters the system through claims. No direct ORM writes to claim-controlled fields. Entity creation and claim persistence both happen in the apply layer's transaction — the planner never writes to the database.

**Claims reference entities by PK, not slug.** Relationship claims (credits, themes, gameplay features, etc.) reference their target entities by primary key, not by slug. The planner resolves "IPDB says person Pat Lawlor" to a PK during reconciliation; the claim stores the PK. This eliminates the class of bugs where slug renames invalidate existing claim values, and decouples the claims system from editorial slug choices. Only pindata uses slugs as identity; no external source has slugs.

**Source-specific complexity stays source-specific.** Parsing, matching heuristics, encoding fixes, entity-creation decisions (e.g. IPDB's corporate entity derivation) — these are inherently per-source. The architecture should not try to force them into a shared abstraction. It should give them a clear place to live and keep them out of the apply layer.

**Idempotency.** Running the same ingest with the same input data twice should produce identical database state. No new rows, no side effects. The current `bulk_assert_claims` already achieves this (unchanged claims are detected and skipped). This must remain true in the redesign; it is an explicit design goal, not an emergent property.

## Architecture

### Two phases: Plan and Apply

Every ingest run has two phases with an explicit boundary between them.

**Plan** — the source adapter reads raw data, matches it to existing entities, applies source-specific policy, and produces a change plan. The planner does not mutate the database. It references entities that need to be created by including `PlannedEntityCreate` operations in the plan, not by writing rows directly.

**Apply** — the framework creates planned entities (capturing PKs), patches PKs into associated claims, validates planned claims, persists all changes in one transaction, resolves affected entities, and emits a run report. The applier processes explicit operations (`create_entity`, `assert_claim`, `retract_claim`) and contains no source-specific logic.

This separation is the core of the design. Everything else follows from it. The boundary must be strict: the planner produces data, the applier performs writes. If the planner is allowed to "just create a bootstrap row," the separation unravels — dry-run is no longer side-effect-free, and the transaction boundary leaks.

### Source adapters

Each source implements three concerns:

**Parse.** Load raw data, convert to typed source records. This is already extracted into per-source record types (`IpdbRecord`, `OpdbRecord`, etc.) and mostly works well today.

**Reconcile.** Match source records to existing entities. Output is a list of `MatchResult` objects:

```python
@dataclass
class MatchResult[R]:
    entity: Model | None   # existing entity, or None if new
    record: R              # typed source record
    created_by_source: bool
    # possibly: match_type (exact_id, name, heuristic, ambiguous)
```

The default reconciliation strategy is a shared fallback chain, in order:

1. **External source ID** — does an existing entity have an ID linking it to this source's record? (e.g. `ipdb_id`, `opdb_id`, `fandom_page_id`). This is the strongest match — it means the entity has been linked to this source before.
2. **Exact name match** — does the source record's name match an existing entity's name exactly?
3. **Exact alias match** — does the source record's name match an existing alias for any entity of this type?

If none match, the entity is new (`created_by_source=True`).

This default covers most entity types. Source adapters can override it when the domain requires a more specific chain. For example, Wikidata manufacturer reconciliation needs to search across both `Manufacturer` and `CorporateEntity` with normalized name matching — a domain-specific sequence that doesn't fit the generic chain.

Only pindata (the Pinbase editorial export) uses slugs as identity. No external source has slugs. Slugs are editorial/display properties, not cross-source identity.

For new entities (no match found), the reconciler does not create database rows. Instead, the claim collection step emits a `PlannedEntityCreate` alongside the claims for that entity. Claims reference the planned entity by a temporary handle (e.g. an index into the plan's create list, or the source-specific identity values). The apply layer creates the row, captures the PK, and patches it into the associated claims before persisting them.

This is more machinery than "just create the row in the reconciler," but it is what makes the planner genuinely non-mutating. Without it, dry-run would still write rows, the transaction boundary would leak, and the plan/apply separation would be nominal rather than real.

The reconciliation chain must produce structured output rather than silently falling through into row creation as a side effect of a lookup helper.

**Collect claims.** Given reconciled results, produce the set of claims this source wants to assert. Source-specific policy is explicit here:

- Slug gating: assert only when `created_by_source` (cross-source invariant)
- Name policy: per-source, per-entity (IPDB skips name for matched machine models due to encoding corruption; Fandom always asserts name to prevent resolver blanking; OPDB asserts name unconditionally)
- Field mappings: which source fields become which claim field names
- Encoding transforms: HTML entity decoding, mojibake handling
- Relationship claims: credits, themes, gameplay features, etc.

Simple policy (slug gating, source permission declarations) should be data. Complex policy (IPDB's CE derivation from manufacturer data, Fandom's near-duplicate person detection) will remain procedural code. The goal is not to make all policy declarative — it is to give policy a named, auditable location rather than embedding it in general-purpose control flow.

Claim value validation is not a concern of the source adapter. The apply layer runs `validate_claims_batch()` on all planned claims — the same claim-boundary validation established by [ValidationFix.md](ValidationFix.md) Component B. Source adapters produce claims; the framework validates them.

### Operation primitives

The apply layer processes three primitive operations:

- **`create_entity`** — create a new catalog entity row
- **`assert_claim`** — record a positive source- or user-attributed fact about an entity
- **`retract_claim`** — explicitly withdraw a previously active claim

These are intentionally narrow. The apply layer does not infer operations from absence — if a source wants to retract something, the planner must emit an explicit `retract_claim`.

Near-term ingest adapters will almost exclusively use `create_entity` and `assert_claim`. `retract_claim` is available from day one because entity lifecycle operations need it (e.g. asserting `status=deleted` may accompany explicit retraction of the entity's claims), but it is not used for omission-based inference.

### Additive-only ingest (near-term)

The project is pre-launch. The normal workflow is to delete the database and rebuild from scratch by running a full ingest. There is no long-lived incremental sync against production data.

In this context, omission-based retraction (inferring that a missing value should be deleted) would be based on assumptions about future source behavior that have not been validated. The near-term ingest model is therefore additive-only:

- Sources assert what they currently provide
- Absence from a source payload has no deletion semantics
- The system does not infer what a source has deleted

The current relationship sweep machinery (`sweep_field` + `authoritative_scope`) is a form of omission-based retraction. On a bare DB it's a no-op (no prior claims to retract). It will be replaced by explicit operations when source adapters are converted.

### Future reconciliation (deferred)

When the project reaches a stage where incremental re-ingest against a live database is needed, retraction-from-omission becomes a real requirement. At that point, a reconciliation workflow can be added that:

1. Takes an authoritative snapshot from a source for a declared scope
2. Computes the diff against the source's current active claims
3. Emits explicit `assert_claim` and `retract_claim` operations
4. Hands those operations to the same apply layer

This is additive to the architecture — it's a planner-level utility that compiles snapshot semantics down to explicit primitives. The apply layer itself never needs to know about sync modes, authoritative scope, or omission semantics.

**Constraint for future reconciliation design:** a claim rejected by validation during the current run must not produce a `retract_claim`. "Source included this field but validation rejected it" is different from "source did not include this field." This rule lives in the reconciliation utility, not in the apply layer.

### Source permissions are separate from retraction

A source may be disallowed from asserting a category of facts regardless of retraction policy. For example, OPDB should not assert `title` or `variant_of` claims; manufacturer/company facts should target `CorporateEntity` not `Manufacturer`. These are source-permission and domain-ownership rules, not sync-mode rules. The framework keeps them separate — source permissions answer "may this source assert claims in this category?" while operations answer "what claims is the source asserting or retracting?"

### Ingest runs and change sets ✓ (data models implemented)

Ingest provenance is recorded at two levels:

**IngestRun** — one record per source invocation. This is the run-level audit trail:

- source (FK to Source, on_delete=PROTECT)
- start/end timestamps
- input fingerprint (CharField)
- git SHA (CharField)
- counts (JSONField: parsed, matched, created, asserted, retracted, rejected)
- status (running, success, partial, failed)
- warnings and errors (JSONField lists)

**ChangeSet** — one per target entity touched in the run. Groups all claims the source asserted about that entity (scalar claims, relationship claims) into a coherent unit. Each ChangeSet has a nullable FK to its IngestRun (on_delete=PROTECT). Exactly one of user or ingest_run must be set (strict XOR).

Retractions are linked to the ChangeSet so entity history shows the complete picture — what was added, what was changed, and what was removed in a given run. Claim has a nullable `retracted_by_changeset` FK (on_delete=PROTECT). When the diff deactivates a claim, the apply layer sets `is_active=False` and sets `retracted_by_changeset` to the current entity's ChangeSet. Entity history can then show both "these claims were asserted" (ChangeSet → claims) and "these claims were retracted" (ChangeSet → retracted claims via reverse FK).

"Per target entity" means grouped by the object the claims are about, not by the source record that triggered them. When IPDB processes one machine record, it may assert claims against the MachineModel, create or update a CorporateEntity, and assert claims against Persons for credits. That is three ChangeSets (one per target entity), not one. This is the right granularity because entity history is viewed per entity — a user looking at Medieval Madness's history sees the claims about Medieval Madness, not about the CorporateEntity that was also updated in the same source record.

Claims already have an optional FK to ChangeSet. The IngestRun is reachable through ChangeSet — claims don't need a direct FK to IngestRun.

This gives two natural query levels:

- "Show me everything IPDB said about Medieval Madness in this run" — that's the ChangeSet
- "Show me everything that happened in the March 28 IPDB run" — that's the IngestRun

ChangeSet is reused exactly as designed: a thin grouping of related claims from one actor. For user edits, the actor is a user and the ChangeSet groups a handful of manual changes. For ingest, the actor is a source and the ChangeSet groups everything a source said about one entity. The single-actor invariant holds in both cases. The scale is right — dozens of claims per entity, not thousands.

**Single-actor enforcement.** A `CheckConstraint` on ChangeSet enforces that exactly one of `user` and `ingest_run` is set (strict XOR). `assert_claim()` additionally checks that source-attributed claims with a changeset require `changeset.ingest_run.source == source`. Note: the apply layer uses `bulk_create` for ChangeSets and Claims, which bypasses `assert_claim()`. Source consistency on the bulk path is maintained by construction — the apply layer creates each ChangeSet from the IngestRun, then creates claims with the same source. Implementers must maintain this invariant explicitly.

**Visibility.** IngestRun is an admin/system-level concept. Admins can browse runs across all sources — inspecting counts, timing, failures, and warnings. Regular users see entity history through ChangeSets, not run records. A user viewing the history of Medieval Madness sees "IPDB updated these fields on March 28" (the ChangeSet), not "IPDB run #47 processed 4,000 machines" (the IngestRun). The IngestRun is reachable from the ChangeSet for admin drill-down, but it is not part of the user-facing entity history.

### Apply layer

The apply layer is source-agnostic. It processes the three primitive operations (`create_entity`, `assert_claim`, `retract_claim`) and contains no source-specific logic.

1. **Create IngestRun** (before transaction) — record source, start time, input fingerprint, status=`running`
2. **Open transaction:**
   a. **Create entities** — execute `create_entity` operations, capture PKs, patch them into associated claims
   b. **Validate** — run `validate_claims_batch` on planned `assert_claim` operations (see [ValidationFix.md](ValidationFix.md) Component B). Invalid claims are rejected with warnings, not persisted.
   c. **Persist assertions** — bulk-create a ChangeSet per target entity, bulk-create new Claim rows linked to their ChangeSet. Unchanged claims (same value already active for this source) are skipped. ChangeSet creation must be batched (`bulk_create`), not one `create()` per entity in a loop.
   d. **Persist retractions** — for any `retract_claim` operations, deactivate the targeted claims (set `is_active=False` and `retracted_by_changeset` to the entity's ChangeSet)
   e. **Resolve** — materialise affected entities (same resolution layer as today)
3. **Finalise IngestRun** (after transaction) — update counts, status, end time

The IngestRun record is created and updated **outside** the apply transaction. If the transaction rolls back on failure, the IngestRun still survives with status=`failed` and error details — which is exactly when you most want the audit record. ChangeSets and claims are created **inside** the transaction, so partial ingest state never persists on failure.

Source adapters never open transactions or write to the database. The data models (IngestRun, ChangeSet.ingest_run FK, Claim.retracted_by_changeset FK) are implemented. The database will be deleted and migrations reset to `0001` as part of the remaining work, so no backfill or data migration is needed.

### Run reports

The IngestRun record is the persisted form of the run report. In dry-run mode the same report is produced as an in-memory data structure but not written to the database. Either way, the report should make it possible to answer "what happened?", "what changed?", "what was skipped?", and "what needs human curation?" without reading logs or re-running the import.

### Dry run

Because the planner is fully non-mutating, dry run is straightforward: parse, reconcile, collect claims, validate, emit report, apply nothing. No rollback transactions needed. The plan is the same object whether or not it gets applied.

### Testing

The most valuable tests target the plan boundary: given these source records and this database state, what change plan is produced? This directly exposes source-attribution decisions, claim-intent policy, and source permission enforcement without requiring end-to-end command execution. Integration tests still matter but sit on top of a more inspectable model.

### Domain ownership enforcement

The architecture cannot decide which model owns a fact — that is a domain decision humans make. But it can make that decision **enforceable** once made.

Today nothing prevents a source adapter from attaching company facts to `Manufacturer` instead of `CorporateEntity`. That's how the Fandom and Wikidata TODOs happened: both sources target `Manufacturer` for company metadata that should live on `CorporateEntity`, and nothing in the system caught or prevented it.

Source policy declarations should include which models and fields a source is permitted to assert claims against. The apply layer can then reject claims that target a model/field combination the source hasn't declared. This turns "emit claims against the right model" from a convention that source authors must remember into a constraint the framework enforces.

The architecture does not decide that company metadata belongs on `CorporateEntity` rather than `Manufacturer`. It makes that decision — once made — hard to violate accidentally.

## `ingest_pinbase` is a special case

The plan/apply model fits IPDB, OPDB, Fandom, and Wikidata naturally. Each is an external source that focuses on one or two entity types per run. `ingest_pinbase` is fundamentally different.

`ingest_pinbase` is the editorial source that seeds the entire catalog. It processes 12 entity types in dependency order (taxonomy, themes, gameplay features, manufacturers, corporate entities, systems, people, series, titles, models), each with its own matching logic, claim shapes, and resolution steps. Later phases depend on rows created by earlier phases (e.g. titles reference manufacturers and systems that were ingested in prior phases).

This does not fit cleanly into "one source adapter produces one plan, the apply layer executes it."

The right approach is a **compound plan**: the pinbase adapter produces a plan with ordered sub-plans, one per entity type (or logical group). The apply layer executes them sequentially within one transaction, making each sub-plan's entities available to the next.

This is the only option that preserves full atomicity naturally — if any phase fails, the entire pinbase ingest rolls back. The alternatives (multiple independent plan/apply cycles, or a hybrid that applies each phase independently) reintroduce the non-atomicity problem unless wrapped in an outer transaction, which negates the benefit of separate cycles.

The compound plan also maps most closely to the current phase structure, making migration straightforward: each `_ingest_*` method becomes a sub-plan builder rather than an imperative mutate-as-you-go method. The apply layer handles entity creation, claim persistence, and resolution for each sub-plan in sequence. Each sub-plan must not have direct ORM writes to claim-controlled fields, and entity creation must be explicit and provenance-backed.

## Entity lifecycle

In the current system, entity creation is a direct ORM write with no provenance. Once a row exists, there is no claims-based mechanism to mark it as invalid, remove it, or record that it's a duplicate. Entity existence is ground truth that can't be disputed through the same system that manages everything else.

This is wrong. A source asserting "this machine exists" is no different from a source asserting "this machine's year is 1992" — both are facts attributed to a source, and both should be disputable.

### Entity status as a claim-controlled field

Every catalog entity gets a `status` field with three values:

- **`active`** — the entity is live in the catalog (default)
- **`deleted`** — the entity should not exist (data entry error, bad ingest, malicious actor)
- **`duplicate`** — the entity is a duplicate of another entity

`status` is claim-controlled like any other catalog field. Resolution picks the winner by source priority. An editorial claim (priority 300) asserting `status=deleted` overrides any external source's implicit `status=active`.

### Duplicate handling

Entities marked `status=duplicate` also have a `duplicate_of` relationship claim pointing to the canonical entity. This follows the same pattern as `variant_of`, `conversion_of`, and `remake_of` — a relationship claim pointing to another entity of the same type.

Claims on the duplicate do not move to the canonical entity. They stay as historical record — "IPDB said this about machine X" remains true even after we determine machine X is a duplicate of machine Y.

### Soft delete

Entity rows are never hard-deleted. A `status=deleted` or `status=duplicate` entity remains in the database with all its claims intact. The provenance trail records who marked it, when, and why (via the claim's citation and changeset). Catalog queries filter on `status=active` to exclude inactive entities from the live catalog.

This also supports restoration — if a deletion was wrong, re-asserting `status=active` with sufficient priority reverses it through normal claim resolution.

### Scenarios

**Data entry error / bad ingest.** A user asserts `status=deleted` with a citation explaining why. The entity disappears from the active catalog but its history survives.

**Duplicate detection.** A user asserts `status=duplicate` and a `duplicate_of` claim pointing to the canonical entity. The duplicate disappears from the active catalog; references can redirect via `duplicate_of`.

**Actor revocation.** All claims from a bad actor are retracted. Entities they created that have since been confirmed by other sources retain their `status=active` claim from those other sources and survive. Entities with no remaining `status=active` claim from any source surface for review.

## What This Does Not Solve

**Domain modeling decisions.** The architecture enforces domain ownership but does not decide it. Which model owns which facts is a domain decision that must be made separately. The existing Fandom and Wikidata TODOs (targeting `Manufacturer` when they should target `CorporateEntity`) are domain fixes that the architecture would then enforce.

**Source-specific parsing complexity.** IPDB's gameplay feature extraction with multiball special-casing, Fandom's wiki fetching and near-duplicate detection, IPDB's encoding corruption handling — these are essential complexity that no architecture can remove. The architecture gives them a clear home (the source adapter) and keeps them out of the apply layer, but they remain code that must be written and maintained per source.

## What Stays Source-Specific

- Parsing raw data into typed records
- Which external ID field to check during reconciliation, and any domain-specific overrides to the default fallback chain
- Field mappings
- Name and encoding policy
- Entity creation decisions
- Complex claim-intent policy that cannot be expressed as data

## What Stops Being Source-Specific

- Transaction management
- Entity reconciliation fallback chain (external ID → exact name → exact alias)
- Claim persistence and retraction
- Resolution orchestration
- Run reporting
- The "collect into a list, then bulk_assert, then resolve" boilerplate that every command currently reimplements

## Relationship to ValidationFix

[ValidationFix.md](ValidationFix.md) established the claim boundary as the place where validation happens and built the machinery (`validate_claim_value()`, `validate_claims_batch()`, `classify_claim()`). This plan reuses that machinery in the apply layer — it does not replace or duplicate it.

The two plans address different layers of the same problem:

- **ValidationFix** answers: "given a claim, is it valid?" (claim-content validation at the boundary)
- **IngestRefactor** answers: "should this claim exist at all, and how does it get to the boundary?" (claim-intent policy, source permissions, transaction management)

ValidationFix step 7 adds a field validator audit to ensure model fields carry adequate validators. This complements the ingest redesign — the apply layer's validation step is stronger when the fields carry adequate validators, but the refactor does not depend on it. The two can proceed in parallel.

## Non-Goals

This document defines the target architecture. It does not:

- Prescribe a migration order for the existing code
- Define every dataclass or module in final detail
- Choose a storage format for planned entity identities or run metadata
- Decide exact package layout beyond the architectural split into source adapters and apply layer
