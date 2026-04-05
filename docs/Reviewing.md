# Reviewing

This document is for AI reviewers. It's a checklist of project-specific rules.

## Review Priorities

When reviewing a change, check in roughly this order:

1. behavioral regressions
2. architectural rule violations
3. missing tests or weak verification
4. documentation or generated-artifact drift
5. style and cleanup issues

Do not lead with style feedback when there are more important correctness or architecture problems.

## Repo-Specific Checks

### App boundaries

When a change adds modules, imports, or new backend entrypoints, check [AppBoundaries.md](AppBoundaries.md).

In particular:

- `core` should not depend on `catalog`, `provenance`, or `media`
- `catalog`, `provenance`, and `media` must not depend on each other (peer isolation)
- new APIs for catalog entities usually belong in `apps.catalog`
- cross-app coupling should be treated as an architecture issue, not a convenience refactor

### Claims and provenance

When a change touches catalog models, fields, or relationships, check [Provenance.md](Provenance.md) and [DataModeling.md](DataModeling.md).

In particular:

- new catalog fields must be claim-controlled (exceptions require explicit user approval)
- "only one source today" is not a valid reason to bypass provenance
- model constraints should be enforced in the database, not only in Python

### Svelte SSR / CSR boundaries

When a change touches routes, layouts, or data loading, check [Svelte.md](Svelte.md).

In particular:

- public content pages should usually use SSR
- authenticated or highly interactive app surfaces may need `ssr = false`
- changing a parent layout's SSR mode can silently change all child routes — audit child routes and add explicit `ssr = false` where needed
- SSR routes must use `createServerClient` from `$lib/api/server`, not the browser client or ad hoc fetch

### Page-oriented APIs

When a change introduces or changes web-facing endpoints for pages, check [WebApiDesign.md](WebApiDesign.md).

In particular:

- important SSR pages should usually fetch one page-oriented endpoint
- page-shaped endpoints should usually live under `/api/pages/...`
- those endpoints should usually be tagged `tags=["private"]`
- avoid frontend fanout when the backend can return the page model directly

### Deployment/runtime assumptions

When a change affects routing, SSR, startup, or runtime ports, check [Hosting.md](Hosting.md) and [WebArchitecture.md](WebArchitecture.md).

In particular:

- same-origin assumptions must remain coherent
- Caddy, Django, and SvelteKit routing must agree
- health checks should reflect real readiness, not only partial readiness

## Generated And Derived Artifacts

Review whether the change also needed to update derived artifacts.

Common examples:

- OpenAPI-derived frontend types after API changes
- `AGENTS.md` / `CLAUDE.md` after editing `docs/AGENTS.src.md`
- docs that describe route behavior, hosting, or API shape after architecture changes

Missing regeneration is a valid finding when it will leave the repo inconsistent.

## What Counts As A Finding

Call something a finding when it is likely to cause one of these:

- broken behavior
- architectural drift that will make later work harder or unsafe
- misleading tests that no longer prove what they claim
- documentation or generated files that leave the repo internally inconsistent

Prefer concrete, repo-specific reasoning over abstract best practices.

## What Usually Does Not Count

These are usually not findings by themselves:

- a different but coherent style choice
- a simplification you would not personally choose
- a hypothetical cleanup that is unrelated to the change
- a test shape you would prefer, if the current test still proves the intended behavior

Do not invent blockers just because a different design would also work.

## Review Discipline

Before flagging an issue:

- check the relevant doc for the area
- verify that the code actually violates that doc or contract
- distinguish a stale reference from a runtime bug
- prefer one precise finding over three speculative ones

The goal is not to maximize comments. The goal is to catch real problems and keep the repo aligned with its own rules.
