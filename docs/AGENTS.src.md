# Development Guide

START_IGNORE

This is the source file for generating [`CLAUDE.md`](../CLAUDE.md) and [`AGENTS.md`](../AGENTS.md).
Do not edit those files directly - edit this file instead.

Regenerate with: make agent-docs

Markers:

- START_CLAUDE / END_CLAUDE - content appears only in [`CLAUDE.md`](../CLAUDE.md)
- START_AGENTS / END_AGENTS - content appears only in [`AGENTS.md`](../AGENTS.md)
- START_IGNORE / END_IGNORE - content stripped from both (like this block)

END_IGNORE

This file provides guidance to AI programming agents when working with code in this repository.

## Python Style — Non-Negotiable

`except ExcType1, ExcType2:` is **valid Python 3** and is ruff-format's preferred style.
Do NOT add parentheses. `except (ExcType1, ExcType2):` will be reverted by ruff-format every time. Stop trying to fix it.

## Svelte, HTML, CSSS

### You MUST use Svelte 5 — Non-Negotiable

The frontend uses **Svelte 5 runes mode** (`runes: true` in compiler options). Do NOT use legacy Svelte 4 patterns:

- `export let` → use `let { } = $props()`
- `$:` reactive declarations → use `$derived` / `$derived.by()` / `$effect()`
- `on:click` directive syntax → use `onclick` attribute
- `createEventDispatcher` → use callback props
- `<slot>` → use `{@render children()}` snippets
- `$$props` / `$$restProps` → use `$props()` with rest syntax

### CSS — Non-Negotiable

NEVER use `:global` in Svelte component styles without explicit approval from the user. Scoped styles are the default and preferred approach. We rearchitect components rather than use `:global`.

## ALL User-Inputted Catalog Fields MUST be Claims-Based — Non-Negotiable

**Every user-inputted catalog field MUST be claims-based**: scalars, FKs, M2M, slugs, parents, aliases. This includes ingested data that goes into fields that users can input.

**System-generated fields aren't claims-based**: `id`/`uuid`, timestamps, derived fields like `Location.location_path = f"{parent.location_path}/{slug}"`.

The test is "could a user input this field?" If yes, claim it. If no, it's system-generated. There is no third category. See [docs/Provenance.md](Provenance.md) for the architecture.

### Writing ChangeSets — `action` Is Required On User ChangeSets

Every `ChangeSet` attributed to a user must carry an `action` value (`create`, `edit`, `delete`, or `revert`). Ingest ChangeSets never do — they're identified by the `ingest_run` FK. The DB enforces this via the `provenance_changeset_action_iff_user` check constraint, so forgetting means an `IntegrityError`, not a code-review catch.

Prefer the factories over `ChangeSet.objects.create` in new code:

- Application code: call `execute_claims(entity, specs, user=..., action=ChangeSetAction.EDIT)` — the action kwarg is required at the type level for readability, even though `EDIT` is the default. Revert writes use `ChangeSetAction.REVERT`. Create flows use `ChangeSetAction.CREATE`.
- Test fixtures: use `from apps.provenance.test_factories import user_changeset, ingest_changeset` instead of constructing `ChangeSet` rows directly. The factories encode the constraint invariants so mistakes fail at call time, not at DB time.

## Project Overview

Django + SvelteKit monorepo. Django owns the data model, APIs (Django Ninja), and admin UI. SvelteKit handles the user-facing frontend with Node SSR for public pages and CSR for authenticated app pages.

Catalog data and the DuckDB exploration database live in separate repos:

