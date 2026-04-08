# Testing

This document describes the project's testing expectations and strategy. For guidance specific to Django and Svelte, see:

- [TestingBackend.md](TestingBackend.md) — Django/pytest patterns
- [TestingFrontend.md](TestingFrontend.md) — Vitest tiers, DOM test patterns, jsdom setup

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
