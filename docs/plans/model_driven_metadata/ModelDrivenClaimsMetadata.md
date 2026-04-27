# Model-Driven Claims Metadata

A small family of `ClassVar`s on `ClaimControlledModel` that customize per-model behavior of the claims layer. Each is declared on the base with an empty default and overridden where needed by subclasses; each is consumed generically by claim infrastructure (no `isinstance` checks anywhere downstream).

This is one facet of the broader goal in [ModelDrivenMetadata.md](ModelDrivenMetadata.md): encode per-model behavior on the model itself, consumed generically by shared infrastructure. See the umbrella for the underlying pattern ([base class / mixin](ModelDrivenMetadata.md#pattern-base-class--mixin)) and the antipattern ([field-on-model](ModelDrivenMetadata.md#antipattern-field-on-model)) this family of work fixes.

## The ClassVars

Each item is its own piece of work — typing, hoist to the base, consumer cleanup, tests — and gets its own doc.

- **`immutable_after_create`** — which fields, once set, cannot change. Default `frozenset()`. See [ModelDrivenImmutableAfterCreate.md](ModelDrivenImmutableAfterCreate.md).
- **`claims_exempt`** — which fields are excluded from claim control. Default `frozenset()`. See [ModelDrivenClaimsExemptMetadata.md](ModelDrivenClaimsExemptMetadata.md).
- **`claim_fk_lookups`** — per-FK override of the lookup field used in claim writes and resolution. Default `{}`. See [ModelDrivenClaimFkLookupsMetadata.md](ModelDrivenClaimFkLookupsMetadata.md).
