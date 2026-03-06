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

## Project Overview

Django + SvelteKit monorepo. Django owns the data model, APIs (Django Ninja), and admin UI. SvelteKit handles the user-facing frontend with static adapter (CSR for authenticated pages, prerendered for public pages).

**Key architectural decisions:**

- Session-based auth via same-origin proxy (no JWT, no CORS)
- Auth gating in the SPA is UX-only; the backend is the source of truth for access control
- OpenAPI types generated from Django Ninja schema (not committed, derived from backend)
- Single domain: `/api/` and `/admin/` route to Django, everything else to SvelteKit

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
- API types are generated from the Django Ninja OpenAPI schema — run `make api-gen` after changing API endpoints
- CSRF: Django sets `csrftoken` cookie; the frontend `client.ts` reads it and sends `X-CSRFToken` on mutating requests
- Vite dev server proxies `/api/` and `/admin/` to Django at `127.0.0.1:8000`

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

END_AGENTS

## Rules

- Don't silence linter warnings — fix the underlying issue
- Never hardcode secrets — use environment variables via `.env`
- Write tests for new behavior
- Describe your approach before implementing non-trivial changes
