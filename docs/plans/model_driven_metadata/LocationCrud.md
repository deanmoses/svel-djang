# Location CRUD

This plan implements Location create, edit, delete, restore, edit-history, sources, and frontend routes. It will be the first full multi-segment `LinkableModel` CRUD surface, and prove out the changes.

## Context

This work should land after [ModelDrivenLinkability.md](ModelDrivenLinkability.md). Linkability establishes the generic URL identity and shared CRUD-factory contracts: `public_id_field`, `public_id`, `:path` route params, page-level edit-history / sources lookup by `(entity_type, public_id)`, and factory support for non-`slug` public IDs.

Location CRUD is the proof that that work actually generalized. Location is the first model that needs a multi-segment `public_id` (`location_path`) and a non-`slug` FK claim lookup (`claim_fk_lookups = {"parent": "location_path"}`). If Location can reach create, restore, edit-history, and sources through the shared factories/endpoints without Location-specific overrides, the Linkability abstraction is doing real work.

The validation criterion:

- Location create uses `register_entity_create` for both top-level countries and child locations.
- Location restore uses `register_entity_restore`.
- Location edit-history and sources use the generic `/api/pages/edit-history/{entity_type}/{public_id:path}/` and `/api/pages/sources/{entity_type}/{public_id:path}/` endpoints.
- Bespoke Location code exists only where hierarchy semantics genuinely differ: PATCH claims, delete-preview subtree analysis, and cascade delete.

## Decisions

- Location inherits `LinkableModel` and declares `entity_type = "location"`, `entity_type_plural = "locations"`, and `public_id_field = "location_path"`.
- Location declares `immutable_after_create = frozenset({"parent"})`. Re-parenting is not supported because `location_path` encodes ancestry and changing it would require recomputing the whole subtree and every reference.
- Top-level Location create always creates a `country`.
- Child Location create derives `location_type` from the country ancestor's `divisions`, using `country.divisions[parent_depth - 1]`.
- Name and slug uniqueness are sibling-scoped for children; top-level countries collide at the root scope.
- Location delete is blocked if any row in the subtree has an active `CorporateEntityLocation`.
- Unblocked Location delete soft-deletes the root and descendants in one `ChangeSet`.

## Backend

### Prerequisite: extend `register_entity_create` with extension hooks

Today's [`register_entity_create`](../../../backend/apps/catalog/api/entity_crud.py) is slug-shaped: it calls `validate_slug_format`, `assert_slug_available`, writes `row_kwargs={"slug": slug}`, and emits a `slug` `ClaimSpec` unconditionally. That works for every shipped model because all default `public_id_field = "slug"`. Location can't plug in without three new keyword-only params on the factory:

- `extra_claim_specs_builder: Callable[[EntityCreateInputSchema, CatalogModel | None], list[ClaimSpec]] | None = None` — appended to the per-create `claim_specs` list. Location uses it to add `location_type` and (for top-level country create) `divisions`.
- `extra_row_kwargs_builder: Callable[[EntityCreateInputSchema, CatalogModel | None], dict[str, Any]] | None = None` — merged into `row_kwargs` before `create_entity_with_claims`. Location uses it to materialize `location_path` and to set `location_type`.
- `body_schema: type[Schema] | None = None` — when set, replaces `EntityCreateInputSchema` as the request body type so endpoints can accept extra fields (Location: top-level country needs `divisions`).

All three default to `None`/no-op so the existing 10+ callers stay byte-identical. Add a small unit test that asserts both builders fire with the resolved `parent` (or `None`), and that a builder returning new keys is reflected in the persisted row and claim list.

The slug-availability check (`assert_slug_available(model_cls, slug)`) also needs to become `public_id_field`-aware: when `model_cls.public_id_field != "slug"`, the freshly-built `location_path` is what must be unique, not the bare slug. Either generalize `assert_slug_available` to query on `public_id_field`, or add a parallel `assert_public_id_available` that the factory dispatches to. The latter keeps the slug-shaped helper intact for the common case.

### Path and type helpers

Add `backend/apps/catalog/services/location_paths.py`:

```python
def compute_location_path(parent: Location | None, slug: str) -> str:
    return slug if parent is None else f"{parent.location_path}/{slug}"


def derive_child_location_type(parent: Location) -> str:
    ...
```

`derive_child_location_type` walks from `parent.location_path` to the country ancestor, then indexes the country's `divisions` by parent depth. When `parent` is already the country, use `parent.divisions` directly instead of doing another DB fetch. Raise `ValidationError` with a useful message if the country has no divisions or the tree is deeper than the declared divisions.

### Write router

Add `backend/apps/catalog/api/locations_write.py` and register it under `/locations/`.

Top-level create:

- Route: `POST /api/locations/`
- Factory: `register_entity_create`
- `public_id_field="location_path"`
- `body_schema=LocationCreateSchema`
- Extra claims: `location_type="country"`, `divisions=data.divisions`
- Extra row kwargs: `location_type`, `divisions`, `location_path=compute_location_path(None, data.slug)`

Child create:

- Route: `POST /api/locations/{parent_public_id:path}/children/`
- Factory: `register_entity_create` in parented mode
- `parent_field="parent"`
- `parent_model=Location`
- `route_suffix="children"`
- `scope_filter_builder=lambda parent: Q(parent=parent)`
- Extra claims: derived `location_type`
- Extra row kwargs: derived `location_type`, `location_path=compute_location_path(parent, data.slug)`

