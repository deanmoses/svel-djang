# Testing

This document describes the project's testing expectations and strategy.

## Running Tests

### Main Commands

- `make test` runs the main backend and frontend test suites
- backend tests use `pytest`
- frontend tests use `vitest`

Use narrower commands when appropriate during development, then widen as needed for confidence.

### Core Rule

For any change, identify and run the smallest meaningful test set.

Do not default to running everything if a narrower test selection will give the answer you need.

### How To Choose a Test Scope

#### Prefer the smallest meaningful scope

Examples:

- a pure backend model/helper change: run the relevant backend tests first
- a frontend component or module change: run the relevant frontend tests first
- a schema or cross-cutting change: run the focused local tests, then widen appropriately

### Widen when risk increases

Run a broader set when:

- the change affects shared infrastructure
- the change crosses app boundaries
- the change affects generated API contracts or backend/frontend integration
- the narrow tests do not give enough confidence

## Writing Tests

### Bug Fixes Require TDD

When fixing a bug, follow this order:

1. Write a failing test that reproduces the bug.
2. Run the test and confirm it fails for the expected reason.
3. Fix the code.
4. Run the test again and confirm it passes.

Do NOT fix the bug first and backfill the test later.

### Backend Testing

Backend tests should generally cover:

- model behavior and DB constraints
- claim/provenance behavior
- ingest behavior
- API behavior
- management command behavior where it matters

When testing DB constraints, prefer direct ORM writes that hit the database constraint path rather than relying on `full_clean()`. See [DataModeling.md](DataModeling.md).

### Frontend Testing

Frontend tests should generally cover:

- TypeScript module logic
- component behavior where UI wiring matters
- data-shape expectations against the API contract where appropriate

Prefer testing logic in small TypeScript units where possible rather than over-relying on broad UI tests.

### Documentation and Tests

When a doc describes a strict engineering rule that affects implementation behavior, make sure the code and tests reflect it. Documentation alone is not enforcement.

Relevant supporting docs:

- [Development.md](Development.md)
- [DataModeling.md](DataModeling.md)
- [Architecture.md](Architecture.md)
- [AppBoundaries.md](AppBoundaries.md)

## To Expand

This doc is intentionally a skeleton. It will likely grow sections for:

- concrete command examples
- test layout by area
- fixtures and helper conventions
- frontend testing patterns
- integration vs unit guidance
- coverage expectations, if the project wants them
