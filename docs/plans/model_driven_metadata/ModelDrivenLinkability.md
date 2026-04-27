# Model-Driven Linkability

## Context

### The Ultimate Goal

This doc is one facet of the broader goal described in [ModelDrivenMetadata.md](ModelDrivenMetadata.md): make the system as model-agnostic as possible. We do that by encoding what varies between models on the models themselves and reading it generically from shared infrastructure.

### Sub-goal: Generic Linkability

For all the catalog models that are URL-addressable, we want that capability to be handled generically. Right now this is partly accomplished via `LinkableModel`: if the model has a slug that's unique within that entity type, it works. The problem is that `LinkableModel` does NOT currently work for `Location`, which is only unique within its parent Location.

This doc outlines an architecture that will support a `LinkableModel` that works for ALL URL-addressable models.

## The Contracts

- **[`LinkableModel`](#linkablemodel)**: declares URL identity.
- **[`ClaimControlledModel.immutable_after_create`](ImmutableAfterCreate.md)**: a new capability on `ClaimControlledModel` to block updates on a field. Location neeeds to block re-parenting, since re-parenting would invalidate the materialized `location_path` on the row and every descendant. This gives Location the ability to freeze its `parent` field. This is a pre-condition for this doc; the work lives in [ImmutableAfterCreate.md](ImmutableAfterCreate.md).

## LinkableModel

A linkable catalog model inherits `LinkableModel` and declares three ClassVars:

- `entity_type: ClassVar[str]` — the singular entity-type token (e.g. `"theme"`, `"location"`).
- `entity_type_plural: ClassVar[str]` — the URL-segment plural (e.g. `"themes"`, `"locations"`).
- `public_id_field: ClassVar[str] = "slug"` — the name of the field that carries URL identity. Defaults to `"slug"` so existing models declare nothing. Location overrides to `"location_path"`.

`LinkableModel` provides, for free:

- `public_id` — `@property` returning `getattr(self, self.public_id_field)`.
- `get_absolute_url()` — formats `link_url_pattern` with `{public_id}`.
- `link_url_pattern` — defaults to `/{entity_type_plural}/{public_id}`; a model may override.

This is a [base class / mixin](ModelDrivenMetadata.md#pattern-base-class--mixin) — discovery is `LinkableModel.__subclasses__()`, no hand-maintained registry of who participates.

Wikilink-picker presentation (label, sort order, autocomplete config) is a separate, opt-in capability layered on top of `LinkableModel` — see [ModelDrivenWikilinkableMetadata.md](ModelDrivenWikilinkableMetadata.md). A `LinkableModel` subclass that doesn't mix in `WikilinkableModel` simply doesn't appear in the wikilink picker.

## `public_id` is a presentation alias, not a stored column

`public_id` is **not a new field** and **not claim-controlled**. It's a computed alias over whichever field already carries URL identity for that model:

- Most models: `public_id` resolves to `self.slug`.
- Location: `public_id` resolves to `self.location_path` — already materialized on the row because Location's slug is only unique within its parent, so the path-encoded form is what's globally unique.

Consequences:

- No new migrations, no denormalization, no slug↔public_id sync logic.
- The underlying field keeps whatever claim-control status it already has. `slug` stays claim-controlled; `location_path` stays claims-exempt (it's derived from `parent` + `slug` at create time).
- A model whose URL identity is multi-segment plugs in by materializing the path into a single `unique=True` field and pointing `public_id_field` at it. The linkability layer doesn't know or care about segment count.

## URL convention

Every LinkableModel-aware route uses Django's `:path` converter and the uniform param name `public_id`:

- Page-level provenance: `/api/pages/edit-history/{entity_type}/{public_id:path}/`, `/api/pages/sources/{entity_type}/{public_id:path}/`
- Per-entity write: `PATCH /api/{plural}/{public_id:path}/claims/`, `DELETE /api/{plural}/{public_id:path}/`, `POST /api/{plural}/{public_id:path}/restore/`
- Parented create: `POST /api/{plural}/{parent_public_id:path}/children/`

The `:path` converter matches single-segment ids without ceremony, so existing single-segment entities aren't affected. It also widens to multi-segment automatically — `/api/pages/edit-history/location/usa/il/chicago/` resolves the same way `/api/pages/edit-history/theme/sci-fi/` does.

A widened route must 404 cleanly when a single-segment model is hit with extra segments (the lookup misses), not 500.

## Startup enforcement

`apps.core.checks` walks `LinkableModel.__subclasses__()` at boot and verifies that each model's `public_id_field` resolves to a real field with `unique=True`. Missing declarations, typos, or non-unique target fields fail `manage.py check` — not at first request. New linkable models inherit the check by virtue of subclassing.

This is the [base class / mixin + startup check](ModelDrivenMetadata.md#pattern-base-class--mixin) pattern: the model class itself is the contract, and the contract is enforced before any request lands.

## The generic write surface

The shared write factories — `register_entity_create`, `register_entity_restore`, `register_entity_delete_with_preview` — must be model-agnostic against the linkability contract. Concretely:

- **Lookups go through `public_id_field`**, not a hardcoded `slug` kwarg. Collision checks query `model.objects.filter(**{model.public_id_field: value})`; post-create fetches do the same.
- **FK claim values respect `claim_fk_lookups`** (a `ClaimControlledModel` ClassVar — see [`claim_fk_lookups`](#claim_fk_lookups) below). When the factory writes a parent FK claim, it reads `getattr(parent, model.claim_fk_lookups[parent_field])`, not `parent.slug`.
- **Extension hooks** let models with derived fields plug in without forking the factory:
  - `extra_claim_specs_builder(data, parent) -> list[ClaimSpec]` — additional claims (Location: `location_type`, `divisions`).
  - `extra_row_kwargs_builder(data, parent) -> dict` — non-claim row kwargs computed from input (Location: `location_path`).
  - `body_schema` — alternate Pydantic schema for endpoints that accept extra fields.

The validation criterion: a new linkable model reaches create / restore / delete-with-preview through these factories with **zero model-specific overrides**. If it can't, the factory has a gap and the factory gets fixed — not the model.

Bespoke handlers are acceptable only where semantics genuinely differ from the linkability contract. Location's delete-preview subtree walk and DELETE cascade are hierarchy semantics, not linkability gaps.

## The generic read/provenance surface

`/api/pages/edit-history/{entity_type}/{public_id:path}/` and `/api/pages/sources/{entity_type}/{public_id:path}/` resolve the entity via `get_linkable_model(entity_type)` + `get_object_or_404(model, **{model.public_id_field: public_id})`. No per-model branches, no per-model endpoint files.

The same shape applies to any future page-level endpoint that takes an entity reference: keyed on `(entity_type, public_id)`, dispatched through the registry, looked up via `public_id_field`.

## `claim_fk_lookups`

When a linkable model has an FK to another linkable model whose URL identifier isn't `slug`, the writing model declares the mapping:

```python
class Location(ClaimControlledModel, LinkableModel):
    claim_fk_lookups: ClassVar[dict[str, str]] = {"parent": "location_path"}
```

This tells the claims layer: "when writing the `parent` FK claim, the value is the related row's `location_path`, not its `slug`." The default is `{}`, meaning every FK claim value is the related row's `slug` (the historical assumption).

Strictly speaking `claim_fk_lookups` is a `ClaimControlledModel` ClassVar — it governs claim writes, not linkability. It's documented here because the linkability layer is the consumer that exposes the need: as soon as a related model's `public_id_field` isn't `slug`, the FK claim value must follow.

The shared factories and the claims executor both read this map. Hardcoding `parent.slug` anywhere in the write path is a [field-on-model antipattern](ModelDrivenMetadata.md#antipattern-field-on-model) waiting to happen.
