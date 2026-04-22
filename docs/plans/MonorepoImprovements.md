# Monorepo Improvements

An honest assessment of the repo's monorepo hygiene, with prioritized, independent recommendations. The short version: monorepo setup here is already better than most — unified scripts, path-filtered CI, OpenAPI-as-contract between packages, and a single source of truth for dev setup. The gaps aren't missing _tools_ so much as missing _polish_ in the ones already in place.

## What's already working well

- Single-entry `make` + `scripts/` that wraps both stacks consistently.
- Path-filtered CI via `dorny/paths-filter` — skips unaffected package work.
- Typed contract (OpenAPI → `schema.d.ts`) generated at build time, not committed.
- Modern package managers in both ecosystems (`uv`, `pnpm`).
- Pre-commit runs the _same_ ruff binary as CI (pinned via `uv run`), eliminating platform formatting drift.

## The big question: Turborepo / Nx?

**Don't adopt them.** Turbo and Nx are designed for JS/TS-heavy polyrepos with many packages. This repo has exactly one JS package and one Python package. Turbo can't meaningfully cache Python work, and Nx's Python support is a heavy abstraction for very little win. The current `make` + `paths-filter` combo already delivers ~80% of what they'd provide. Revisit only if the repo splits into four or more packages.

## Recommendations, in priority order

Each item is independent — adopt in whatever order fits.

### 1. Stop bypassing installed tooling in pre-commit

Pre-commit currently shells out to `npx prettier@3.8.1 --write` and `npx markdownlint-cli2@0.21.0`. Two problems:

- **Prettier is already a `devDependency`** in `frontend/package.json` (pinned at `^3.8.1`). The `npx` call ignores that installation and fetches again. Pure waste.
- **markdownlint-cli2 is not installed anywhere**, so every pre-commit run downloads it fresh.

**Do:**

1. Add `markdownlint-cli2` to `frontend/devDependencies`.
2. Change the two pre-commit hooks to `bash -c 'cd frontend && pnpm exec prettier --write "$@"' --` and `bash -c 'cd frontend && pnpm exec markdownlint-cli2 "$@"' --` (or equivalent).

**Why it matters:** Uses the already-installed, already-pinned binaries. Faster hooks, no surprise version drift, no network dependency on every commit.

**What this explicitly is _not_:** a `pnpm` workspace or a root `package.json`. With only one JS package, a workspace is ceremony for little benefit — revisit only if a second JS package ever appears.

### 2. CODEOWNERS + Dependabot config

No `.github/CODEOWNERS` and no `.github/dependabot.yml` currently. Dependabot especially matters in a monorepo because there are four ecosystems to track: `pip` (via `uv`), `npm` (via `pnpm`), `github-actions`, and `docker`. Without config, three of those four get zero coverage.

**Do:** Add a `dependabot.yml` with four `updates:` entries (backend pip, frontend npm, github-actions, docker). Add a minimal `CODEOWNERS` even with a single reviewer — it routes PR reviews automatically and documents ownership.

### 3. Make targets that aren't `.PHONY`

Currently `api-gen` regenerates every time, even when nothing changed. Every target in the Makefile is `.PHONY`.

**Do:** Convert generation steps to real file targets with real dependencies. Example:

<!-- markdownlint-disable MD010 -->

```make
backend/openapi.json: $(shell find backend/apps -name 'api.py' -o -name 'schemas.py')
	cd backend && uv run python manage.py export_openapi_schema

frontend/src/lib/api/schema.d.ts: backend/openapi.json
	cd frontend && pnpm api:gen
```

<!-- markdownlint-enable MD010 -->

**Why it matters:** Turbo-style incremental rebuilds for free. Highest-leverage change if `make dev` feels slow.

### 4. A `make ci` target that mirrors CI exactly

Today `make lint` ≠ CI (CI also runs `pnpm check` and verifies type generation). `make quality` is closer but ad-hoc.

**Do:** Add a `make ci` target that runs the union of all CI jobs, in CI order. Document it as the one command to run before pushing.

**Why it matters:** Closes the "works on my machine" gap and gives contributors a single pre-push command.

### 5. Concurrency group in CI

`.github/workflows/ci.yml` has no `concurrency:` block, so every push to a PR branch runs the full matrix even if a previous run is still in flight.

**Do:** Add at workflow level:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

**Why it matters:** Saves minutes on every force-push.

### 6. `.editorconfig`

Not present. Cheap, universally understood, catches whitespace and EOL drift before ruff/prettier do.

**Do:** Add a repo-root `.editorconfig` that reflects the Python (4-space) and JS/Svelte (2-space) conventions already in use.

### 7. A `make doctor` / `scripts/doctor`

Verify dev environment assumptions and print actionable errors when they fail: `uv` installed, Node version matches `.node-version`, `pnpm` installed, `.env` present, Django migrations up to date, R2 creds set (when relevant), DB reachable.

**Why it matters:** Huge onboarding win. Most healthy monorepos have one because misconfiguration errors in a polyglot setup are especially cryptic.

### 8. Shared TS config extraction (only when needed)

Minor. `frontend/tsconfig.json` is fine as-is today. If a second JS package ever appears, extract a `tsconfig.base.json` at root that both packages `extends`. Not worth doing speculatively.

## What _not_ to add

- **Nx / Turbo / Bazel** — overkill for this shape.
- **Changesets / release-please** — nothing here is a published artifact.
- **Devcontainer / Nix flake** — nice, but the existing `bootstrap` script already works; diminishing returns.
- **A `packages/shared/` today** — YAGNI. Create it the first time there's genuinely shared code beyond generated OpenAPI.

## Suggested sequencing

The three most consequential and independent items are #1, #2, and #3. Any order works; they don't depend on each other. #4 naturally follows once the others land because the `make ci` target then has everything it needs to call.
