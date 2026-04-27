# Immutable After Create

## Context

This work is a pre-condition for [ModelDrivenLinkability.md](ModelDrivenLinkability.md), and an instance of the broader pattern described in [ModelDrivenMetadata.md](ModelDrivenMetadata.md): encode per-model behavior on the model itself and consume it generically from shared infrastructure.

`ModelDrivenLinkability.md` proposes a `LinkableModel` that supports models with multi-segment URL identity — specifically Location, whose `public_id` is the materialized `location_path` (encoding ancestry). Once a row's URL is materialized from `parent` + `slug`, re-parenting becomes prohibitively expensive: it would invalidate the entity's URL and every descendant's URL, and force every reference to chase the change. We opt out of re-parenting Location entirely.

This doc specifies the generic mechanism that lets Location declare that opt-out without leaking `isinstance(model, Location)` into the claims executor. It's a [base class / mixin](ModelDrivenMetadata.md#pattern-base-class--mixin) ClassVar on `ClaimControlledModel`, defaulted empty, consumed by the claims executor before each write.

## The contract

`ClaimControlledModel` declares:

```python
immutable_after_create: ClassVar[frozenset[str]] = frozenset()
```

Default empty — every existing model is unaffected. Location declares:

```python
immutable_after_create: ClassVar[frozenset[str]] = frozenset({"parent"})
```

The claims executor, before writing each spec, checks: if the field is in `entity.immutable_after_create` and the **current row value** is non-null and would change, raise `ValidationError` and abort the transaction.

## Row value, not prior-claim, is the discriminator

"Reject if a prior claim exists" breaks for legitimate first-time writes; "reject if the row already has a value" captures the actual invariant — _this field, once it has a value, cannot change_.

For nullable fields where `None → value` is allowed (Location's top-level countries have `parent=None`), the check is `current is not None and current != new`. A consequence: a top-level country with `parent=None` is also frozen at `None` — a country can't later become a state of another country. That's the desired semantic.

## Why this lives on `ClaimControlledModel`

Like `claim_fk_lookups`, this is a claim-write concern, not a linkability concern. It's documented separately from the broader linkability work because Location's path materialization is what forces the opt-out, and the linkability contract is what makes re-parenting expensive in the first place. The mechanism itself is generic — any future model that needs immutable-after-create fields gets it for free, with no `isinstance` checks anywhere in the claims code.
