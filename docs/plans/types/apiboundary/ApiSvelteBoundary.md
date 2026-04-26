# API Boundary Improvements

This is a plan to improve the ergonomics of working with both the backend and frontend API surface area.

## Context

The Django Ninja schema names that flow through OpenAPI into the generated
TypeScript types are inconsistent and noisy: 117 names end in `Schema` (a
Ninja base-class artifact, not domain vocabulary), the media app uses
divergent `In`/`Out` suffixes, and a handful of bare names (`Variant`,
`Source`, `Stats`, `Recognition`, `Create`) are too generic at the OpenAPI
component level.

The OpenAPI contract is the shared vocabulary between Django, the generated
types, ~86 frontend consumers, and any AI agent reading the codebase. When
the same role (input, output, list-row, detail) takes different suffixes
depending on which app a schema lives in, every contributor has to learn the
per-app convention before they can type anything correctly. The cost
compounds: every new schema either follows the local convention
(perpetuating divergence) or invents its own, and the inconsistency blocks
lint enforcement because there's no single rule a boundary test can assert.

A second friction sits one layer down: those 86 frontend consumers reach the generated types via `components['schemas']['XSchema']` indexed access — verbose, no IDE autocomplete, OpenAPI structure leaking into every call site. We want instead to write `import type { Foo } from '$lib/api/schema'`. We didn't realize that `openapi-typescript` could emit top-level type aliases via its `--root-types` flag until recently. That flag is now turned on, but the front end has not switched to using `import` statements yet.

## Direction

1. **Rename schemas.** Rename the schemas at the source — in the backend Python classes — so the OpenAPI contract, the generated `schema.d.ts`, and the frontend imports all share one vocabulary. Change the usage by the front end consumers at the same time.
2. **Add tests.** Once the contract is consistent, pin the conventions with boundary tests.

## Tasks

### Document rationalized API names - DONE

Document the convention rules and rename tables in [ApiNamingRationalization.md](ApiNamingRationalization.md). These have been reviewed and approved.

### Rename API schemas

Two-stage migration. The TS-side import style change (indexed access → named imports) is independent of the Python renames, so it ships first as one mechanical PR. After that, per-app rename PRs only need to rename existing import specifiers, never invent new import blocks.

This split was chosen over interleaving rename + import-style per app because:

- The dedupe / import-management logic (the trickiest part of the TS transform) gets exercised once on the full corpus, not over and over with shifting scopes.
- Per-app rename PRs become much simpler — each one is "rename N classes in Python, then rewrite N specifiers in TS imports."
- PR 0 is reviewable as a single concern ("switch import style") with no semantic change.
- Reviewers and `git bisect` can isolate import-style regressions from rename regressions.

The remainder of this section assumes that split. PR 0 is described first; PR 1+ follow.

#### Op-ID stability — verified

Renaming Ninja schema classes does not shift `operationId` values. Verified empirically against the current `openapi.json`: op IDs follow the `<module>_<function_name>` pattern (e.g., `config_api_stats`), derived from the view function's qualified name, not from any schema class. No endpoint declares `operation_id=` explicitly, so this is the actual mechanism in use.

The TS transform therefore never needs to touch op IDs in client call sites. If a future Ninja upgrade changes default op-ID derivation, re-verify by diffing `openapi.json` after a one-class rename.

#### Tooling

- **Python side**: libcst — preserves comments and formatting; built for codemods. Add as a dev dependency: `cd backend && uv add --dev libcst`.
- **TS side**: ts-morph — wraps the TS compiler API; first-class import-management APIs. Add as a dev dependency: `cd frontend && pnpm add -D ts-morph tsx`. Run scripts via `pnpm tsx`.

Scripts live in the language-native trees, not at repo root, so each toolchain only knows about its own:

- `backend/scripts/codemod/rename_schemas.py` — libcst transform.
- `frontend/scripts/codemod/sweep-indexed-access.ts` — PR 0's TS transform.
- `frontend/scripts/codemod/rename-import-specifiers.ts` — PR 1+'s TS transform.
- `frontend/scripts/codemod/rename-table.json` — shared `{"OldName": "NewName"}` map. Living in `frontend/` is mildly arbitrary (the Python script reads it too), but it co-locates with the larger of the two consumers and avoids inventing a new top-level dir. Python script reads it via a relative path.

