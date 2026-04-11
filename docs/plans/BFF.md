# Page Module Namespace

> Status: Not pursuing. We decided the proposed `pages/`/BFF split adds churn and indirection without enough architectural payoff.

Page-oriented endpoints need cross-app reads. This document defines where that code lives and how the exception is scoped.

## Problem

Page endpoints ([WebApiDesign.md](../WebApiDesign.md)) need data from multiple apps, but [AppBoundaries.md](../AppBoundaries.md) restricts cross-app dependencies. Today, the cross-app reads happen in general API modules (`catalog/api/titles.py` imports from `provenance`, `media`, `core`) with no structural distinction from domain-native code. The exception is implicit.

## Proposal

Each app that owns page endpoints gets an explicit `pages/` module namespace. Only `pages/` modules may use cross-app read imports for page composition. The route definitions in `api/page_endpoints.py` stay where they are.

```text
backend/apps/catalog/
  api/
    page_endpoints.py      # route definitions (thin, stays here)
    titles.py              # resource API (no cross-app page reads)
  pages/
    __init__.py
    titles.py              # page queryset, prefetch, annotation logic
    manufacturers.py
    schemas.py             # page-specific DTOs
    helpers.py             # shared presentation helpers (page-only)

backend/apps/provenance/
  api.py
  page_endpoints.py        # route definitions (stays here)
  pages/
    __init__.py
    evidence.py
    changes.py
    schemas.py
```

## What moves

Today, modules like `catalog/api/titles.py` contain both resource-API code and page-specific queryset functions (`_detail_qs`, `_serialize_title_detail`). Those page-specific functions — along with their cross-app imports (`build_sources`, `claims_prefetch`, `EntityMedia`, etc.) — move into `pages/`. The resource-API code stays in `api/`.

`page_endpoints.py` becomes a thin routing layer that imports from `pages/` instead of from sibling API modules.

## The real exception

The real exception here is ORM/queryset composition.

For page-only read composition, `pages/` modules may:

- import peer app models as needed
- build cross-app querysets as needed
- compose page-specific read shapes directly

That is the actual dependency being allowed. It is not a separate service layer, and it should not be disguised as one.

## The rule

- Only `pages/` modules may import from peer apps for page composition.
- Only `page_endpoints.py` may import from `pages/`.
- Resource API modules, admin, signals, commands, ingestion, and resolve code may not import from `pages/`.
- `pages/` modules are read-only. No writes, no business invariants, no domain truth.

## Enforcement

Enforced by documentation and code review, not by tooling. The `pages/` boundary is an intra-app convention — `import-linter` cannot express "only one sibling module within the same app may import a sub-package" without fighting its contract model (shared-descendant conflicts between `source_modules` and `forbidden_modules`).

The rules are simple enough for AI-assisted development and review to apply consistently:

- Only `page_endpoints.py` may import from `pages/`.
- `pages/` modules are read-only composition — no writes, no business invariants.
- Resource API modules, admin, signals, commands, ingestion, and resolve code must not import from `pages/`.

See [AppBoundaries.md](../AppBoundaries.md) for the documented exception.

## Migration

1. Create `catalog/pages/` — extract `_detail_qs`, `_serialize_*_detail`, page schemas, and their cross-app imports from `catalog/api/titles.py`, `manufacturers.py`, etc.
2. Update `catalog/api/page_endpoints.py` to import from `catalog/pages/` instead of from sibling API modules.
3. Repeat for `provenance/pages/` — extract evidence-building and change-feed logic from `provenance/page_endpoints.py`.
4. Move cross-app imports out of resource API modules (e.g., `build_sources` in `catalog/api/titles.py` moves to `catalog/pages/titles.py`).

Steps 1-4 can be done one entity at a time. No flag day needed. See [BFFMigration.md](BFFMigration.md) for the step-by-step playbook.

## Rejected alternatives

**Dedicated `apps.pages` app** — Centralizes unrelated page code without removing the ORM-level coupling. Title page queries require deep knowledge of catalog models; separating them into a different app moves code away from the models it queries without reducing coupling. Ownership becomes unclear.

**Cross-app read contracts as a default abstraction** — Most of the real work lives in querysets, prefetches, and annotations. Adding a contract/interface layer on top doesn't solve the coupling — the ORM composition is the coupling. It adds abstraction without addressing the actual source of dependency.

**Keep current implicit pattern** — Cross-app reads for page composition are already happening in general API modules. Without structural separation, the exception cannot be reviewed or enforced.

## Rejected tooling

**`import-linter`** was evaluated and rejected. Its `forbidden` contract type requires `source_modules` and `forbidden_modules` to have no shared descendants. Since `pages/` lives inside the app (e.g. `apps.catalog.pages` is a descendant of `apps`), any contract scoping `source_modules` broadly enough to be useful conflicts with `forbidden_modules` targeting the child package. Enumerating every non-pages module explicitly would work but is brittle — every new module requires a contract update. The rule is clear enough for documentation and review.
