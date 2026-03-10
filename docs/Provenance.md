# Provenance System

## Two-Layer Architecture

The catalog uses a **claims-based provenance system** with two layers:

1. **Claims layer** — A stream of source-attributed facts. Each claim is a single assertion by a Source (external database, book, editorial team) or User about one field of one catalog entity. Multiple sources can assert different values for the same field.

2. **Resolution layer** — Materialized model fields derived from claims via priority-based conflict resolution. The highest-priority source wins. Resolution is deterministic and repeatable.

Provenance tracks **attribution**, not just disputes. Every piece of catalog data may eventually come from a different source or user, and the system must always be able to answer "who said this, and where did it come from?"

## Claims

A **Claim** asserts a single fact: "Source X says Entity Y's field Z has value V."

Key properties:

- **Target**: Any catalog entity (via generic foreign key)
- **Attribution**: Exactly one of `source` (external) or `user` (human contributor)
- **Field**: `field_name` identifies what's being claimed (e.g. "name", "year", "credit")
- **Claim key**: Uniqueness identifier. For scalar fields this equals the field name. For relationships it encodes the relationship identity (e.g. `credit|person:pat-lawlor|role:design`)
- **Value**: The asserted data (JSON)
- **Superseding**: A new claim from the same source for the same claim key deactivates the old one

### Scalar Claims

Simple field values: name, year, player count, manufacturer (by slug), etc.

### Relationship Claims

Structured relationships with identity: credits (person + role), themes, tags, gameplay features, abbreviations. Each relationship instance gets its own claim key encoding its identity parts.

## Resolution

Resolution picks a winner per field/claim-key and materializes the result:

- Claims ordered by source priority (descending), then creation date
- Highest-priority source wins
- Scalar winners are coerced to the appropriate field type and set on the model
- Relationship winners are materialized into M2M tables or dedicated records

## The Rule

**Every catalog field must be claims-based.** This includes scalar fields, foreign keys, and relationships. The only exempt fields are internal infrastructure: `id`/`uuid`, `created_at`/`updated_at`, and `slug`.

If you think a field needs an exception, ask the user first.

## Known Exceptions Pending Migration

- `variant_of` on MachineModel — currently a direct FK, should be migrated to claims

## Key Code

- `backend/apps/provenance/models.py` — Source, Claim, ClaimManager
- `backend/apps/catalog/claims.py` — Relationship schemas and claim key helpers
- `backend/apps/catalog/resolve/` — Resolution logic