PATCH claims:

- Route: `PATCH /api/locations/{public_id:path}/claims/`
- Bespoke for now because there is no shared PATCH-claims factory.
- Body allows scalar edits for `name`, `description`, `short_name`, `code`, plus aliases, note, and citation.
- `divisions` is editable only for top-level country rows.
- Body must not allow `parent`, `slug`, or `location_type`.
- Use the same primitives as themes: `validate_scalar_fields`, `plan_alias_claims`, and `execute_claims`.

Delete preview:

- Route: `GET /api/locations/{public_id:path}/delete-preview/`
- Walk the root plus descendants by `location_path`.
- Return descendant counts by `location_type`, total count, active `CorporateEntityLocation` blockers, and `is_blocked`.
- Only active referrers block deletion.

Delete:

- Route: `DELETE /api/locations/{public_id:path}/`
- Recompute delete-preview server-side.
- Return `409` if blocked.
- Otherwise write `status=deleted` claims for root and descendants in one transaction and one `ChangeSet` with `action=DELETE`.
- Cascading delete consumes one delete rate-limit bucket.

Restore:

- Route: `POST /api/locations/{public_id:path}/restore/`
- Factory: `register_entity_restore`
- Pass `parent_field="parent"` so restore is rejected while the parent is deleted.
- Restore affects only the requested row; descendants remain deleted unless restored separately.

### Read API

Extend `LocationDetailSchema` with:

```python
expected_child_type: str | None
```

Populate it with `derive_child_location_type(location)`, or `None` if derivation fails because divisions are missing or exhausted. This lets the frontend stop hardcoding country-specific child labels.

## Frontend

Add the missing write routes under `frontend/src/routes/locations/`.

- `/locations/new` creates a top-level country. It asks for name, slug, note, citation, and comma-separated divisions. Redirect target is `/locations/{slug}`.
- `/locations/[...path]/new` creates a child location. It uses the parent detail's `expected_child_type` for labels such as "New State" or "New Region". It sends only name, slug, note, and citation; the server derives type. If `expected_child_type` is `null`, render an explanatory state instead of a form.
- `/locations/[...path]/edit` and `/edit/[section]` reuse the shared taxonomy edit base components.
- `/locations/[...path]/edit-history` uses the generic edit-history loader with `entity_type="location"` and `public_id=path`.
- `/locations/[...path]/sources` uses the generic sources loader.
- `/locations/[...path]/delete` uses the shared delete page, adapting descendant counts and blockers into the existing UI contract.

Add Location editor wiring:

- `frontend/src/lib/components/editors/location-edit-sections.ts`
- `frontend/src/lib/components/editors/LocationEditorSwitch.svelte`
- `frontend/src/routes/locations/[...path]/save-location-claims.ts`

The edit menu should not offer parent, slug, or location-type edits.

### Child labels

Remove the frontend `EXPECTED_CHILD` fallback. `newChildLabel(profile)` should prefer:

1. The first existing child's `location_type`, when children exist.
2. `profile.expected_child_type`, when there are no children.
3. `null`, which suppresses the "+ New ..." action rather than showing a wrong label.

Once Location is fully mapped, remove `locations` from the `UNMAPPED_ROUTE_DIRS` skip list in `catalog-meta.test.ts`.

## Tests

Backend tests:

- `compute_location_path` covers top-level, child, and deeper paths.
- `derive_child_location_type` covers USA, France, missing divisions, and too-deep trees.
- Top-level create succeeds, rejects name collisions, rejects `location_path` collisions, and rejects missing divisions.
- Top-level create rejects extra fields such as a client-supplied `location_type`.
- Child create succeeds, rejects sibling name/slug collisions, allows same slug under different parents, and writes the parent FK claim using `parent.location_path`.
- Child create derives country-specific child types.
- PATCH edits name, description, and aliases.
- PATCH rejects `parent`, `slug`, and `location_type`.
- Detail includes `expected_child_type` for valid hierarchies and `null` when it cannot be derived.
- Delete-preview counts descendants and reports active `CorporateEntityLocation` blockers.
- DELETE returns `409` when blocked and cascade soft-deletes the subtree when unblocked.
- Restore reactivates only the requested row and is rejected when the parent is deleted.
- Generic edit-history and sources endpoints resolve Location by multi-segment public ID.

Frontend tests:

- Location helper tests cover existing-child label, server-supplied `expected_child_type`, and `null` suppression.
- `saveLocationClaims` sends `public_id`, not `slug`.
- Delete page renders blocked and unblocked states.
- Catalog metadata parity no longer skips `locations`.

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
- Edit name, description, and aliases.
- Visit edit-history and sources for the new child.
- Delete the child.
- Confirm deleting `/locations/usa` is blocked by active corporate-entity location referrers.
- Confirm existing single-segment entities such as themes and manufacturers still handle edit, edit-history, sources, and delete after the `slug` to `public_id` rename.

## Out of Scope

- Re-parenting Location.
- Restore UI on deleted-entity pages.
- Rich divisions editor UI.
- Undoing a specific past delete `ChangeSet`.
- Switching generic href consumers to call `entity.get_absolute_url()` directly.