Commit scripts and the JSON map so reviewers can re-run the transform after rebasing past other work.

#### PR 0: TS-side sweep (indexed access → named imports)

**Goal**: every `components['schemas']['XSchema']` indexed-access reference in `frontend/src/**` becomes a named import + bare-name use. No Python or OpenAPI changes; `schema.d.ts` is regenerated only to confirm `--root-types` aliases exist for every schema (already on, [frontend/package.json:20](../../../../frontend/package.json#L20)).

**Script behavior** (`sweep-indexed-access.ts`):

1. Find every `components['schemas']['Name']` reference in `frontend/src/**/*.{ts,svelte}`. Skip `frontend/src/lib/api/client.ts` (the only legitimate consumer of indexed access).
2. For each unique `Name` referenced in a file, add it to a `import type { … } from '$lib/api/schema'` block — create if absent, merge into existing if present, sort specifiers, dedupe.
3. Rewrite the indexed-access reference to bare `Name`.
4. If no other code in the file references `components`, remove the now-unused `import type { components } from '$lib/api/schema'` import.

**Scope today**: ~853 indexed-access call sites across ~86 files (verified via grep). Zero files currently use named imports from `$lib/api/schema` — confirmed greenfield, no pre-existing import blocks to merge against in this PR. The merge logic still needs to exist for multi-schema-per-file consumers within PR 0 itself.

**Verification**:

- `pnpm check` passes (no type drift).
- `pnpm lint` passes.
- `pnpm test` passes.
- `grep -r "components\['schemas'\]" frontend/src --include="*.ts" --include="*.svelte" | grep -v "lib/api/client.ts"` returns zero matches.

**Why this is one PR, not split per area**: the codemod is mechanical and easier to review as a single sweep. Splitting by route/area would force humans to track which files were converted and which still use indexed access — extra cognitive load for no review benefit.

#### PR 1+: per-app schema renames

After PR 0, every consumer uses named imports. Each per-app PR follows this loop.

##### Run order

1. **Python rename** (`backend/scripts/codemod/rename_schemas.py`, scoped to one app's entries from `rename-table.json`).
2. **`make api-gen`** — regenerates `frontend/src/lib/api/schema.d.ts`.
3. **TS rename** (`frontend/scripts/codemod/rename-import-specifiers.ts`, same JSON scope) — rewrites import specifiers and any in-code references.
4. **Format**: `cd backend && uv run ruff format .` + `cd frontend && pnpm format`. libcst and ts-morph emit valid but noisy whitespace; without this the diffs are polluted and the pre-commit hook would rewrite the files anyway.
5. **Verify** (see _Iterate until tests pass_ below).
6. Only then commit.

##### Python transform scope

Find class definitions wherever they live — `apps/*/schemas.py` is canonical, but `apps/citation/api.py` has 15 inline schemas, `apps/accounts/api.py` has 4, and the boundary tests intentionally don't yet enforce the schemas-must-live-in-`schemas.py` rule. The transform walks every `class FooSchema(Schema):` declaration regardless of file. Then updates every reference across `backend/**/*.py` — other apps' imports, serializers, tests, fixtures, endpoint `response=` decorators, type annotations.

The rename table is what's per-app; the file scope isn't.

##### TS transform scope

Walks `frontend/src/**/*.{ts,svelte}` (excluding `client.ts`). For each `OldName → NewName` in the PR's scope:

1. In every file that imports `OldName` from `$lib/api/schema`, replace the specifier with `NewName` (preserving sort order in the import block).
2. Replace every in-code reference to `OldName` with `NewName`.

After PR 0, no indexed-access dedupe logic is needed — every relevant reference is already a named import. Much simpler than the original combined transform.

#### Iterate until tests pass

- `git reset --hard` between runs is free. No human-in-the-loop deciding per-batch whether things look right — just run, check, revert, fix script.
- Three-part oracle, all binary signals:
  - `make api-gen` succeeds — the OpenAPI doc is internally consistent after the Python rename.
  - `pnpm check` passes — every frontend consumer compiles against the new `schema.d.ts`.
  - `make test` passes — runtime catches anything the type checks miss (string references in fixtures, admin field configs, `extra_data` JSON, etc.).

#### Per-app rollout order

After PR 0, sequence the rename PRs smallest-first so the script grows on simple cases before encountering edge cases:

1. `config/api.py` — one schema (`StatsSchema → SiteStats`), non-`apps/` location, debugs file-discovery on a one-schema surface.
2. `accounts` — 4 schemas, all simple `…Schema → …` suffix-strips.
3. `core` — 8 schemas, mostly suffix-strips.
4. `media` — 6 schemas, introduces the `In/Out → Input`/bare pattern.
5. `citation` — 15 schemas, mix including the `RecognitionSchema → CitationRecognition` and `SourceSchema → CitationSource` bare-name renames.
6. `provenance` — 27 schemas. Wide consumer reach (`ChangeSet`, `Claim`, `CitationInstance` are heavily used), so expect a large frontend diff. Mechanical; reviewers can rerun.
7. `catalog` — 74 schemas, includes role-suffix decisions (`PersonSchema → PersonListItem` drops `Schema` AND adds a new suffix), embedded sub-shape renames (`SystemSchema → ManufacturerSystem`).

Expect the script to grow with each app, not just its input table. `config/` and `accounts` validate only trivial cases.

#### Caveats

- The codemod must cover `backend/**/*.py` (including `backend/config/api.py`,
  which holds `StatsSchema → SiteStats`), not just `apps/*/schemas.py` —
  tests and fixtures reference schema names too.
- `RelationshipSchema` in `apps/provenance/validation.py` is a `@dataclass`,
  not a Ninja schema, so it never reaches OpenAPI and the rename rules don't
  apply. Excluding it keeps a Python-level grep from producing a false hit.

#### Rollback

Per-app PRs are independently revertible. If a later PR reveals a script defect that retroactively breaks an earlier rename, revert the affected PRs in reverse order. The inverse transform is mechanical — swap keys/values in the rename table, re-run the codemod — but in practice `git revert` on the merged PR is faster.

PR 0 is also revertible — it's a pure import-style change with no semantic effect.

### Ghost-type fixes

Two component names in the OpenAPI doc don't come from explicit Ninja schemas. They need source-side fixes alongside (or before) the renames. Each is a separate small PR — neither is a Python class rename and neither fits the codemod machinery.

#### `JsonBody` — single call site

`JsonBody` only enters OpenAPI via [backend/apps/catalog/api/machine_models.py:178](../../../../backend/apps/catalog/api/machine_models.py#L178): `extra_data: JsonBody` on `MachineModelDetailSchema`. The other `JsonBody` uses (`apps/catalog/resolve/`, `apps/catalog/claims.py`) are internal Python and never reach OpenAPI.

**Fix**: change the field annotation to `dict[str, Any]` in place. Ninja will inline this as `additionalProperties: true, type: object` rather than registering a named component. The `JsonBody` type alias in `apps/core/types.py` stays — it's used elsewhere for test typing. One-line change plus regeneration.

#### `Input` — orphan from Ninja's pagination

`components.schemas.Input` exists with zero `$ref`s pointing at it (verified via jq). The source is Ninja's `PageNumberPagination.Input` inner class — Ninja registers it as a component side-effect of `@paginate(PageNumberPagination, ...)`, even though the path-level params are inlined and the component is never referenced.

**Spike result**: subclassing works. A `PageNumberPagination` subclass with an inner `PaginationParams` Schema and `Input = PaginationParams` produces a `PaginationParams` component in OpenAPI. After replacing all four `@paginate(PageNumberPagination, ...)` sites with the subclass, `Input` disappears entirely — only `PaginationParams` remains. All four endpoints share one component (no duplication).

**Fix**:

1. Add `apps/core/pagination.py` with a single `NamedPageNumberPagination` subclass:

   ```python
   class NamedPageNumberPagination(PageNumberPagination):
       class PaginationParams(Schema):
           page: int = Field(1, ge=1)
           page_size: int | None = Field(None, ge=1)

       Input = PaginationParams  # type: ignore[assignment]
   ```

2. Replace `@paginate(PageNumberPagination, ...)` with `@paginate(NamedPageNumberPagination, ...)` at all 4 call sites:
   - [backend/apps/catalog/api/machine_models.py:589](../../../../backend/apps/catalog/api/machine_models.py#L589)
   - [backend/apps/catalog/api/people.py:211](../../../../backend/apps/catalog/api/people.py#L211)
   - [backend/apps/catalog/api/titles.py:651](../../../../backend/apps/catalog/api/titles.py#L651)
   - [backend/apps/catalog/api/manufacturers.py:241](../../../../backend/apps/catalog/api/manufacturers.py#L241)
3. Run `make api-gen`; verify `Input` is gone, `PaginationParams` is present.

Single small PR. No frontend changes (nothing references the orphan today).

### Boundary tests

After all rename PRs land, the conventions worth pinning will be clearer.
Likely candidates, to be confirmed against what actually shipped:

- Schema suffix discipline: per
  [ApiNamingRationalization.md](ApiNamingRationalization.md), no schema name
  ends in `Schema`, `In`, or `Out`; outputs are bare or use a role suffix
  (`…Detail`, `…ListItem`, `…GridItem`, `…List`, `…Ref`); inputs use
  `…Input`, `…Patch`, or `…Create`. The test asserts the negative (no
  `Schema`/`In`/`Out` suffixes in `components.schemas`) plus a positive
  check that every name matches one of the allowed role patterns. Target
  `components.schemas`, not Python class names, so dataclasses like
  `RelationshipSchema` aren't false hits.
- Schemas live in `schemas.py`, not embedded in endpoint files
  (`apps/citation/api.py` has 15 inline classes; `apps/accounts/api.py` has
  4).
- Every mutating endpoint declares typed 4xx responses (already established
  by _Type error responses_).
- ESLint `no-restricted-syntax` rule banning `components['schemas']` indexed
  access outside `client.ts`. Land this immediately after PR 0 (the
  indexed-access sweep) — at that point the rule has zero violations and
  permanently locks in the import style.

Existing precedent at
[backend/apps/catalog/tests/test_api_schema_boundaries.py](../../../../backend/apps/catalog/tests/test_api_schema_boundaries.py)
is the model: assertions against the live OpenAPI doc and module locations,
not text-pattern checks.

The session for this task should treat the candidate list as input, not as a
spec — some items may turn out to be too noisy to enforce, others may have
been resolved during the rename in ways that change what the test should
assert.

## Acceptance checks

Per task: `make lint`, `make test`, `pnpm check` (svelte-check, distinct from `make lint`'s eslint/prettier/ruff), `make api-gen`, and a spot-check of the running app via `make dev` where appropriate.

PR 0 (indexed-access sweep):

- `grep -r "components\['schemas'\]" frontend/src --include="*.ts" --include="*.svelte" | grep -v "lib/api/client.ts"` returns zero matches.
- `pnpm check`, `pnpm lint`, `pnpm test` pass.
- No backend changes; `make api-gen` is a no-op.

Per per-app rename PR (partial — only the schemas in that PR's scope have been renamed):

- After `make api-gen`, the old names are gone from the OpenAPI doc:
  `jq -r '.components.schemas | keys[]' backend/openapi.json | grep -E '^(OldName1|OldName2|...)$'`
  returns nothing.
- `git diff` of `openapi.json` op IDs is empty (verified once on the first PR; spot-check thereafter).
- No `components['schemas']` indexed access reintroduced (the post-PR-0 ESLint rule enforces this automatically).

Ghost-type fix PRs:

- After the `JsonBody` PR: `jq '.components.schemas.JsonBody' backend/openapi.json` returns `null`.
- After the `Input` PR (whichever option is chosen): either `jq '.components.schemas.Input' backend/openapi.json` returns `null`, or the orphan is renamed to a non-generic name and added to the boundary-test allowlist.

After the final rename PR lands:

- `frontend/src/lib/api/schema.d.ts` contains zero `…Schema` component
  names, zero `…In` / `…Out` component names, and no generic-name components
  (`Variant`, `Source`, `Stats`, `Recognition`, `Create`, `JsonBody`, and
  `Input` modulo the spike outcome above).
- Every schema in `components.schemas` is exposed as a top-level type alias
  in `schema.d.ts` (the `--root-types` flag is on).
- No `components['schemas']` indexed access remains outside `client.ts`
  (enforced by the ESLint rule landed after PR 0).

## Follow-ups

See [ApiSvelteBoundaryFollowups.md](ApiSvelteBoundaryFollowups.md).
