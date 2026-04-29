# Location CRUD

This plan implements Location create, edit, delete, restore, edit-history, sources, and frontend routes. It will be the first full multi-segment `LinkableModel` CRUD surface, and prove out the changes.

## Context

This is the second of three sequential plans in the Location-promotion chain:

1. The Location → `CatalogModel` promotion + walk collapse (the small structural prep). - DONE
2. **This plan** — the full Location CRUD surface (write router, frontend, tests).
3. [ModelDrivenWikilinkableMetadata.md](ModelDrivenWikilinkableMetadata.md) — the wikilink picker mixin (Location stays out by absent inheritance).

All cross-cutting prerequisites have landed; this plan now covers only the Location CRUD surface itself. For reference, the prework was:

1. Backend: extension hooks on `register_entity_create` — see §"Create-factory hooks" below for the API Location uses.
2. Frontend: `client.ts` preserves slashes in `public_id` path params (decodes `%2F` → `/` in `URL.pathname` via the existing `onRequest` middleware). Invisible to callers; Location's multi-segment `public_id` reaches the server as `/api/locations/usa/il/chicago/…` automatically.
3. Frontend: `catalog-meta.test.ts` is segment-aware (`ROUTE_DIR_TO_KEY` carries `{ key, segment }`; both `[slug]` and `[...path]` are discovered). `'location'` remains in `DEFERRED_KEYS` and the Location PR drops it.
4. Shared delete / provenance / DeletePage layer was renamed `slug` → `public_id`. Location's wrappers pass `public_id={path}`.

Foundational work landed earlier in [ModelDrivenLinkability.md](ModelDrivenLinkability.md): generic URL identity and shared CRUD-factory contracts (`public_id_field`, `public_id`, `:path` route params, page-level edit-history / sources lookup by `(entity_type, public_id)`, and factory support for non-`slug` public IDs).

Location CRUD needs to be the proof that that work actually generalized. Location is the first model that needs a multi-segment `public_id` (`location_path`) and a non-`slug` FK claim lookup (`claim_fk_lookups = {"parent": "location_path"}`). If Location can reach create, restore, edit-history, and sources through the shared factories/endpoints without Location-specific overrides, the Linkability abstraction is doing real work.

The validation criterion:

- Location create uses `register_entity_create` for both top-level countries and child locations.
- Location delete, delete-preview, and restore use `register_entity_delete_restore`. Subtree cascade and active-CorporateEntityLocation blocking are driven by `soft_delete_cascade_relations` / `soft_delete_usage_blockers` class attributes — no bespoke delete handler.
- Location edit-history and sources use the generic `/api/pages/edit-history/{entity_type}/{public_id:path}/` and `/api/pages/sources/{entity_type}/{public_id:path}/` endpoints.
- The only Location-specific write code is the PATCH-claims route (no shared PATCH-claims factory yet).

## Decisions

- Location is a `CatalogModel` (post chain step 1) and declares `entity_type = "location"`, `entity_type_plural = "locations"`, `public_id_field = "location_path"`, `claim_fk_lookups = {"parent": "location_path"}`, and `claims_exempt = frozenset({"location_path"})` — `location_path` is a derived field written into `row_kwargs` at create time, not through a claim.
- **Re-parenting and slug-renaming are not supported.** `location_path` is computed from `parent.location_path + slug` and materialized on the row, so changing `parent` _or_ `slug` would invalidate the path on every descendant and every reference. The model-level enforcement (`immutable_after_create = frozenset({"parent", "slug"})`) is deferred per [ModelDrivenLinkability.md](ModelDrivenLinkability.md)'s "Deferred: re-parenting protection" section. **For this PR, the protection is UI- and route-level**:
  - The Location editor does **not** register `NameEditor` (which edits `name` + `slug` together) and provides no replacement: name editing is omitted from this PR. It returns once `NameEditor` learns to render name-only when slug is frozen (driven by `immutable_after_create` or an equivalent profile bit), at which point Location registers the same shared editor as every other entity.
  - The PATCH-claims route below explicitly rejects `parent`, `slug`, and `location_type` in the body.
  - When `immutable_after_create` lands later, drop both workarounds and let the model enforce.
