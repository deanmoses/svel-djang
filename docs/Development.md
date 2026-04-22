# Development

This document is the contributor-facing hub for working on the Pinbase codebase.

It does not try to restate every project rule. Instead, it points to the more specific docs that define how work in this repository should be approached.

## Start Here

- [../README.md](../README.md) for setup, commands, and local development
- [Architecture.md](Architecture.md) for the top-level system map
- [WebArchitecture.md](WebArchitecture.md) for the Django + SvelteKit web stack
- [Svelte.md](Svelte.md) for route-level rendering choices and SvelteKit page conventions
- [WebApiDesign.md](WebApiDesign.md) for frontend/backend API design rules for pages and SSR
- [SSRConversion.md](SSRConversion.md) for the step-by-step workflow for converting an existing route subtree from CSR to SSR
- [Reviewing.md](Reviewing.md) for repo-specific review checks, especially for AI reviewers
- [AppBoundaries.md](AppBoundaries.md) for backend app dependency rules
- [DomainModel.md](DomainModel.md) for the business/domain model of pinball

## Modeling and Schema Work

When changing models, constraints, or persistence structure, read:

- [DataModeling.md](DataModeling.md)

If a lower-level technical data-model reference is added later, link it here.

## Testing

For testing expectations and strategy, read:

- [Testing.md](Testing.md)

## Type Checking

The backend uses **mypy** with the **django-stubs** plugin. Pre-commit runs mypy in daemon mode (`dmypy`) so full-project analysis stays fast on every commit. A baseline at `backend/mypy-baseline.txt` captures known-accepted findings; pre-commit and CI only fail on _new_ errors above the baseline.

**If local mypy disagrees with CI,** the daemon is likely out of sync (common after branch switches or rebases). Run:

```sh
make mypy-restart
```

Other daemon commands: `make mypy-warm` (pays cold-start up front), `make mypy-status` (is the daemon alive?).

To regenerate the baseline after fixing errors: `cd backend && uv run mypy --config-file pyproject.toml . | uv run mypy-baseline sync`.

## Domain-Specific System Docs

When working in these areas, use the focused reference docs:

- [Svelte.md](Svelte.md) for route-level SSR/CSR choices and page-loading conventions
- [Provenance.md](Provenance.md) for claims, resolution, and audit model
- [Ingest.md](Ingest.md) for ingest architecture and source flow
- [WebApiDesign.md](WebApiDesign.md) for page-oriented API design and SSR-friendly endpoint shaping
- [Hosting.md](Hosting.md) for deployment and runtime operations

When a stable media reference doc exists, add it here as well.

## Working Across App Boundaries

Before adding imports across Django apps, read [AppBoundaries.md](AppBoundaries.md).

When strict app boundaries make integration awkward, prefer these patterns over widening imports:

- generic foreign keys and content types for cross-domain references where appropriate
- registration hooks, where a generic subsystem lets another app register behavior without becoming coupled to it
- serialized or value-level contracts rather than direct model imports
- orchestration in higher-level entrypoints, such as API composition or management commands, rather than deep lateral imports

The important rule is: solve integration by designing a boundary, not by punching through one.

## Principles

As a contributor, keep these distinctions clear:

- product and domain docs explain what Pinbase is modeling
- architecture docs explain how the system is organized
- development docs explain how to work safely in the codebase
- plan docs in [plans/README.md](plans/README.md) are historical reference, not canonical current documentation

## To Expand

This doc is intentionally a skeleton. It will likely grow sections for:

- common workflows
- code generation and derived artifacts
- local data and ingest setup
- frontend/backend development notes
- release or migration checklists