- **[pindata](https://github.com/deanmoses/pindata)** — canonical catalog records (markdown files + JSON schemas)
- **[pinexplore](https://github.com/deanmoses/pinexplore)** — DuckDB exploration/validation database

Both publish to Cloudflare R2. Pinbase pulls catalog JSON exports from R2 via `make pull-ingest`.

See [DomainModel.md](DomainModel.md) for the catalog entity hierarchy (Title → Model, variants, remakes, manufacturers, taxonomy, etc.).

**Key architectural decisions:**

- Session-based auth via same-origin proxy/reverse proxy (no JWT, no CORS)
- Auth gating in the SPA is UX-only; the backend is the source of truth for access control
- OpenAPI types generated from Django Ninja schema (not committed, derived from backend)
- Single domain: `/api/`, `/admin/`, `/media/`, and `/static/` route to Django, everything else to SvelteKit

## Requirements

- Python 3.14+
- Node 24+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [pnpm](https://pnpm.io/) (Node package manager, or enable via `corepack enable`)

## Getting Started

```bash
cp .env.example .env
make bootstrap
make dev
```

Then open http://localhost:5173

To create a Django admin superuser:

```bash
cd backend && uv run python manage.py createsuperuser
```

## Development Commands

```bash
make bootstrap    # Install all deps, run migrations, generate API types
make dev          # Start Django + SvelteKit dev servers
make test         # Run pytest (backend) + vitest (frontend)
make lint         # Run ruff (backend) + eslint/prettier (frontend)
make pull-ingest  # Download catalog data from R2
make ingest       # Run full ingestion pipeline
make agent-docs   # Regenerate CLAUDE.md and AGENTS.md
```

## Project Structure

```text
backend/          Django project (uv, pyproject.toml)
  config/         Django settings, urls, wsgi, asgi
  apps/           Django apps
frontend/         SvelteKit project (pnpm)
  src/lib/api/    Generated types (schema.d.ts) + hand-written client (client.ts)
  src/routes/     SvelteKit routes
scripts/          POSIX shell scripts
docs/             Documentation source files
```

## Key Conventions

- Backend dependencies managed with `uv`, frontend with `pnpm`
- CSRF: Django sets `csrftoken` cookie; the frontend `client.ts` reads it and sends `X-CSRFToken` on mutating requests
- Vite dev server proxies `/api/`, `/admin/`, `/media/`, and `/static/` to Django at `127.0.0.1:8000`
- For SSR route conventions, see [Svelte.md](Svelte.md). For API design — both endpoint shape (page-oriented vs resource) and schema design heuristics (when to consolidate, when to keep separate, inheritance smells) — see [ApiDesign.md](ApiDesign.md)

### Generated Types — `schema.d.ts` is gitignored

`frontend/src/lib/api/schema.d.ts` is generated and **not committed**. Do not stage or commit it. After adding or changing any API endpoint, run `make api-gen` to regenerate it — the typed client will not see new endpoints until you do.

### Frontend URLs and `resolve()`

SvelteKit's `resolve()` from `$app/paths` is strongly typed and only accepts known route patterns. For dynamic URLs (e.g. from API data), use the `resolveHref()` wrapper from `$lib/utils` instead:

```svelte
<script lang="ts">
  import { resolveHref } from '$lib/utils';
</script>

<!-- Internal dynamic URL -->
<a href={resolveHref(someUrl)}>Link</a>

<!-- External URL — don't use resolve at all -->
<a href={externalUrl} target="_blank" rel="noopener">Link</a>
```

The `svelte/no-navigation-without-resolve` ESLint rule is disabled project-wide because it doesn't recognize the wrapper.

START_CLAUDE

## Tool Usage

Use Context7 (`mcp__context7__resolve-library-id` and `mcp__context7__query-docs`) to look up current documentation when:

- Implementing Django features (models, views, forms, admin, etc.)
- Working with SvelteKit routing, adapters, or configuration
- Configuring Railway hosting and deployment
- Answering questions about library APIs or best practices

GitHub access:

- Use the GitHub MCP server for read-only operations (listing/viewing issues, PRs, commits, files)
- Use the `gh` CLI for writes or auth-required actions (creating/updating/commenting/merging)

END_CLAUDE

START_AGENTS

## Environment Setup (Codex Cloud)

The Makefile works without a venv — it detects the environment automatically.

**Setup command**: `bash scripts/bootstrap`

After setup, use the standard commands:

```bash
make test         # Run tests
make lint         # Lint and format check
```

**Notes:**

- Internet is disabled during task execution — all dependencies must be installed during setup
- Tests use SQLite in-memory by default
- Use the `gh` CLI for GitHub operations
- For multi-session Codex worktree setup only, see [docs/CodexWorktrees.md](docs/CodexWorktrees.md)

END_AGENTS

## Data Ingestion

The catalog app has management commands for importing from external data sources (IPDB, OPDB, Fandom wiki, etc.). Run `make pull-ingest` to download data from R2, then `make ingest` to run the pipeline. See [docs/Ingest.md](Ingest.md) for sources, file formats, and production ingestion steps.

## Pre-commit Hooks

Pre-commit hooks auto-regenerate `CLAUDE.md` and `AGENTS.md` when `docs/AGENTS.src.md` changes, and block direct edits to those generated files. Hooks also run ruff, ESLint, type checks, and the full test suite. Do not edit `CLAUDE.md` or `AGENTS.md` directly — edit `docs/AGENTS.src.md` instead.

## Deployment

Single Railway service: Caddy fronts SvelteKit Node SSR and Django/Gunicorn inside one container. Multi-stage Dockerfile builds the frontend with Node/pnpm, then copies the SSR runtime into the Python image. WhiteNoise still serves Django static assets, while Caddy routes frontend requests to SvelteKit and `/api/`/`/admin/` to Django. See [docs/Hosting.md](Hosting.md) for setup and troubleshooting.

## Testing

- For any change, identify and run the smallest meaningful test set.

### Bug Fixes Require TDD — Non-Negotiable

When fixing a bug, you **MUST** follow this exact order:

1. **Write a failing test first** that reproduces the bug.
2. **Run the test** and confirm it fails for the expected reason.
3. **Then fix the code** to make the test pass.
4. **Run the test again** and confirm it passes.

Do NOT skip step 1. Do NOT write the fix first "to understand the problem" and backfill tests after. The failing test _is_ how you understand the problem.

### New Features

For new behavior, include tests. Consider writing the test first, though sometimes that's more trouble than it's worth.

## Data Modeling

See [docs/DataModeling.md](DataModeling.md) for modeling principles, Django pitfalls, and constraint testing patterns. Key rules:

- **Validate strictly** — start with the tightest constraint you can defend. Relaxing is a one-line migration; tightening requires auditing every row.
- **Validate in the database** — `full_clean()` is optional; CHECK constraints are not. Use `field_not_blank()`, CHECK constraints for enums/ranges, and UNIQUE constraints for identity rules.
- **Default to `PROTECT`** on foreign keys. Use `CASCADE` only for wholly owned children.

## Code Review

When reviewing code or a PR, read [docs/Reviewing.md](Reviewing.md) first and follow its checklist.

## Rules

- Don't silence linter warnings — fix the underlying issue
- Never hardcode secrets — use environment variables via `.env`
- Describe your approach before implementing non-trivial changes
