# Claims Exempt

## Context

This work is part of the family described in [ModelDrivenClaimsMetadata.md](ModelDrivenClaimsMetadata.md), and an instance of the broader pattern in [ModelDrivenMetadata.md](ModelDrivenMetadata.md): encode per-model behavior on the model itself, consume it generically from shared infrastructure.

`claims_exempt` is the per-model knob that excludes specific fields from claim control entirely. The fields named here keep whatever Django shape they have on the row but aren't discovered, materialized, or validated by the claims layer.

## The contract

`ClaimControlledModel` declares:

```python
claims_exempt: ClassVar[frozenset[str]] = frozenset()
```

Default empty — every existing model is unaffected. Location declares:

```python
claims_exempt: ClassVar[frozenset[str]] = frozenset({"location_path"})
```

`location_path` is materialized from `parent` + `slug` at create time, never edited afterward, and never carries a claim. Listing it in `claims_exempt` keeps `get_claim_fields` from treating it as a claim-controlled field.

`get_claim_fields(model_class)` in `apps/core/models.py` reads `claims_exempt` to filter the discovered claim fields. Downstream consumers (resolvers, validators, the claim executor) see only the unfiltered set; nothing else needs to know about exemption.

## Current state and hoist plan

Today `claims_exempt` is typed (`ClassVar[frozenset[str]]`, per [ModelDrivenMetadataCleanup.md](ModelDrivenMetadataCleanup.md)) but only declared on subclasses that need it. `get_claim_fields` reads it via `getattr(model_class, "claims_exempt", frozenset())` — the [field-on-model antipattern](ModelDrivenMetadata.md#antipattern-field-on-model) shape.

Hoist:

- Declare `claims_exempt: ClassVar[frozenset[str]] = frozenset()` on `ClaimControlledModel`.
- Subclass declarations remain — they become overrides of the base default rather than ad-hoc additions.
- Replace the `getattr(model_class, "claims_exempt", frozenset())` read in `get_claim_fields` with a direct attribute access (`model_class.claims_exempt`).
- No semantic change. Existing test coverage of `get_claim_fields` carries over.

## Why this lives on `ClaimControlledModel`

The set of fields exempt from claim control is meaningful only for models that participate in claim control. `ClaimControlledModel` is the smallest base that captures the audience. Hoisting puts the contract on the class the consumer already knows about, lets the type checker enforce the shape, and makes a fourth or fifth ClassVar in this family (see [ModelDrivenClaimsMetadata.md](ModelDrivenClaimsMetadata.md)) cheap to add — same shape, same home, same hoist recipe.
