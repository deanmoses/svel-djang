# Catalog Resolve Baseline Cleanup

Step 4 of [ResolveHardening.md](ResolveHardening.md). Mypy baseline burn-down on `backend/apps/catalog/resolve/*.py`: helper function signatures and tuple-variable-reuse cleanup. Bundled with the hardening sequence because it touches the same files as Steps 2–3, not because baseline reduction is load-bearing for the hardening story.

## Context

After Step 3 ([CatalogResolveTyping.md](CatalogResolveTyping.md)) lands, the claim-value shape work is done but two other classes of mypy entries remain in `catalog/resolve/*`:

- **Untyped keystone helpers.** `validate_check_constraints`, `_coerce`, `_resolve_fk_generic`, `_sync_markdown_references`, `_resolve_aliases`, `_resolve_parents`, `resolve_entity`, `resolve_all_entities`, `_annotate_priority` — missing signatures. `_annotate_priority(qs)` is the keystone: it contributes ~9 `no-untyped-call` entries across every resolver.
- **Tuple-shape variable reuse** in `_relationships.py` and `_media.py`: loop variables get assigned from `values_list(...)` tuples of different arities (or a tuple and a model instance) in the same scope, tripping `Incompatible types in assignment` + `Need more than N values to unpack`.

## Scope — behavior-preserving

Pure typing cleanup. No resolver logic changes. Baseline only moves downward.

## Prerequisites

[CatalogResolveTyping.md](CatalogResolveTyping.md) (Step 3) lands first. Rationale: Step 3's Phase B rewrites most resolver loops to add `cast` calls; rebasing this cleanup over that diff is more friction than doing it after.

## Approach

### Phase 1 — Type keystone helpers