- Top-level Location create always creates a `country`.
- Child Location create derives `location_type` from the country ancestor's `divisions`, using `country.divisions[parent_depth - 1]`.
- Name and slug are sibling-scoped at every tier, enforced at the DB by four partial `UniqueConstraint`s on `Location`: `catalog_location_unique_slug_per_parent` and `catalog_location_unique_name_per_parent` (for `parent IS NOT NULL`), and `catalog_location_unique_slug_at_root` and `catalog_location_unique_name_at_root` (for `parent IS NULL`). Name constraints use `Lower("name")`, so name uniqueness is case-insensitive. The sibling set is rows sharing the same `parent`, including the root tier where the siblings are all countries. The route does not need `scope_filter_builder` for either field — the DB is the source of truth; the route layer just surfaces violations as 422s instead of `IntegrityError`s.
- Location delete is blocked if any row in the subtree has an active `CorporateEntityLocation`. Enforced by listing `corporate_entities` (a new M2M through `CorporateEntityLocation`) in `Location.soft_delete_usage_blockers`; `manager.active()` filters by the CorporateEntity's status, matching Theme's existing pattern.
- Unblocked Location delete soft-deletes the root and descendants in one `ChangeSet`. Enforced by `Location.soft_delete_cascade_relations = frozenset({"children"})`; the soft-delete walker recurses to arbitrary depth.

## Backend

### Model setup

Add to `Location`:

```python
class Location(CatalogModel, TimeStampedModel):
    soft_delete_cascade_relations: ClassVar[frozenset[str]] = frozenset({"children"})
    soft_delete_usage_blockers: ClassVar[frozenset[str]] = frozenset({"corporate_entities"})

    # Reverse accessor intentionally suppressed (`related_name="+"`); CorporateEntity
    # already reaches Location through `CorporateEntityLocation` directly.
    corporate_entities = models.ManyToManyField(
        "catalog.CorporateEntity",
        through="CorporateEntityLocation",
        related_name="+",
    )
```

The M2M is the join-table reverse manager Theme uses for `machine_models` — `location.corporate_entities.active()` resolves through `CorporateEntityLocation` and filters by the CE's status, which is exactly the "block if any row in the subtree has an active `CorporateEntityLocation`" semantic. No data migration is required (the through table already exists); only the Django-side relationship descriptor is added.

### Create-factory hooks

API available to Location's create routes on the shared factory at [`entity_crud.py`](../../../backend/apps/catalog/api/entity_crud.py):

- `body_schema: type[EntityCreateInputSchema] | None` — replaces the request body type. Subclass-checked at registration. Used by Location top-level (carries `divisions`) and child create.
- `extra_create_fields_builder: (data, parent) -> (row_kwargs, claim_specs)` — derived columns + matching claims, merged into the standard row/claim trio. One builder, not two, so callers derive shared values (e.g. `location_type`) once.
- `scope_filter_builder(data, parent) -> Q` — narrows the name-uniqueness scan. Now signature `(data, parent)` (was `(parent,)`); works in both parented and unparented modes (the parented-only gate was dropped). Used by Location for sibling/root scoping.
- `assert_public_id_available(model_cls, value)` (renamed from `assert_slug_available`) in [`entity_create.py`](../../../backend/apps/catalog/api/entity_create.py) — checks uniqueness on `model_cls.public_id_field`. Location's factory call passes the freshly-built `location_path`.
- `validate_create_input(data, model_cls, *, scope_filter, include_deleted_name_check)` — composite primitive (name + slug validation + name uniqueness check) extracted from the factory. Available to any future outlier that needs a custom create handler instead of the factory.

