# Claim FK Lookups

## Context

This work is part of the family described in [ModelDrivenClaimsMetadata.md](ModelDrivenClaimsMetadata.md), and an instance of the broader pattern in [ModelDrivenMetadata.md](ModelDrivenMetadata.md): encode per-model behavior on the model itself, consume it generically from shared infrastructure.

`claim_fk_lookups` is the per-model knob that maps FK fields to the lookup field on the related model. By default the claims layer assumes every FK claim value is the related row's `slug`. When that assumption is wrong — typically because the related model's URL identifier isn't `slug` — the writing model declares an override.

The need is exposed by [ModelDrivenLinkability.md](ModelDrivenLinkability.md): as soon as a related model's `public_id_field` isn't `slug`, the FK claim value must follow.

## The contract

`ClaimControlledModel` declares:

```python
claim_fk_lookups: ClassVar[dict[str, str]] = {}
```

Default empty — every FK claim resolves through `slug` (the historical assumption). Location declares:

```python
claim_fk_lookups: ClassVar[dict[str, str]] = {"parent": "location_path"}
```

When writing the `parent` FK claim, the resolver reads `getattr(parent, "location_path")` rather than `parent.slug`. The same map drives FK resolution at materialization time: `_resolve_fk_generic` in `apps/catalog/resolve/_helpers.py` looks up the related row by its `location_path` instead of its `slug`.

## Current state and hoist plan

Today `claim_fk_lookups` is typed (`ClassVar[dict[str, str]]`, per [ModelDrivenMetadataCleanup.md](ModelDrivenMetadataCleanup.md)) but only declared on subclasses that need it (Location is the only one). Consumers in `apps/catalog/resolve/_helpers.py` (two call sites) and `apps/catalog/management/commands/validate_catalog.py` read it via `getattr(model_class, "claim_fk_lookups", {})` — the [field-on-model antipattern](ModelDrivenMetadata.md#antipattern-field-on-model) shape, three call sites with no typed contract.

Hoist:

- Declare `claim_fk_lookups: ClassVar[dict[str, str]] = {}` on `ClaimControlledModel`.
- Subclass declarations remain — they become overrides of the base default rather than ad-hoc additions.
- Replace the three `getattr(model_class, "claim_fk_lookups", {})` reads with direct attribute access (`model_class.claim_fk_lookups`).
- The shared write factories described in [ModelDrivenLinkability.md](ModelDrivenLinkability.md) also read this map when constructing parent FK claims; that read becomes direct attribute access too.
- No semantic change. Existing test coverage of FK claim writes and FK resolution carries over.

## Why this lives on `ClaimControlledModel`

FK claim lookups are meaningful only for models that participate in claim control — claim writes resolve FKs by some lookup key, and claim materialization reverses that. `ClaimControlledModel` is the smallest base that captures the audience. Hoisting puts the contract on the class the consumer already knows about, lets the type checker enforce the shape, and lines up with the rest of the [claims metadata family](ModelDrivenClaimsMetadata.md) — same base, same hoist recipe.