**Revised from initial implementation attempt (2026-04-25):** the original plan proposed `type[models.Model]` / `models.Model` as the base for helper signatures. This proved too loose — it forced `.objects` → `._default_manager` swaps throughout, broke tests that call `resolve_entity(obj).slug`, and scattered `# type: ignore[attr-defined]` across the internals. The codebase has an existing typed abstract hierarchy that fits this use case directly: [CatalogModel](../../../backend/apps/core/models.py#L423) (a `LinkableModel` + `LifecycleStatusModel` composition) already declares `name: str` and `slug: str` at the typed base level and carries `CatalogManager[Self]` — per its own docstring, "so `type[CatalogModel]` introspection code sees `.objects.active()` without per-callsite casts."

**Audit:** 19/20 callers pass `CatalogModel` subclasses. The lone exception is `Location`, which deliberately declines `CatalogModel` (non-unique `slug`, no `entity_type`). For Location's two call sites (`resolve_all_entities(Location)` and `_resolve_aliases(Location, "location_alias")`), cast at the call site with a short comment flagging a future retrofit (a shared `ClaimControlledModel` mixin between `CatalogModel` and `Location`) as out-of-scope.

Annotate in callee-before-caller order:

- [\_helpers.py](../../../backend/apps/catalog/resolve/_helpers.py): `validate_check_constraints(obj: models.Model) -> None`; `_coerce(model_class: type[models.Model], attr: str, value: object) -> object` — body needs `int(str(value))` / `Decimal(str(value))` to accept `object`; `_resolve_fk_generic(..., value: object, ...)`; **`_annotate_priority(qs: QuerySet[Claim]) -> QuerySet[Claim]`** (kills the `no-untyped-call` entries on `_annotate_priority`). Only [\_media.py:181](../../../backend/apps/catalog/resolve/_media.py#L181) reads `effective_priority`, and it already uses `cast(HasEffectivePriority, claim)` — keep it.
  - **Callers that `.order_by("-effective_priority")` must add `# type: ignore[misc]`** — django-stubs validates order_by strings against the model's declared fields and cannot see runtime `.annotate()` fields. Scattered across 12 call sites in `resolve/*.py`. Document the reason in `_annotate_priority`'s docstring; at each call site use a bare `# type: ignore[misc]` pointing back to that comment. (Category-3 Django-leak idiom applied to annotated-queryset ordering; same pattern already used for `aliases.rel` / `parents.through`.)
- [\_entities.py](../../../backend/apps/catalog/resolve/_entities.py): `_sync_markdown_references(obj: models.Model)`; `_resolve_single(obj: models.Model, ...)`; `_resolve_bulk(model_class: type[CatalogModel], ...)`; `resolve_entity(obj: T) -> T` with `T = TypeVar("T", bound=CatalogModel)` — preserves the caller's specific type so `man = resolve_entity(manufacturer); man.name` still type-checks; `resolve_all_entities(model_class: type[CatalogModel], *, object_ids: set[int] | None = None)`. Flip `extra_data: dict | None = {} if has_extra_data else None` to `JsonBody | None` — both locals mutate the dict, so the covariant `JsonData = Mapping[str, object]` is wrong; invariant `JsonBody = dict[str, object]` is correct per [core/types.py:19-20](../../../backend/apps/core/types.py#L19). `obj.extra_data` access stays behind the existing `hasattr(obj, "extra_data")` runtime guard — use `setattr`/`getattr` (or a targeted ignore) since not every `CatalogModel` has that field.
- [\_relationships.py](../../../backend/apps/catalog/resolve/_relationships.py): `_resolve_aliases(parent_model: type[CatalogModel], claim_field_name: str)`; `_resolve_parents(parent_model: type[CatalogModel], *, claim_field_prefix: str | None = None)`. Reverse-relation accessors (`parent_model.aliases.rel`, `parent_model.parents.through`) are category-#3 `Any` per the idiom — Django's descriptor API genuinely discards the info. Confine the ignores to two small helpers:
  - `_get_alias_rel_info(parent: type[Model]) -> tuple[type[Model], str]` — returns `(alias_model, fk_col)` from `parent.aliases.rel` with a single `# type: ignore[attr-defined]` + comment naming the GenericRelation reverse-accessor constraint.
  - `_get_parents_through(parent: type[Model]) -> type[Model]` — returns `parent.parents.through`, same pattern.

  Inside these helpers and the parent-hierarchy loop, the returned `through` / `alias_model` is typed as generic `type[Model]`, so `.objects` still fails on them — use `._default_manager` (idiomatic for generic Django operations) or local ignores.

  A Protocol can't express `parents.through` (or the `.rel.field.name` path), so helper-with-ignore is the minimum-touch option; scattering the ignores across `_resolve_aliases` / `_resolve_parents` loop bodies would be easier to accidentally normalize.

- [\_\_init\_\_.py](../../../backend/apps/catalog/resolve/__init__.py): the `dict | None` / `dict` generics on `sfl_map` (→ `SourceFieldLicenseMap | None` from [core/licensing.py:15](../../../backend/apps/core/licensing.py#L15)), `extra_data` (→ `JsonBody`), `_apply_resolution` signatures.

**Location call sites** — 2 total, cast at each:

- [\_\_init\_\_.py:191](../../../backend/apps/catalog/resolve/__init__.py#L191) `resolve_all_entities(Location)`
- [\_relationships.py:853](../../../backend/apps/catalog/resolve/_relationships.py#L853) `_resolve_aliases(Location, "location_alias")`

**Downstream callsite fixes (not in original plan):**

- [ingestion/apply.py:817](../../../backend/apps/catalog/ingestion/apply.py#L817) — passes `type[Model] | None` into `resolve_all_entities`. Add a `None` guard (or narrow the local) before the call.

**Done when:** every function in `resolve/` has a full signature; the `_annotate_priority` `no-untyped-call` entries are gone; test files (`test_resolve*.py`, `test_bulk_resolve*.py`) have no new baseline entries (the TypeVar on `resolve_entity` is what preserves their `.name`/`.slug`/`.description` accesses).

### Phase 2 — Clean up tuple-reuse in `_relationships.py` and `_media.py`

Two files, same pattern: a loop variable gets assigned from `values_list(...)` with one tuple arity and then reassigned in a later scope (either a different values_list, or a model instance from `in_bulk`). Mypy locks in the first-seen type and flags every divergence.

- `_relationships.py` — baseline lines 81–92 and siblings. ~6 loops across `_resolve_machine_model_m2m`, `resolve_all_gameplay_features`, `resolve_all_credits`, both abbreviation resolvers, `_resolve_aliases`, `_resolve_parents`. `resolve_all_gameplay_features` in particular has the same tuple-vs-instance collision as `_media.py`: [line 253-258](../../../backend/apps/catalog/resolve/_relationships.py#L253) uses `row` for a `values_list` tuple, then [line 294](../../../backend/apps/catalog/resolve/_relationships.py#L294) reassigns `row = rows[pk]` to a `MachineModelGameplayFeature` instance and writes `row.count = count` — this triggers three baseline entries (`[assignment]`, `[method-assign]`, second `[assignment]`) that all collapse when the inner-loop local is renamed (`mgf_row` or similar).
- `_media.py` — baseline entries at [\_media.py:244-250](../../../backend/apps/catalog/resolve/_media.py#L244) (values_list row) colliding with [\_media.py:293](../../../backend/apps/catalog/resolve/_media.py#L293) (`row = rows[update.row_pk]` — the `EntityMedia` instance). Rename the inner-loop local (`media_row` or similar).

Fix by inline-unpacking the tuple at the loop header and renaming any colliding inner-scope reuse:

```python
# before
for row in MachineModelGameplayFeature.objects.filter(...).values_list(
    "pk", "machinemodel_id", "gameplayfeature_id", "count"
):
    pk, mid, fk_id, count = row
    ...

# after
for pk, mid, fk_id, count in MachineModelGameplayFeature.objects.filter(...).values_list(
    "pk", "machinemodel_id", "gameplayfeature_id", "count"
):
    ...
```

Sequenced after Phase 1 so collateral `no-untyped-call` errors are already gone and don't clutter the diff.

**Done when:** baseline for `resolve/_relationships.py` and `resolve/_media.py` is zero.

## Ordering

1 → 2. Phase 1's helper annotations remove `no-untyped-call` noise that would otherwise clutter Phase 2's diff.

## Critical files

- `backend/apps/catalog/resolve/_helpers.py` — `_annotate_priority` annotation is the keystone.
- `backend/apps/catalog/resolve/_relationships.py` — bulk of the signatures + tuple cleanup.
- `backend/apps/catalog/resolve/_entities.py`, `_media.py`, `__init__.py` — smaller passes.

## Reuse

- `JsonBody` from [apps/core/types.py](../../../backend/apps/core/types.py) — invariant `dict[str, object]` alias for mutable JSON-shaped dicts. Use for `extra_data` locals and signatures that build up the dict. `JsonData` (covariant `Mapping[str, object]`) is for read-only params; don't use it where the code assigns into the dict.
- NamedTuple shapes in `_media.py` (`CtInfo`, `PrimaryCandidate`, `AttachmentTimestamp`, `MediaRowState`, `EntityCategoryKey`) — the template for any incidental tuple-shape cleanup that falls out of Phase 2.

## Non-goals

- No architectural refactoring of `_resolve_single` / `_resolve_bulk` / `_apply_resolution`.
- No new abstractions — signatures only.
- No subscript flip on resolver reads — that's Step 5 ([ResolverReadsTightening.md](ResolverReadsTightening.md)).

## Verification

- `./scripts/mypy` — expect baseline `new: 0` at every phase, `fixed: >0` at each.
  - After Phase 1: the ~9 `no-untyped-call` entries on `_annotate_priority` gone; `no-untyped-def` entries on `_helpers.py` / `_entities.py` gone.
  - After Phase 2: `_relationships.py` and `_media.py` baselines at zero.
- `uv run --directory backend pytest apps/catalog/tests/test_resolve*.py apps/catalog/tests/test_bulk_resolve*.py` — behavior-preserving; all resolver tests pass.
- After each phase, sync baseline with `uv run --directory backend mypy --config-file pyproject.toml . 2>&1 | uv run --directory backend mypy-baseline sync` once `./scripts/mypy` reports `new: 0`.