The factory's docstring documents the **hooks discipline**: convergence-enforcement is the factory's value (every catalog create routes through one pipeline, so callers can't drift), so a single-caller hook is justified when the alternative is a parallel handler that copies 80%+ of the factory's pipeline. Hooks are NOT justified for hypothetical future callers. Structurally-different entities (different transactional shape, different side effects) should write a custom handler over the primitives instead of extending the factory. Each existing hook carries a "Callers: …" comment with a re-evaluation trigger when a second caller appears with a different extension pattern.

The factory's `scope_filter_builder` lambdas Location passes are temporary — see §"Follow-ups: Derive uniqueness scope from `model._meta.constraints`" for the model-driven replacement.

### Path and type helpers

Add `backend/apps/catalog/services/location_paths.py`:

```python
def compute_location_path(parent: Location | None, slug: str) -> str:
    return slug if parent is None else f"{parent.location_path}/{slug}"


def derive_child_location_type(parent: Location) -> str:
    """Raises ValidationError if divisions are missing or the tree is too deep."""
    ...


def try_derive_child_location_type(parent: Location) -> str | None:
    try:
        return derive_child_location_type(parent)
    except ValidationError:
        return None
```

`derive_child_location_type` walks from `parent.location_path` to the country ancestor, then indexes the country's `divisions` by parent depth. When `parent` is already the country, use `parent.divisions` directly instead of doing another DB fetch. Raise `ValidationError` with a useful message if the country has no divisions or the tree is deeper than the declared divisions.

The two callsites want opposite things on failure, so we expose two helpers rather than one `str | None`:

- Child create calls `derive_child_location_type` and lets the `ValidationError` bubble up to a 422 with the original "no divisions" / "tree too deep" message intact.
- The detail serializer calls `try_derive_child_location_type` so `expected_child_type` can be `None` when derivation fails, letting the frontend suppress the "+ New …" action.

### Write router

Add `backend/apps/catalog/api/locations_write.py` and register it under `/locations/`.

Two sibling body schemas, both `extra=forbid`, so "client-supplied `location_type`" and "client-supplied `divisions` on child create" are rejected by schema validation before any handler code runs:

```python
class LocationTopLevelCreateSchema(EntityCreateInputSchema):
    divisions: list[str]  # required, non-empty, validated

class LocationChildCreateSchema(EntityCreateInputSchema):
    pass  # name, slug, note, citation only — server derives location_type
```

The OpenAPI split also gives the generated TS client a typed `divisions` field on `/locations/new` and not on `/locations/[...path]/new`, instead of one optional field on both forms.

Top-level create:

- Route: `POST /api/locations/`
- Factory: `register_entity_create`
- `public_id_field="location_path"`
- `body_schema=LocationTopLevelCreateSchema`
- `scope_filter_builder=lambda data, parent: Q(parent__isnull=True)` — pre-check is scoped to the country tier, matching the `parent IS NULL` partial UNIQUE constraints on `Location`. `parent` is `None` here.
- `extra_create_fields_builder` returns:
  - row kwargs: `location_type="country"`, `divisions=data.divisions`, `location_path=compute_location_path(None, data.slug)`
  - claims: `location_type="country"`, `divisions=data.divisions`

Child create:

- Route: `POST /api/locations/{parent_public_id:path}/children/`
- Factory: `register_entity_create` in parented mode
- `parent_field="parent"`
- `parent_model=Location`
- `route_suffix="children"`
- `body_schema=LocationChildCreateSchema` (may be omitted if identical to the factory default)
- `scope_filter_builder=lambda data, parent: Q(parent=parent)` — pre-check is scoped to siblings of the resolved `parent`, matching the `parent IS NOT NULL` partial UNIQUE constraints on `Location`. Both lambdas are temporary; see §"Follow-ups: Derive uniqueness scope from `model._meta.constraints`".
- `extra_create_fields_builder` returns (with `location_type = derive_child_location_type(parent)` computed once):
  - row kwargs: `location_type`, `location_path=compute_location_path(parent, data.slug)`
  - claims: `location_type`

PATCH claims:

- Route: `PATCH /api/locations/{public_id:path}/claims/`
- Bespoke for now because there is no shared PATCH-claims factory.
- Body allows scalar edits for `name`, `description`, `short_name`, `code`, plus aliases, note, and citation.
- Body must not allow `parent`, `slug`, or `location_type` — schema-rejected (`extra=forbid`), mirroring the create split.
- Two sibling body schemas, dispatched by the resolved row's `location_type`, so `divisions` is schema-rejected on non-country rows rather than handled as a 422 in the handler:
  - `LocationCountryPatchSchema` — adds `divisions: list[str] | None`.
  - `LocationChildPatchSchema` — no `divisions` field; `extra=forbid` rejects it.
- Use the same primitives as themes: `validate_scalar_fields`, `plan_alias_claims`, and `execute_claims`.

Delete, delete-preview, and restore:

- Single call to `register_entity_delete_restore(router, Location, ..., parent_field="parent")`.
- Do **not** pass `child_related_name` — that adds a "block on active children" check, which is the opposite of what we want. Active children cascade-delete via `soft_delete_cascade_relations`.
- Mounts the standard wire shape used by every other entity:
  - `GET /api/locations/{public_id:path}/delete-preview/` returning `TaxonomyDeletePreviewSchema`.
  - `POST /api/locations/{public_id:path}/delete/` returning 200 on success or 422 with `blocked_by` populated from active `CorporateEntityLocation`-reachable CEs across the subtree.
  - `POST /api/locations/{public_id:path}/restore/` rejecting restore while the parent is deleted (via `parent_field="parent"`).
- Cascade and blocker semantics ride on the model-level class attributes (see §"Model setup").
- Restore affects only the requested row; descendants remain deleted unless restored separately. This is standard factory behavior — `execute_claims` writes a single-entity status claim — but creates a deliberate asymmetry with delete (delete cascades, restore does not). A user who deletes `usa` and then restores it will find every state and city still soft-deleted with no bulk recovery path; each descendant has to be restored individually. Subtree restore is out of scope for this PR (see §"Out of Scope") and is the cleanest follow-up if the asymmetry proves painful in practice.
- The frontend gets `createDeleteSubmitter('locations')` and the shared `DeletePage.svelte` for free once `make api-gen` regenerates `schema.d.ts`.

The plan previously specified a bespoke `DELETE` verb with 409 status and a per-`location_type` descendant breakdown in the preview. We dropped both: the wire shape now matches every other delete, and the standard preview (`active_children_count` for direct children + `blocked_by` for blockers) is enough. If we later want a full subtree count in the preview, generalize the factory to report `len(plan.entities_to_delete) - 1` — that's a one-line change benefiting Title delete too, and lives in `register_entity_delete_restore`, not in Location code.

### Read API

Extend `LocationDetailSchema` with:

```python
expected_child_type: str | None
```

Populate it with `try_derive_child_location_type(location)` — `None` when divisions are missing or exhausted. This lets the frontend stop hardcoding country-specific child labels.

## Frontend

### Routes and components

Add the missing write routes under `frontend/src/routes/locations/`.

- `/locations/new` creates a top-level country. It asks for name, slug, note, citation, and comma-separated divisions. Redirect target is `/locations/{slug}`.
- `/locations/[...path]/new` creates a child location. It uses the parent detail's `expected_child_type` for labels such as "New State" or "New Region". It sends only name, slug, note, and citation; the server derives type. If `expected_child_type` is `null`, render an explanatory state instead of a form.
- `/locations/[...path]/edit` and `/edit/[section]` reuse the shared taxonomy edit base components.
- `/locations/[...path]/edit-history` uses the generic edit-history loader with `entity_type="location"` and `public_id=path`.
- `/locations/[...path]/sources` uses the generic sources loader.
- `/locations/[...path]/delete` reuses the shared `DeletePage.svelte` component and `createDeleteSubmitter('locations')` (the wire shape matches every other entity once `make api-gen` regenerates `schema.d.ts`), but still needs the standard per-entity wrapper that every existing delete route has — see [`series-delete.ts`](../../../frontend/src/routes/series/[slug]/delete/series-delete.ts) and [`+page@.svelte`](../../../frontend/src/routes/series/[slug]/delete/+page@.svelte) for the canonical shape. Concretely:
  - `frontend/src/routes/locations/[...path]/delete/location-delete.ts` exporting `submitDelete = createDeleteSubmitter('locations')`.
  - `frontend/src/routes/locations/[...path]/delete/+page.ts` (or `+page.server.ts`) — load `params.path` (a string for `[...path]`), fetch the delete-preview, and pass `{ preview, path }` to the page.
  - `frontend/src/routes/locations/[...path]/delete/+page@.svelte` — builds `BlockedState` from `preview.blocked_by` with a Location-specific lead ("This location can't be deleted because active corporate-entity locations across this subtree still point at it"), `renderReferrerHref: (r) => r.slug ? '/corporate-entities/' + r.slug : null`, and a hint that mentions the subtree relationship; builds `impact` describing the subtree cascade ("this location and all descendants", `pluralize(preview.changeset_count, 'change set')`); wires `cancelHref` and `editHistoryHref` from `path` (not `slug`); and chooses `redirectAfterDelete` per tier — for a country, redirect to `/locations`; for a child, redirect to the parent's detail page (`/locations/{parent_path}`, computed by stripping the last segment of `path`).
  - The wrapper is ~40 lines and structurally a copy of the Series version; the Location-specific decisions above are the only meaningful work.

Add Location editor wiring:

- `frontend/src/lib/components/editors/location-edit-sections.ts` — registers the Location-editable sections. **Do not register `NameEditor`** here; `NameEditor` edits `name` and `slug` together, and `slug` is frozen for Location (see Decisions §"Re-parenting and slug-renaming are not supported"). No replacement is provided in this PR — name editing is unavailable until `NameEditor` is taught to render name-only when slug is frozen.
- `frontend/src/lib/components/editors/LocationEditorSwitch.svelte`
- `frontend/src/routes/locations/[...path]/save-location-claims.ts`

The edit menu does **not** offer `name`, `parent`, `slug`, or `location_type` edits. `name` is omitted in this PR (see above); the others are frozen by design. `divisions` is editable only on top-level country rows. Other scalars (`description`, `short_name`, `code`) and aliases edit normally.

### Child labels

Remove the frontend `EXPECTED_CHILD` fallback. `newChildLabel(profile)` should prefer:

1. The first existing child's `location_type`, when children exist.
2. `profile.expected_child_type`, when there are no children.
3. `null`, which suppresses the "+ New ..." action rather than showing a wrong label.

### Un-defer Location in `catalog-meta.test.ts`

The test is already segment-aware and `locations: { key: 'location', segment: '[...path]' }` is registered in `ROUTE_DIR_TO_KEY`. Drop `'location'` from `DEFERRED_KEYS` once Location's edit-history and sources subroutes exist so parity is enforced like every other entity.

## Tests

Backend tests:

- `compute_location_path` covers top-level, child, and deeper paths.
- `derive_child_location_type` covers USA, France, missing divisions, and too-deep trees.
- Top-level create succeeds, rejects another country with the same slug (DB `catalog_location_unique_slug_at_root`), rejects another country with the same name case-insensitively — e.g. `Georgia` vs `georgia` — (DB `catalog_location_unique_name_at_root` over `Lower("name")`), and rejects missing divisions.
- Top-level create _allows_ a country whose name or slug matches a non-sibling descendant — e.g. creating country `Georgia` succeeds when a state `Georgia` already exists under USA. Verifies the root-tier `scope_filter_builder` lambda is wired (without it, the pre-check would do an unscoped global scan and falsely reject).
- Top-level create rejects extra fields such as a client-supplied `location_type` (schema-level, via `extra=forbid` on `LocationTopLevelCreateSchema`).
- Child create rejects a client-supplied `divisions` (schema-level, via `extra=forbid` on `LocationChildCreateSchema`).
- Child create succeeds, rejects sibling slug collisions (DB `catalog_location_unique_slug_per_parent`), rejects sibling name collisions case-insensitively (DB `catalog_location_unique_name_per_parent` over `Lower("name")`), allows same slug and same name under different parents, and writes the parent FK claim using `parent.location_path`.
- Child create derives country-specific child types.
- PATCH edits name, description, and aliases.
- PATCH rejects `parent`, `slug`, and `location_type`.
- Detail includes `expected_child_type` for valid hierarchies and `null` when it cannot be derived.
- Delete-preview reports active `CorporateEntityLocation`-reachable CEs across the subtree as `blocked_by`. Location is the first `soft_delete_usage_blockers` entry that resolves through an M2M-through table (every existing blocker is a reverse FK), so include a fixture where the same CE is linked to the same Location via two different `CorporateEntityLocation` rows: `blocked_by` must list that CE once, not twice. If the walker double-counts, add `.distinct()` at the iteration site rather than working around it in Location code.
- `POST /delete/` returns 422 with `blocked_by` populated when blocked, and on the unblocked path cascade soft-deletes the subtree in one `ChangeSet`. Verified by asserting `soft_delete_cascade_relations` and `soft_delete_usage_blockers` on `Location` and exercising `plan_soft_delete` against a multi-level fixture; no Location-specific delete handler exists to test.
- Restore reactivates only the requested row and is rejected when the parent is deleted.
- Generic edit-history and sources endpoints resolve Location by multi-segment public ID.

Frontend tests:

- Location helper tests cover existing-child label, server-supplied `expected_child_type`, and `null` suppression.
- `saveLocationClaims` sends `public_id`, not `slug`.
- Delete page renders blocked and unblocked states.
- `catalog-meta.test.ts` passes Location parity: `'location'` is dropped from `DEFERRED_KEYS` and Location's edit-history/sources subroutes are discovered under `[...path]`.

## Verification

Run the smallest useful set while implementing, then finish with:

```bash
make api-gen
make lint
make test
```

Manual smoke test against `make dev` with a logged-in superuser:

- `/locations`, `/locations/usa`, and `/locations/usa/il/chicago` still render.
- Create a new country at `/locations/new`.
- Create a child from the new country's action menu.
- Edit description and aliases (name editing is intentionally absent in this PR).
- Visit edit-history and sources for the new child.
- Delete the child.
- Confirm deleting `/locations/usa` is blocked by active corporate-entity location referrers (the standard shared delete page surfaces them via `blocked_by`).
- Confirm existing single-segment entities such as themes and manufacturers still handle edit, edit-history, sources, and delete (regression check that Location's factory hooks haven't disturbed shipped callers).
- Confirm `catalog-meta.test.ts` discovers Location via the new `[...path]` segment and asserts the same edit-history/sources parity as every other entity (`'location'` absent from `DEFERRED_KEYS`).

## Follow-ups

### Derive uniqueness scope from `model._meta.constraints`

Location's create routes pass explicit `scope_filter_builder` lambdas (`Q(parent__isnull=True)` for top-level, `Q(parent=data.parent)` for child). Those lambdas restate information already declared on the model — the partial `UniqueConstraint`s `catalog_location_unique_slug_per_parent`, `catalog_location_unique_slug_at_root`, etc. encode exactly the same scoping. Per [ModelDrivenMetadata.md](ModelDrivenMetadata.md), the model is the source of truth; the route layer should read the constraint declaration rather than duplicate it.

The shape of the follow-up:

1. In `assert_name_available` and the public-id-aware availability check, walk `model_cls._meta.constraints` for `UniqueConstraint`s whose `fields` include the field being checked.
2. For each matching constraint, derive a scope `Q` from `(fields ∪ condition)` and the new row's values: a constraint `fields=["parent", "slug"], condition=Q(parent__isnull=False)` against a row with `parent=X` yields `Q(parent=X)`; `fields=["slug"], condition=Q(parent__isnull=True)` yields `Q(parent__isnull=True)`.
3. Apply the union of derived scopes to the availability query. If no partial constraint matches, fall back to the existing global check — Manufacturer / Theme / etc. stay byte-identical, since none of them have partial UNIQUE constraints today.
4. Add a startup system check (per [ModelDrivenMetadata.md](ModelDrivenMetadata.md)'s "Enforce at startup, not at first request" rule) that verifies every model whose create route runs `assert_*_available` has a coherent constraint set on the checked fields — either fully global (no partial constraints) or a complete partition (every row covered by some partial UNIQUE). Catches gaps at boot rather than at first 422.
5. Delete Location's two `scope_filter_builder` lambdas and confirm Location's existing tests still pass — that's the proof the constraint-derived path is wired correctly. Keep `scope_filter_builder` as the documented escape hatch for cases that don't fit constraint derivation (none in the catalog today).

Tests for the follow-up:

- A model with a partial `UniqueConstraint` on `parent IS NULL` produces the right root-scoped pre-check.
- A model with `(parent, slug)` UNIQUE on `parent IS NOT NULL` produces the right sibling-scoped pre-check.
- A model with no partial constraints (e.g. Theme) produces the existing global check unchanged — regression check that the 10+ shipped callers stay byte-identical.
- The startup system check fails fast on a deliberately-broken model with a partial constraint that doesn't cover every row.
- Location's existing sibling-collision and root-collision tests pass after removing the lambdas.

Splitting this out lets Location land with contained, reviewable scoping (two five-line lambdas), and gives constraint derivation its own focused PR where the "complete partition" verification logic and the system check can be reviewed against more than one concrete caller.

### Consolidate PATCH-claims handlers into a shared factory

Each catalog model with editable claims today has its own hand-rolled PATCH-claims route — themes, manufacturers, franchises, corporate-entities, gameplay-features, series, taxonomy, and (after this PR) locations. They all do roughly the same work: parse the body, validate scalar fields, plan alias claims, and call `execute_claims`. The duplication is real but not yet uniform enough to factor cleanly — name/slug rules, alias shapes, and which scalars are editable vary per model.

Location's PATCH route adds one more instance to the pile. Once it lands, the next consolidation target is a `register_entity_patch_claims` factory in `entity_crud.py` that mirrors the create / delete-restore factories. Likely shape:

- Generic body-parsing for `name`, scalar fields, aliases, note, citation.
- `editable_scalar_fields: frozenset[str]` per model (drives both schema validation and the claim list).
- `immutable_after_create: frozenset[str]` per model (rejected from the body — folds in the Location-specific rejection of `parent`, `slug`, `location_type`).
- Hooks for model-specific extras (Location: `divisions` editable only on top-level rows).

Doing it now would be scope creep — the factory's right shape will be clearer with N+1 concrete callers than with N. Doing it never means accepting hand-rolled PATCH handlers as the steady state.

## Out of Scope

- **Model-level `immutable_after_create` enforcement.** Re-parenting and slug-renaming are blocked at the UI / route level in this PR (see Decisions). The model-level frozen-fields enforcement is its own follow-up; once it lands, drop the UI/route workarounds.
- Re-parenting Location.
- Subtree restore. Restore is row-only in this PR (see Decisions §"Delete, delete-preview, and restore"); cascading restore is a follow-up if the row-only behavior proves painful.
- Restore UI on deleted-entity pages.
- Rich divisions editor UI.
- Undoing a specific past delete `ChangeSet`.
- Switching generic href consumers to call `entity.get_absolute_url()` directly.
- Adding Location to the wikilink picker. Location is a `CatalogModel` but explicitly suppressed from the picker (today via the `link_autocomplete_serialize = None` sentinel; replaced in [ModelDrivenWikilinkableMetadata.md](ModelDrivenWikilinkableMetadata.md) by absent `WikilinkableModel` inheritance). Location refs in markdown still render and validate — only the authoring picker excludes them.
