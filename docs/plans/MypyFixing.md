# Mypy Fixing

## Context

We recently introduced mypy and grandfathered in a lot of exceptions in backend/mypy-baseline.txt. This is the plan to attack them.

## Status

Steps 1–3 complete. Step 4 (tech-debt cleanup) or Step 5 (decorator relaxation) is next.

## Running mypy

- **Full check:** `./scripts/mypy` from the repo root. Wraps `uv run --directory backend mypy --config-file pyproject.toml .` piped through `mypy-baseline filter`. Exit 0 only when no _new_ (above-baseline) errors exist. Reports `fixed / new / unresolved` and a per-error-code breakdown with deltas. Do **not** run `mypy` directly — absolute paths won't match the baseline.
- **Don't pass a file path.** `./scripts/mypy src/foo.py` is ignored by the wrapper on purpose (see the comment at the top of [scripts/mypy](scripts/mypy)); partial runs generate paths that don't align with the baseline.
- **Sync baseline after clearing entries:** `uv run --directory backend mypy --config-file pyproject.toml . 2>&1 | uv run --directory backend mypy-baseline sync`. Only run this once `./scripts/mypy` shows `new: 0`.
- **Kill dmypy when the type system changes.** `scripts/mypy` uses fresh one-shot mypy, but the IDE and `scripts/dmypy` use a persistent daemon. Adding a type alias, changing an override, or renaming a module-level symbol can make dmypy's cache stale and report wrong errors. Fix: `uv run --directory backend dmypy stop` (the IDE pays cold-start cost on next check).
- **Relevant overrides to keep in mind** (from [backend/pyproject.toml](backend/pyproject.toml)):
  - `strict = true` is global. Touching imports in an otherwise-clean file can surface new errors.
  - `*.tests.*` / `conftest` relaxes `disallow_untyped_defs` + friends ([line 127](backend/pyproject.toml#L127)) — annotation-style rules only, not `arg-type` / `attr-defined` / etc.
  - `apps.*.api.*` relaxes `disallow_untyped_decorators` ([line 136](backend/pyproject.toml#L136)) for Ninja's untyped decorators.

## Guiding principles

- **Type callees before callers.** Most `no-untyped-call` errors evaporate when the function being called gets annotated. Sweeping caller signatures against `Any`-returning helpers just means revisiting them.
- **Ratchet via the baseline, not per-module strictness.** `strict = true` is already global in [backend/pyproject.toml](backend/pyproject.toml); the only per-module levers are _relaxations_, and the enforceable direction is removing them. Concretely: (a) shrink `mypy-baseline.txt` monotonically and fail CI on new entries (`mypy-baseline --fail-on-new-error` or equivalent); (b) as `apps.*.api.*` packages clean up, narrow or remove the `disallow_untyped_decorators = false` relaxation at [pyproject.toml:136](backend/pyproject.toml#L136).
- **Re-run `make api-gen` after any Ninja endpoint retyping.** Annotated return types change the generated OpenAPI schema and therefore `frontend/src/lib/api/schema.d.ts`. Run the frontend typecheck too, not just pytest.

## Idioms

### Idiom for serialization helpers: return Schema, not `dict`

In a Django + Ninja app, the Ninja `Schema` (Pydantic v2) is the canonical data shape — for request/response validation _and_ for in-process typing. Serialization helpers should **return Schema instances**, not dicts that later get re-validated against the same Schema.

- **Schema-shaped output → return the Schema instance.** Pydantic v2 construction is microseconds; the "runtime cost" concern is not real.
- **No Schema exists yet for this shape → add one.** Two duplicated shapes (a TypedDict and a Schema) is a worse outcome than one Schema used everywhere.
- **Truly free-form `JSONField` bags → `JsonData` from [apps/core/types.py](backend/apps/core/types.py).** Only `extra_data` qualifies. `JsonData = Mapping[str, object]` — `object` (not `Any`) forces `isinstance`-narrowing at use sites, which is correct for JSON. `Mapping` (covariant) is needed because dict literals with specific value types aren't subtypes of the invariant `dict[str, object]`. Use `JsonBody` (the `dict` form) only for test-client write bodies.
- **Exception: cached-bytes hot paths.** Endpoints that build the input to `set_cached_response` (e.g. `list_all_titles`, `list_all_models`) persist JSON bytes; the dict _is_ the cached form. Building Schemas only to `model_dump()` them back is the round-trip the cache exists to avoid. Keep these few helpers dict-returning, type the local as `list[dict[str, Any]]`, and leave a comment naming the cache contract. The Schema for the same shape still applies to the non-cached sibling endpoint.
  - **Cached-endpoint return type:** `get_cached_response()` returns `HttpResponse | None`, so the endpoint's return annotation must be `HttpResponse | list[dict[str, Any]]` (not just the list). Mixing `return response` (HttpResponse) and `return result` (list) in one function otherwise fails mypy.

`TypedDict` is the fallback for code that can't or won't use Pydantic. In a Ninja app, Pydantic is already present — use it.

**Flipping a serializer's return from `dict` to Schema requires updating every caller's return annotation too.** Endpoint funcs typed `-> dict[str, Any]` that `return _serialize_foo(...)` must flip to `-> FooSchema`. Mypy catches one or two; grep `_serialize_foo` across the package to find the rest in one pass.

### Idiom for `Any`: four categories, only one is valid

Writing `Any` means "don't type-check this." Default to never. When tempted, classify which of these it is:

1. **Lazy `Any`** — "I haven't bothered to write the real type." The real type exists and callers pass exactly it. **Not valid.** Write the real type.
2. **Queryset-annotated attribute** — a single `.annotate()` field (e.g. `title.model_count`) that isn't on the model. Typing the param as `Any` throws away the whole model's type info to paper over one attribute. **Not valid.** Use `getattr(obj, "annotated_field", default)` — scoped to the one field.
3. **Third-party API constraint that forces information loss** — e.g. `Prefetch[str, Any, str]` on a factory feeding `prefetch_related`, which has a single `_PrefetchedQuerySetT` TypeVar that can't unify across heterogeneous concrete args. The `Any` isn't hiding info we have; it acknowledges the 3rd-party API shape discards it. **Valid — with a comment naming the constraint.**
4. **"JSON-shaped" data** — looks like it justifies `Any` but doesn't; JSON's value type is `object` with `isinstance`-narrowing. **Not valid.** Use `JsonData` / `JsonBody`.

Rule: if you're about to write `Any` and it's not #3, find the real type.

### Idioms for introspection-heavy code

For code that operates on a generic `type[Model]` (resolvers, validators, management commands):

- **Use `_default_manager` instead of `.objects`** — typed on the base `Model` class; `.objects` is added per-subclass and invisible at `type[Model]`.
- **Narrow `type[Model] | Literal['self']`** with `assert isinstance(target_model, type) and issubclass(target_model, models.Model)`. At runtime `"self"` is already resolved by `_meta.get_field()`; the union is a django-stubs artifact.
- **Narrow `Field | ForeignObjectRel`** with `isinstance(field, models.Field)`. `ForeignObjectRel` lacks `validators`, `blank`, `to_python`, `choices`.

### Idiom for generics over heterogeneous model classes

When a helper is generic over N concrete model classes that share a Schema shape but _don't_ share a base class carrying the fields / custom manager (e.g. the 9 taxonomy models share `name` / `slug` / `display_order` / `CatalogManager` but inherit them from different mixins):

- **Constrained `TypeVar`, not bound.** A bound TypeVar (`[M: CatalogModel]`) collapses `type[M]` to the common base and loses `.objects.active()` and the per-subclass fields. Only a constraint list preserves the concrete type at each call site.
- **`typing.TypeVar` with a module-level constraint list + per-def `# noqa: UP047`.** PEP 695 inline syntax (`def foo[M: (A, B, C, …)](…)`) is ergonomic for 1–2 constraints but forces the full list to be repeated at every generic function. Module-level `TypeVar` keeps the constraints DRY; ruff's UP047 then fires per def — suppress it locally.
- **Narrow with `isinstance`, not `hasattr` + `getattr`.** When one arm of the union has a reverse relation the others don't (e.g. only `RewardType` has `aliases`), `if isinstance(obj, RewardType): obj.aliases.all()` type-checks cleanly. The `hasattr` + `getattr(obj, "attr")` spelling trips ruff's B009.
- **The speculative fix is a shared abstract base.** Introducing a `TaxonomyBase` mixin with the shared fields and manager would let a bound TypeVar work and eliminate the noqas. Not in-scope for any step of this plan — revisit only if multiple future helpers need the same shape or the entity-type registry consolidation lands.

### Idiom for Schema/dict boundaries during migration

When a helper transitions from returning `dict` to returning `Schema`, but the converse boundary still returns `dict` — either a shared callback registrar consumed by untyped callers, or a cross-step callee whose own conversion is scheduled later:

- **Wrap at the boundary, not the callee.**
  - Schema-side calling dict-side: `Schema.model_validate(callee_dict(...))` at the call site. (Step 1 titles.py used this for `MachineModelDetailSchema.model_validate(_serialize_model_detail(pm))`, pending Step 3.1's removal of the bridge.)
  - Dict-side calling Schema-side: `serialize_detail=lambda obj: _serialize_taxonomy(obj).model_dump()` confines the round-trip to the single call site.
  - Either way, tightening the shared callback type or callee return ripples into every untyped consumer, ballooning the current step's scope.
- **Flag the wrapper as tech debt.** A comment naming the later step that will remove the bridge keeps the intent visible. Don't silently leave the `.model_dump()` / `.model_validate()` hop in place once the boundary is tightened.

### Idiom for Pydantic response unions: structural discrimination is required

When typing a Ninja response slot as a union of Schemas (`response={422: SchemaA | SchemaB}`), Pydantic smart-mode union dispatch is **structural**, not intent-based. Two schemas that share a required field subset will mis-route bodies in both directions:

- A body with only the shared fields matches whichever arm covers the rest via defaults — so the "minimal" body is serialized as the "rich" schema, with the rich schema's default values leaking into the wire response.
- A body with extra fields matches whichever arm treats extras permissively (the Pydantic default) — so the "rich" body is serialized as the "minimal" schema, **silently dropping the extra fields from the wire response**.

Both failure modes pass mypy, pass OpenAPI generation, and pass tests that don't assert on the full response body. They surface as frontend classifier bugs (wrong `kind` branch) or as lost data in the 422 body.

Two tools make dispatch deterministic; apply both on every union of response schemas with shared fields:

- **Mark the distinguishing field as required (no default) on the richer schema.** A body lacking the field then fails validation against the rich arm, forcing the minimal arm.
- **Set `model_config = ConfigDict(extra="forbid")` on the minimal schema.** A body carrying extras then fails validation against the minimal arm, forcing the rich arm.

Before landing a union, verify dispatch with `TypeAdapter(A | B).validate_python(body)` for every real body shape the endpoint emits. The baseline and test suite will not catch it. `{"detail": "…"}` alone is ambiguous; fix it before shipping.

See [schemas.py:SoftDeleteBlockedSchema](backend/apps/catalog/api/schemas.py) / `AlreadyDeletedSchema` / `PersonSoftDeleteBlockedSchema` for the canonical example (Step 3.2).

### Idiom for narrowing optional FK fields

`obj.fk_id is not None` (column read, no DB hit) and `obj.fk is not None` (related-object dereference, may hit the DB) **are not equivalent**. Don't swap one for the other to satisfy mypy.

- The original guard is usually `obj.fk_id is not None` because callers don't want the related fetch.
- To narrow the related object for mypy without changing semantics, bind a local and assert: `parent = obj.fk; assert parent is not None`. The `_id` check guarantees the assert holds; the local lets mypy track the narrowing through the rest of the block.

## Step 1: keystone helpers in `catalog/api` - DONE

Type the shared helpers before their callers. Expect the `no-untyped-call` count to drop noticeably as a side effect.

- [apps/catalog/api/taxonomy.py](backend/apps/catalog/api/taxonomy.py) — **done** (58 → 2; the 2 remaining are pre-existing `Cannot infer type of lambda` on default-arg-captured lambdas in the `_register_*` wrappers).
- [apps/catalog/api/titles.py](backend/apps/catalog/api/titles.py) — **done** (51 → 0). Two `MachineModelDetailSchema.model_validate(_serialize_model_detail(...))` bridges remain; remove when Step 3.1 converts `_serialize_model_detail` to return the Schema. `_serialize_model_detail` and `_model_detail_qs` in [machine_models.py](backend/apps/catalog/api/machine_models.py) were minimally typed (return `dict[str, Any]` and `QuerySet[MachineModel]`) as cross-file callee unblocks — the full Schema conversion is Step 3.1 work.

Return Schema instances (see idiom above). Add schemas for shapes that don't have one yet.

## Step 2: `catalog/api` signatures - DONE

With taxonomy + titles done, the rest of the package falls into two groups. Order matters: shared-helper modules first (callee-before-caller), then endpoint-only files. Run `make api-gen` + frontend typecheck after each batch.

### Step 2.1: shared helper signatures - DONE

(not endpoint files; expose the keystone helpers every endpoint in the package calls — `execute_claims`, `plan_*`, `assert_*`, `serialize_blocking_referrer`, `execute_soft_delete`).

`edit_claims.py` (17 → 0) → `soft_delete.py` (17 → 0) → `entity_create.py` (11 → 0) → `entity_crud.py` (17 → 0).

Typing these first means the step 2.2 sweep collects `no-untyped-call` reductions for free.

### Step 2.2: endpoint signatures - DONE

(`request: HttpRequest`, explicit Schema return types)

`systems.py` (12 → 0) → `manufacturers.py` (11 → 0) → `series.py` (10 → 0) → `locations.py` (20 → 0) → `people.py` (20 → 0) → `machine_models.py` (34 → 0) → `page_endpoints.py` (46 → 0).

`machine_models.py` was sequenced before `page_endpoints.py` for two reasons: (a) it carries the titles.py bridges (`MachineModelDetailSchema.model_validate(_serialize_model_detail(...))`) which Step 3.1 will remove; (b) `page_endpoints.py` imports `_serialize_model_detail` / `_model_detail_qs` from it, so typing machine_models first unblocks the largest file the same way it unblocked titles.

Baseline: 710 → 377 (~47% reduction). Commit: `e7b8204f`.

## Step 3: close out `catalog/api` - DONE

Order: Schema-return conversion (3.1) before error-schema swap (3.2) because 3.1 is unblocked while 3.2 needs a design decision. Step 4 (tech-debt cleanup) is independent and can land any time. Step 5 (decorator-relaxation narrowing) is the final milestone and is gated on Step 3.

### Step 3.1: Convert `_serialize_model_detail` to return Schema - DONE

Step 1's deferred work. Two bridges in [titles.py](backend/apps/catalog/api/titles.py) still read `MachineModelDetailSchema.model_validate(_serialize_model_detail(pm))`; they must be removed, not left to rot. `_serialize_model_detail` is currently typed `-> dict[str, Any]` as a minimal-touch unblock. Flip the return to the Schema, drop the two `model_validate` wrappers in titles.py, and re-run `make api-gen` + frontend check.

**Done when:** `_serialize_model_detail` returns `MachineModelDetailSchema`, the two `model_validate` wrappers are gone from titles.py, `./scripts/mypy` stays clean, and frontend typecheck passes.

### Step 3.2: Swap `422` / `404` dict responses to shared error schemas - DONE

Delete endpoints now type 422 as a union of `SoftDeleteBlockedSchema | AlreadyDeletedSchema` (or `PersonSoftDeleteBlockedSchema | AlreadyDeletedSchema` for `delete_person`); restore endpoints use `ErrorDetailSchema` for 422 / 404.

**Design decisions resolved:**

- **Kept two blocked schemas, not one generalized field.** `SoftDeleteBlockedSchema.active_children_count` and `PersonSoftDeleteBlockedSchema.active_credit_count` measure genuinely different things (cascade-owned children vs. Credits referentially joined to active Models/Series). Collapsing to `active_referrer_count` would have unified only the wire field name — the pre-walker query logic is inherently different and not consolidatable, and the generic PROTECT-walker path is already shared via `execute_soft_delete`. A rename would also have touched `PersonDeletePreviewSchema.active_credit_count`, widening the blast radius beyond 422 bodies.
- **Introduced `AlreadyDeletedSchema` as the second union arm.** The "already soft-deleted" 422 has only `detail` (no `blocked_by`), which the frontend's [delete-flow.ts classifier](frontend/src/lib/delete-flow.ts) relies on to fall through to `form_error` instead of `blocked`. A distinct class alone is **not sufficient** — Pydantic smart-union dispatch is structural, so `{"detail": "…"}` matches whichever arm has defaults covering the missing fields, and `{"detail": "…", "blocked_by": […]}` matches whichever arm treats extras permissively. Correct dispatch required making `blocked_by` required (no default) on `SoftDeleteBlockedSchema` / `PersonSoftDeleteBlockedSchema`, **and** `model_config = ConfigDict(extra="forbid")` on `AlreadyDeletedSchema`. See the "Pydantic response unions need structural discrimination" idiom above. Named `AlreadyDeletedSchema` rather than reusing `ErrorDetailSchema` so the union is self-documenting at the call site.
- **No inheritance between error schemas.** Pydantic subclassing doesn't affect union dispatch (structural) or openapi-typescript output (duplicates fields, no TS subtyping). No backend code processes these polymorphically; no frontend code either. Inheritance would be a type-gesture only.

## Step 4: Clean up tech debt from the Step 2 signature sweep

Quality regressions introduced to clear the baseline quickly. Independent of Steps 3 / 5 — can land any time, but should not normalize.

- **`_Entity = Any` is wider than its justification.** The alias in [edit_claims.py](backend/apps/catalog/api/edit_claims.py) is used for `plan_parent_claims`, `plan_alias_claims`, `plan_gameplay_feature_claims`, `plan_credit_claims`, `plan_abbreviation_claims`. Only the first two are genuinely cross-model. The last three are effectively MachineModel-only (or MachineModel | Title for abbreviations) and should use concrete types so "wrong entity passed" is caught at the call site. The module comment claims idiom #3 justification — real for the cross-model cases, lazy-`Any` (idiom #1) for the single-model ones.
- **`cast(Any, user)` widens past what the runtime guarantees.** Two call sites in `execute_claims` / `execute_multi_entity_claims`. `_UserLike = AbstractBaseUser | AnonymousUser` matches what `request.user` returns, but `ChangeSet.user` is NOT NULL and `AnonymousUser.pk` is `None`. Every caller is behind `auth=django_auth`, so an anonymous user can't actually reach these helpers in prod — this is type-level laxity, not a latent bug. Tighten by narrowing with `assert not isinstance(user, AnonymousUser)` at entry and dropping `AnonymousUser` from `_UserLike`.
- **`cur: Any` loop-variable pattern.** Three spots — [manufacturers.py:219](backend/apps/catalog/api/manufacturers.py#L219), [machine_models.py:631](backend/apps/catalog/api/machine_models.py#L631), [locations.py:122](backend/apps/catalog/api/locations.py#L122) — use `cur: Any = cel.location` to sidestep the reassignment to `.parent` (`Location | None`). Correct fix is `cur: Location | None = cel.location`, which preserves `.location_path` / `.name` / `.parent` typing inside the loop.
- **`list[Any]` return on `list_manufacturers` / `list_people`.** Regression from `list[dict[str, Any]]` caused by `.values(...)` returning a mypy TypedDict that doesn't structurally match. Restore the dict annotation and cast the return if needed.
- **`entity_crud.py` casts `model_cls` to `Any` four times** for `.entity_type` / `.active()`. Tightening the registrar params from `type[Model]` to `type[CatalogModel]` eliminates all four casts and restores type info on the manager.
- **`create_view: Callable[..., Any]`** in `register_entity_create` was the minimal assignment-incompatibility fix but discards signature info on the eventual `router.post(...)(create_view)` call.

**Done when:** every bullet above is resolved or explicitly closed with a "won't fix, because..." note in this doc. No baseline-count criterion — these items don't all surface as baseline entries.

## Step 5: narrow `apps.*.api.*` decorator relaxation

Gated on Step 3. With `catalog/api` signatures typed and error schemas swapped, `disallow_untyped_decorators = false` at [pyproject.toml:136](backend/pyproject.toml#L136) can likely be scoped to just the files that still pay the cost, or removed for `catalog/api` entirely. Measure the fallout before flipping.

**Done when:** the `apps.*.api.*` override at [pyproject.toml:136](backend/pyproject.toml#L136) is either removed, scoped to a narrower path, or kept with an inline comment naming the specific files that still need it and why.

## Step 6: `citation/api` and `provenance/api`

Same pattern as Step 2 — helpers first, endpoints after, `make api-gen` between batches. Smaller scopes (38 + 15 entries); should go quickly after Step 2's muscle memory.

## Step 7: `catalog/resolve/*`

Refactor tuple-heavy resolver code into `dataclass` / `TypedDict` where state is being unpacked inconsistently. Apply the idioms above for remaining `attr-defined` / `union-attr` noise.

## Step 8: Ingestion and management commands

Grouped because they share patterns (external I/O, command runners, bare dicts from JSON parsing):

- [catalog/management/commands/ingest_pinbase.py](backend/apps/catalog/management/commands/ingest_pinbase.py) (47 — #2 hotspot)
- [catalog/ingestion/opdb/adapter.py](backend/apps/catalog/ingestion/opdb/adapter.py) (30)
- [catalog/ingestion/ipdb/adapter.py](backend/apps/catalog/ingestion/ipdb/adapter.py) (20)
- [catalog/management/commands/validate_catalog.py](backend/apps/catalog/management/commands/validate_catalog.py) (17)
- remaining ingestion + media tail

Ordering of Steps 6 / 7 / 8 is not fixed; re-plan when Steps 3–5 are complete.

## Process

- `strict = true` is already global, so the enforcement surface is the baseline itself plus removing relaxations.
- Fail CI on new baseline entries and shrink the file monotonically as each step lands.
