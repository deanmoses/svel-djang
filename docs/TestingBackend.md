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
