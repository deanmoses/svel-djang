# ClaimControlledModel Base

Extract the shared contract between `CatalogModel` and `Location` into a typed abstract base so that claim-resolver helpers (and any other code that operates generically over claim-controlled entities) can accept all of them under one static type.

Follow-up to [CatalogResolveBaselineCleanup.md](CatalogResolveBaselineCleanup.md). During that plan's revision, the helpers were retyped to `type[CatalogModel]` — which covers 19/20 callers. `Location` is the outlier and is cast at 2 call sites with a comment pointing at this plan.

The headline payoff is **not** the two disappearing casts — it's collapsing 20+ duplicated `claims = GenericRelation("provenance.Claim")` declarations into one canonical site and giving generic helpers a typed contract for "anything claim-controlled." The cast removal is a minor follow-on.

## Problem

Every claim-controlled catalog entity declares the same set of attributes:

- `claims = GenericRelation("provenance.Claim")` — reverse accessor to provenance claims. Duplicated verbatim on 20+ concrete models today (see `grep -rn 'claims = GenericRelation' backend/apps/catalog/models/`).
- `slug: SlugField(...)` — short URL-safe identifier. Uniqueness and max-length vary.
- `name: CharField(...)` — human-readable label. Max-length and validators vary.
- Optional `extra_data: JSONField` — unmatched-claim staging dict on a subset.

`CatalogModel` (via `LinkableModel`) declares typed `name: str` / `slug: str` at the abstract base level — which is why generic code that takes `type[CatalogModel]` can read those attributes without per-callsite casts. But `CatalogModel` also requires `entity_type` / `entity_type_plural` declarations (because `LinkableModel` is about _public URL-addressable_ entities) and inherits `SluggedModel`'s globally-unique `slug`.

`Location` deliberately opts out of that contract:

- Its `slug` is not globally unique — two different countries can both have cities with slug `springfield`. Uniqueness is scoped to `location_path` instead.
- It has no `entity_type` / `entity_type_plural` — Location is not a first-class URL-addressable catalog entity in the same way `MachineModel` or `Manufacturer` are.

So `Location` sits outside the `LinkableModel`/`CatalogModel` hierarchy even though, for the purposes of the claim resolver, it satisfies the same contract: it has `claims`, `slug`, `name`, and its fields are claim-controlled.

The consequences today:

- Generic helpers that want to operate on "any claim-controlled entity" have to pick between (a) `type[CatalogModel]` plus a cast at each Location call site, (b) `type[models.Model]` plus `_default_manager` swaps and scattered attribute ignores, or (c) a `runtime_checkable` Protocol. The Protocol option works for `slug: str` / `name: str` but breaks down on `claims` — `GenericRelation` is a descriptor whose runtime type (`RelatedManager`) is constructed per-class, and Protocols can't express "this attribute is a descriptor that resolves to a per-class generic manager." That `claims` requirement is the load-bearing reason an abstract base wins over a Protocol here, not a general dismissal of Protocols.
- The `claims = GenericRelation("provenance.Claim")` declaration is copy-pasted across 20+ models — no single place to change if the GenericRelation configuration ever needs to shift (e.g. `related_query_name`).
- Static type checkers can't express "anything claim-controlled" — every new such helper either accepts the looser type or invents a new cast site.

## Approach

Introduce a new abstract base — `ClaimControlledModel` — in `apps/provenance/models/`. Provenance owns `Claim`, owns the `GenericRelation` target, and has consumers of its own (the `type[models.Model]` annotations scattered through [provenance/validation.py](../../../backend/apps/provenance/validation.py) are really "type[ClaimControlledModel]" in disguise). "Anything that has claims" is a provenance-shaped abstraction, not a core or catalog one.

**App-boundary note.** Per [AppBoundaries.md](../../AppBoundaries.md), `core` depends on nothing — even string-reference dependencies. `apps/core/models.py` cannot host `GenericRelation("provenance.Claim")`, and for the same reason `CatalogModel` (which lives in core) cannot inherit `ClaimControlledModel`. Provenance is the correct home for the new base; catalog already depends on provenance, so concrete catalog models can inherit cleanly at the leaf.

**Hierarchy shape — `LinkableModel`, `CatalogModel`, and `ClaimControlledModel` stay separate.** They describe orthogonal capabilities:

- `LinkableModel` = "I have a public URL" (URL-addressability).
- `CatalogModel` = "I am a catalog entity" (marker for catalog-specific code paths; combines `LinkableModel` + `LifecycleStatusModel`).
- `ClaimControlledModel` = "I have provenance claims attached."

The overlap on the current concrete set is coincidental: every `LinkableModel` today happens to be a `CatalogModel` and every `CatalogModel` is claim-controlled, but neither inclusion is structural. `Location` is claim-controlled but not linkable. A future `UserProfile` could be linkable but not claim-controlled. Keeping the bases independent lets each capability evolve without dragging the others.

`LinkableModel` and `CatalogModel` stay in `core` untouched. Concrete catalog models multi-inherit `ClaimControlledModel` at the leaf:

- `MachineModel(CatalogModel, ClaimControlledModel, ...)` — URL-addressable + status-tracked + claim-controlled.
- `Manufacturer(CatalogModel, ClaimControlledModel, ...)` — same.
- ...20+ concrete catalog models, all already being touched to remove `claims = GenericRelation`.
- `Location(LifecycleStatusModel, ClaimControlledModel)` — claim-controlled and status-tracked, but not linkable.

The shared `name: str` / `slug: str` annotations on `LinkableModel` and `ClaimControlledModel` are independently justified — `LinkableModel` needs them because URLs are built from slugs; `ClaimControlledModel` needs them because the resolver reads them generically. The duplication is harmless at the MRO level.

```python
# apps/provenance/models/_base.py (or similar)

class ClaimControlledModel(models.Model):
    """Abstract base for entities whose display fields are claim-controlled.

    Declares the reverse-accessor to provenance claims and the typed ``slug``
    / ``name`` shape that claim-resolver helpers read generically.  Does NOT
    imply URL-addressability, globally-unique slugs, or status tracking —
    those are ``LinkableModel`` / ``SluggedModel`` / ``LifecycleStatusModel``
    concerns and are layered in independently at the concrete class.
    """

    # Instance-level annotations let ``type[ClaimControlledModel]`` code read
    # ``.slug`` / ``.name`` without casting.  Concrete subclasses declare the
    # actual CharField / SlugField with their own max_length and validators.
    slug: str
    name: str

    claims = GenericRelation("provenance.Claim")

    class Meta:
        abstract = True
```

Then:

- Each concrete catalog model: add `ClaimControlledModel` to its base list (e.g. `class MachineModel(CatalogModel, ClaimControlledModel, SluggedModel, TimeStampedModel): ...`). `CatalogModel` and `LinkableModel` themselves are unchanged.
- `Location`: change from `class Location(LifecycleStatusModel, models.Model)` to `class Location(LifecycleStatusModel, ClaimControlledModel)`.
- Remove `claims = GenericRelation("provenance.Claim")` from every concrete catalog model (20+ sites) — now inherited from `ClaimControlledModel`.

Once those are in place, generic helpers switch from `type[CatalogModel]` (or `type[models.Model]`) to `type[ClaimControlledModel]`:

