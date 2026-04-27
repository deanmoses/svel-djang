# Backend Testing

Backend tests use `pytest` with `pytest-django`.

## What to Test

- model behavior and DB constraints
- claim/provenance behavior
- ingest behavior
- API behavior
- management command behavior where it matters

## DB Constraint Testing

When testing DB constraints, prefer direct ORM writes that hit the database constraint path rather than relying on `full_clean()`. See [DataModeling.md](DataModeling.md).

## Typing private helpers for stand-in test inputs

When a private helper exists to validate a contract (system checks, registry walkers, etc.) and its tests want to pass synthetic stand-ins to exercise individual error branches, prefer **duck typing the helper signature** over `# type: ignore[arg-type]` at every test call site.

The pattern: declare the public entry point with the real type (`type[LinkableModel]`, `type[Model]`, etc.) so production callers stay tight. Then have it delegate to a private `_check_one(model: type, ...)` (or `type[object]`) that uses `getattr` to read the contract attributes. Production callers still flow through with full typing; tests pass `BadModel`, `MissingX` stand-ins without ignores.

See [`apps/core/checks.py`](../../backend/apps/core/checks.py) and [`apps/core/tests/test_linkability_contract.py`](../../backend/apps/core/tests/test_linkability_contract.py) for the worked example. The private helper's body is already duck-typed via `getattr`; loosening the static type only catches up to what the runtime is doing.
