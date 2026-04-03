# Name + Alias Cross Uniqueness

## The Problem

Some catalog entity types have unique names — Manufacturer, Theme, GameplayFeature, RewardType — meaning the name alone can resolve to exactly one entity during ingest and lookup. Each of these entities also has zero or more aliases that serve the same resolution purpose. If the same string appears as an entity's name and as another entity's alias (or as aliases on two different entities), resolution becomes ambiguous: which entity did the source mean?

This does not apply to entity types with non-unique names (Person, Location, CorporateEntity), where two records can have the same name -- two people can have the same name -- and are used for search but not for unambiguous resolution.

Today there are no collisions in the data. But as the system opens to end-user editing, fat-fingered entries will create them. The question is whether the system catches those mistakes before they land, or discovers them later as confusing search results.

## Current State

Application-level validation prevents collisions through four independent code paths:

1. **Model `clean()` methods** — reject name↔alias collisions on `full_clean()`
2. **API validation** — reject collisions in the edit claims endpoints
3. **Resolver filtering** — silently skip colliding aliases during batch ingestion
4. **Per-table DB constraints** — enforce name uniqueness within a single entity type, and alias uniqueness within a single alias table

The gap: nothing prevents a name in one table from matching an alias in another table at the database level. The checks are application-only, which means `bulk_create`, raw SQL, concurrent writes, or any future code path that doesn't know about the rule can introduce collisions silently.

## Proposed Architecture: NameRegistry

Add a single shared table that indexes every name and alias across all entity types:

| Column        | Purpose                                       |
| ------------- | --------------------------------------------- |
| `value`       | Lowercased string (unique)                    |
| `entity_type` | ContentType FK — which model owns this string |
| `entity_id`   | PK of the owning entity                       |
| `role`        | `"name"` or `"alias"`                         |

The `UNIQUE` constraint on `value` makes cross-table collisions impossible at the database level.

### What it is

An index table. Names and aliases still live on their respective models — the registry is a projection that the DB can enforce uniqueness on. It could be rebuilt from scratch by scanning the name fields and alias tables.

### What it replaces

The four independent application-level checks collapse into one mechanism. Model `clean()` methods, API cross-checks, and resolver name-set filtering all become unnecessary — the DB constraint does the work. The code simplifies from "check the rule in four places" to "write to the registry; the DB enforces the rule."

### How it stays in sync

Writes to name fields and alias tables must create/update/delete registry rows in the same transaction. This can be done via:

- The resolver (which already manages alias rows in bulk)
- The edit claims execute path (which already writes in a transaction)
- A post-save signal as a safety net

A periodic sweep (management command) can detect and report drift.

### What it enables beyond uniqueness

- **Conflict preview in the UI** — "is this string taken?" becomes a single indexed query
- **Global search** — one table to search for any entity by name or alias
- **Namespace reservations** — if needed later, reserve strings before an entity exists

## Migration Path

1. Ship the current application-level checks (already written, tested, passing) — they provide immediate protection for end-user editing.
2. Add the `NameRegistry` model and populate it from existing data.
3. Wire up the write paths (resolver + edit claims) to maintain the registry.
4. Remove the redundant application-level cross-checks, keeping only the registry.

Step 1 is ready now. Steps 2-4 can happen in a follow-up when the cost of the current approach (maintaining four code paths) outweighs the cost of the migration.

## Open Questions

- Should the registry include entity types that don't have aliases today (Series, Franchise)? Reserving their names in the shared namespace would prevent a future alias from colliding with them.
- Should the registry span across entity types? Today "Gottlieb" as a Manufacturer name and "Gottlieb" as a Theme name are allowed. Is that a problem?
- Is the registry the right place to enforce alias-to-alias uniqueness within a type, replacing the per-table `UniqueConstraint(Lower("value"))` constraints?