- The 2 Location casts disappear: the type cast `cast(type[CatalogModel], Location)` in [catalog/resolve/\_\_init\_\_.py:197](../../../backend/apps/catalog/resolve/__init__.py#L197), and the instance cast `cast(CatalogModel, entity)` in [catalog/resolve/\_dispatch.py:225](../../../backend/apps/catalog/resolve/_dispatch.py#L225) (along with its explanatory comment at lines 221-224).
- Provenance helpers that take `type[models.Model]` for claim-bearing entities (~12 sites in `validation.py` — grep for `type[models.Model]` and pick the ones operating on claim-bearing entities) can tighten to `type[ClaimControlledModel]`.
- Downstream code that inspects `.claims` generically gains a typed contract.

## Things to verify before implementing

- **`GenericRelation` inheritance semantics.** Django's `GenericRelation` is a descriptor; confirm it survives abstract-base inheritance cleanly (it should, given how many projects do this). Run the migration and check that removing the per-model declaration doesn't produce a phantom migration.
- **Check-constraint name collisions.** Concrete subclasses use `field_not_blank("slug")` / `slug_not_blank()` which embed `%(app_label)s_%(class)s` — those stay on the concrete subclass, so no collision. But verify that no `constraints` list on a subclass refers to `slug` in a way that collides with anything the new base might add (the proposed base adds nothing).
- **`claims_exempt` / `claim_fk_lookups`.** These are concrete-class `ClassVar`s and stay on the concrete subclass. The new base does not declare them. Confirm `get_claim_fields` still works against the new hierarchy (it introspects `model_class._meta.get_fields()` which is unaffected).
- **Manager compatibility.** `CatalogManager[Self]` is declared on `LifecycleStatusModel` (see [core/models.py:248](../../../backend/apps/core/models.py#L248)), so every concrete subclass that mixes in `LifecycleStatusModel` — including `Location` — already has `CatalogManager`, not the default `models.Manager`. The new `ClaimControlledModel` base should NOT declare `objects`; the existing `LifecycleStatusModel`-supplied manager continues to apply unchanged.
- **Existing typing on `LinkableModel`.** `LinkableModel` already declares `name: str` / `slug: str`. With multi-inheritance at the leaf, both `LinkableModel` and `ClaimControlledModel` declare the same annotations — harmless but redundant at the MRO level. Leave `LinkableModel`'s declarations alone for this PR; touching `core` is also forbidden by the boundary rules that drove the provenance-home decision.
- **MRO and `Meta` inheritance.** Multi-inheriting two abstract bases (e.g. `LifecycleStatusModel` and `ClaimControlledModel`) is standard Django but verify Django doesn't complain about ambiguous `Meta` resolution. Both should declare only `abstract = True`, so there's nothing to merge.

## Scope and ordering

Land the structural change as a single atomic commit — model edits, removed declarations, and migration together — so the "migration is empty" invariant is verifiable in one diff:

1. Add `ClaimControlledModel` to `apps/provenance/models/` (new module, exported from the `provenance.models` package).
2. Add `ClaimControlledModel` to each concrete catalog model's base list (20+ leaf classes) and to `Location`'s base list. `CatalogModel` and `LinkableModel` in `core` are NOT modified — adding a provenance import to `core` would re-introduce the boundary violation this plan was rewritten to fix. The diff will be large-but-boring; the invariant test in step 3 is what makes this reviewable.
3. Remove 20+ `claims = GenericRelation("provenance.Claim")` declarations from concrete catalog models — now inherited from the new base.
4. **Add the structural invariant test.** Because opt-in is leaf-by-leaf, a missed leaf would silently drop the inherited `claims` relation — typecheck wouldn't catch it, and existing validator coverage only inspects models that already have a `claims` relation (so a model that lost it is invisible to those checks). Add a test in `apps/provenance/tests/` that:
   - Enumerates models with the exact expression: `django.apps.apps.get_app_config("catalog").get_models()` filtered by `not m._meta.abstract and (issubclass(m, CatalogModel) or m is Location)`. Do **not** use `CatalogModel.__subclasses__()` — it skips intermediate abstract layers. Do **not** enumerate by hand — it rots.
   - For each enumerated model, asserts `issubclass(model, ClaimControlledModel)`.
   - For each enumerated model, asserts `model._meta.get_field("claims").related_model is Claim`.

   This test is the canonical guard against future leaves being added without `ClaimControlledModel` in their bases.

5. Run `makemigrations`. The expected result is **no new migration** — pulling a `GenericRelation` to an abstract base is a Python-only change with no DDL impact. If Django _does_ emit a migration, **stop and investigate** before committing; a non-empty migration here means something about the field config differs and the rollover isn't actually a no-op.

   `--dry-run` catches field changes but not reverse-accessor churn from the reshuffle. Also sanity-check that `Claim._meta.related_objects` (count and targets) is unchanged before/after — a one-line REPL check, cheap insurance against a silent reconfiguration.

6. Flip the remaining helper signatures in `catalog/resolve/*.py` from `type[CatalogModel]` to `type[ClaimControlledModel]`; flip provenance helpers in `validation.py` from `type[models.Model]` to `type[ClaimControlledModel]` where they specifically operate on claim-bearing entities.
7. Remove the 2 Location casts and their follow-up comments.

Keep this PR purely structural — see "Reuse" below for tempting additions to defer.

## Non-goals

- Does NOT promote `Location` to `CatalogModel` / `LinkableModel`. Location's non-unique slug and non-public-addressability are real semantic differences that the narrower base respects.
- Does NOT unify the `extra_data` field — it remains per-model (some have it, some don't) and stays behind the existing `hasattr(obj, "extra_data")` runtime guard in the resolver.
- Does NOT introduce a shared manager class. `CatalogManager[Self]` continues to come from `LifecycleStatusModel` for every entity that mixes it in (including both `CatalogModel` subclasses and `Location`). The new `ClaimControlledModel` base does not declare `objects`.

## Verification

- `./scripts/mypy` — baseline `new: 0`. Several `attr-defined` / `arg-type` entries in `catalog/resolve/*.py` and any downstream caller that narrowed around the CatalogModel/Location split should drop.
- `uv run --directory backend pytest apps/catalog/tests/ apps/core/tests/ apps/provenance/tests/` — behavior-preserving; the migration should be a no-op and all resolver tests should pass. Includes the new structural invariant test at `apps/provenance/tests/test_claim_controlled_entity.py` (or similar).
- `uv run --directory backend python manage.py makemigrations --dry-run` — verify no surprise migrations after the GenericRelation pull-up.

## Reuse

The new base is the canonical home for _any_ future attribute that is universal across claim-controlled entities. Candidates to consider:

- `validate_check_constraints` as a method on the base.
- `resolve()` shortcut delegating to `resolve_entity`.
- `claims_exempt: ClassVar[frozenset[str]] = frozenset()` with the default declared once.

**Explicitly NOT in the initial PR.** The initial PR is purely structural: add the base, pull up `GenericRelation`, retype helpers, remove casts. Adding behavior to the base in the same change makes the "migration is empty / no behavior change" invariant much harder to verify in review, and bundles a refactor with a feature. Each of the candidates above is its own follow-up PR.

Resist bundling any of these in even if tempting — especially the `claims_exempt` default, which is one line and looks harmless. One line of behavior change in a 20+-file structural diff is exactly how "no behavior change" invariants get broken without anyone noticing.

## Out-of-scope follow-ups

- **Provenance `.claims` reverse accessors in other apps.** If any non-catalog code accesses `.claims` on a mixed set of catalog entities, it can also tighten to `ClaimControlledModel`. Grep before the flip to surface them.
- **Claim-field registry.** `get_claim_fields` currently takes `type[models.Model]`; once the base exists, narrowing to `type[ClaimControlledModel]` makes the contract explicit. Low priority.
