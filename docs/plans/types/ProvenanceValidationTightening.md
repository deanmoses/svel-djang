# Provenance Validation Tightening

## Context

This is **Step 2** of [ResolveHardening.md](ResolveHardening.md) — the write-path foundation of a multi-step sequence that tightens the claim-value contract across `catalog/resolve/*`:

- **Step 2 (this doc)** — unify the three registries that hand-maintain catalog relationship namespace knowledge today, and tighten the write-path shape validation that the unified registry now makes expressible.
- **Step 3** — [Claim-value TypedDicts + resolver casts + consistency test](CatalogResolveTyping.md). Introduces TypedDicts over the resolver read path that mirror this doc's registry, plus a consistency test enforcing the mirror holds.
- **Step 4** — [Mypy baseline burn-down on `catalog/resolve/*`](CatalogResolveBaselineCleanup.md). Helper signatures + tuple-reuse cleanup. Not load-bearing for the hardening story, bundled because it touches the same files.
- **Step 5** — [Subscript flip](ResolverReadsTightening.md). Flips resolver reads from `cast + .get()` to subscript access for required keys — sound only because Step 2's write-path validation now guarantees required keys are present, _and_ because Step 2's post-merge wipe + re-ingest has rebuilt stored rows under the new validator.

### Primary work: unify three hand-maintained registries

Namespace knowledge for catalog relationships lives in three registries today, covering overlapping ground:

- `_entity_ref_targets` in [catalog/claims.py](../../../backend/apps/catalog/claims.py) — `namespace → [RefKey(name, model)]`. Drives FK claim construction.
- `_literal_schemas` in [catalog/claims.py](../../../backend/apps/catalog/claims.py) — `namespace → LiteralKey(value_key, identity_key)`. Drives literal claim construction.
- `_relationship_target_registry` in [apps/provenance/validation.py](../../../backend/apps/provenance/validation.py) — namespace → FK existence targets. Drives batch validation.

Adding or changing an FK namespace means touching two of these in lockstep; there's no cross-check that they agree. Step 3 is about to introduce a fourth source of truth: TypedDicts over the resolver read path, which must agree with the write-path schema for Step 5's subscript flip to be sound. Adding that fourth without unifying first is strictly worse than today — four hand-maintained registries, drift risk every time a namespace is added, no mechanical way to enforce agreement.

**Unify to one registry** (`_relationship_schemas` in `provenance/validation.py`) that drives claim construction (`build_relationship_claim`), namespace enumeration (`get_relationship_namespaces`), write-path validation (shape + existence), and — via Step 3's consistency test — the read-side TypedDicts in `_claim_values.py`. After this work, adding a namespace is one `register_relationship_schema(...)` call + one TypedDict (test-enforced to match). Two places.

The unified registry is what earns Step 3's consistency test its keep: it's the single authority the TypedDicts are tested against. Without unification, the TypedDicts would have three disagreeing registries to reconcile with, and the test would either not exist or silently gloss over the disagreements.

### Along for the ride: three silent-data-loss bugs

The unified registry makes shape validation expressible in one place, and three pre-existing holes in the write path get closed as a natural consequence rather than as standalone tightening:

- **`assert_claim` bypasses relationship validation.** [claim.py:121-127](../../../backend/apps/provenance/models/claim.py#L121) classifies each claim and only validates `DIRECT` payloads; `RELATIONSHIP` passes through untouched. User edits via `execute_claims` → `assert_claim` therefore never reach any relationship shape check.
- **Malformed payloads misclassify as EXTRA.** [classify_claim](../../../backend/apps/provenance/validation.py#L86) returns `RELATIONSHIP` only if `"exists" in value`. On any model with an `extra_data` field (MachineModel, Title, …), a malformed credit/theme/alias payload lacking `"exists"` falls through to `EXTRA` and gets silently stored as free-form staging data — never hitting the relationship validator at all.
- **Literal namespaces have no schema.** [validate_relationship_claims_batch](../../../backend/apps/provenance/validation.py#L359) only validates namespaces registered via `register_relationship_targets`, which covers FK value_keys. Aliases (`alias_value`, `alias_display`) and abbreviations (`value`) are intentionally unregistered today and pass through without any schema check.

Closing these is also load-bearing for Step 5: the subscript flip only becomes safe once the write path guarantees required keys are present on stored claims. So the bug-fixes aren't just opportunistic — they're the other half of what unblocks Step 5.

We're pre-launch. Loosening later is a one-line change; tightening later requires auditing every production row. **Err tight.**

**Data posture.** The DB can be dropped and all migrations reset to 0001. The remediation path for any malformed legacy rows surfaced by the new validator is: wipe the DB, reset migrations, `make pull-ingest`, `make ingest`. No audit script, no row-level cleanup, no `is_active=False` sweeps. If re-ingestion produces rejections, that is an extractor bug — fix at the source (where the malformed shape originated), re-ingest, repeat.

The validator runs on new writes only; it does **not** re-validate already-stored rows. What makes the posture safe is the wipe+re-ingest, not the validator itself — the validator is the tripwire that catches future malformed writes, the wipe is what guarantees every currently-stored claim was written under the new rules. Pre-launch there are no user-edit claims in shared env, so nothing is lost by wiping. Before merge, confirm that assumption still holds (no one has started using `execute_claims` against staging); if it doesn't, this posture needs revisiting.

## Non-goals

- **Not adding target-existence validation to the single-write path.** Existence stays batch-only. `validate_relationship_claims_batch` already groups claims by namespace and issues one SQL query per group — cheap amortized. Doing the same check in `assert_claim` would be one query per claim, and `execute_claims` writes many claims per user edit (e.g. editing a Title's gameplay features). The brief window of tolerated stale FK targets is an explicit trade-off: stale targets get caught at the next bulk resolve. If we later see drift in practice, benchmark before changing.
- **Not reworking `extra_data` semantics.** Claims that genuinely belong in `EXTRA` (unrecognized field names on models with `extra_data`) still flow through untouched.
- **Not touching DIRECT claim validation.** `validate_claim_value` stays as-is.
- **Not collapsing bespoke resolvers into a generic spec-driven resolver.** The registry added here is intentionally consumed by `classify_claim`, `validate_single_relationship_claim`, `validate_relationship_claims_batch`, and `build_relationship_claim` only. Folding `_parent_dispatch` / `_custom_dispatch` / `M2M_FIELDS` into one generic resolver is a plausible follow-up that can consume the same registry. Commit `2eea1ebaf` standardized every bespoke resolver on `(subject_ids: set[int] | None = None) -> None`, so the signature-divergence obstacle is already gone — what remains is the latent behavior change in `resolve_all_corporate_entity_locations` (which today filters `is_active=True` before winner selection) that must not be bundled into an otherwise behavior-preserving registry unification. Keeping the collapse out of scope here bounds the PR and defers the `is_active` decision.
- **Not lifting the identity-vs-UC cross-check from [CatalogRelationshipSpec](../model_driven_metadata/ModelDrivenCatalogRelationshipMetadata.md).** That guard — verifying `subject_fks ∪ identity_fields` matches one `UniqueConstraint` per through-model at `ready()` — is genuinely useful, but it belongs with the model-driven metadata work it was drafted for. Pulling it in here would motivate `through_model` and `subject_fks` on the schema, which would force `(namespace, subject_content_type)` keying and the "abbreviation registers twice" complication — all scaffolding for a check the rest of this PR does not use. Deferred as a whole.
- **Not collapsing the separate `identity` label into the value-key `name`.** `ValueKeySpec.identity: str | None` exists to preserve today's divergence where e.g. alias namespaces use value-key `"alias_value"` with identity label `"alias"` (matching the current `LiteralKey("alias_value", "alias")` shape). A simpler design would drop `identity` entirely, use `is_identity: bool`, and always compose `claim_key` from the value-key `name` — one fewer invariant to enforce at registration, one fewer concept for future readers. The post-merge wipe + re-ingest rebuilds every `claim_key` under the new rules, so the _stored_ format isn't constrained by backwards compatibility. What _is_ constrained: `build_relationship_claim` accepts identity-label kwargs today (e.g. `build_relationship_claim("theme_alias", alias="foo", exists=True)`), and collapsing the label means flipping every such call site to the value-key name (`alias_value="foo"`). That's a caller-side rewrite touching adapters, management commands, and tests — the same ~40-site blast radius as threading `subject_model` through, and with no safety payoff. Keeping the indirection is the cheaper choice today; if a future pass collapses the registry for clarity, the `claim_key` format is still free to change under the same wipe+re-ingest posture.
- **Not threading `subject_model` through `build_relationship_claim`.** The wrong-subject check moves from _build time_ (where, today, calling `build_relationship_claim("credit", …)` on a Title-bound adapter would have no registered entity*ref_targets to match) to \_write time* (`assert_claim` / batch validation both reject). That's a regression in failure locality — a buggy adapter can now construct a well-formed-but-wrong-subject `Claim` object that only fails on persist. Accepted because: (a) the write-path rejection still catches it before the row lands, (b) threading `subject_model` would touch ~40 call sites across adapters, management commands, and tests in Commit A, defeating the "mechanical rewrite" posture, and (c) the two call sites that matter for safety — `assert_claim` and `validate_claims_batch` — already have the subject model in hand and pass it to the validator. **Debugging note:** if a test constructs a Claim object that's well-formed but never persists, and the error is "ValidationError: subject not in schema.valid_subjects", check `build_relationship_claim` — the subject model wasn't in the registered namespace's valid_subjects.

## Design

### Registry API

Module-level registry of relationship schemas in [apps/provenance/validation.py](../../../backend/apps/provenance/validation.py). Replaces `_relationship_target_registry` and (via the catalog-side refactor below) also replaces `_entity_ref_targets` and `_literal_schemas` from `catalog/claims.py`.

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class ValueKeySpec:
    """One key in a relationship claim's value dict."""
    name: str
    scalar_type: type  # int, str, or bool — matched with `type(v) is scalar_type`
    required: bool
    nullable: bool = False  # True allows `None` in addition to scalar_type
    identity: str | None = None
    # If set, this key participates in the claim_key identity and the string
    # is the label used in the identity dict. Use `name` when the label
    # matches the value_key name (e.g. identity="person" for value_key "person").
    # Use a different string when they differ (e.g. identity="alias" for
    # value_key "alias_value" — matches today's LiteralKey("alias_value", "alias")).
    # None means this key is non-identity (e.g. count, category, alias_display).
    # **INVARIANT:** identity is not None ⇒ required=True. Identity keys must
    # be required, otherwise the canonical claim_key formula depends on whether
    # the caller chose to include optional identity keys, and two well-formed
    # writes for the same entity could land under different claim_keys. Enforced
    # at registration time in register_relationship_schema.
    fk_target: tuple[type[models.Model], str] | None = None
    # If set, (target_model, lookup_field) — this value_key is an FK reference
    # and batch-path existence checks apply via validate_relationship_claims_batch.

@dataclass(frozen=True, slots=True)
class RelationshipSchema:
    namespace: str                                     # claim field_name, e.g. "credit", "theme_alias", "abbreviation"
    value_keys: tuple[ValueKeySpec, ...]
    valid_subjects: frozenset[type[models.Model]]      # subject model classes this namespace applies to

# Registry keyed by namespace. Shared-namespace cases (abbreviation, credit,
# media_attachment) register once with multiple valid_subjects.
_relationship_schemas: dict[str, RelationshipSchema] = {}

def register_relationship_schema(
    namespace: str,
    value_keys: tuple[ValueKeySpec, ...],
    valid_subjects: frozenset[type[models.Model]],
) -> None:
    # Invariant: identity keys must be required, otherwise the canonical
    # claim_key formula depends on whether optional identity keys are present.
    for spec in value_keys:
        if spec.identity is not None and not spec.required:
            raise ImproperlyConfigured(
                f"namespace {namespace!r}, value_key {spec.name!r}: "
                f"identity keys must be required (identity={spec.identity!r}, required=False)"
            )
    new = RelationshipSchema(namespace=namespace, value_keys=value_keys, valid_subjects=valid_subjects)
    existing = _relationship_schemas.get(namespace)
    if existing is not None:
        # Idempotent re-registration (Django may run ready() more than once
        # in some test/app-registry scenarios). Identical schemas are a no-op;
        # conflicting schemas are a genuine drift bug and must raise.
        if existing == new:
            return
        raise ImproperlyConfigured(
            f"namespace {namespace!r} already registered with a different schema"
        )
    _relationship_schemas[namespace] = new

def get_relationship_schema(namespace: str) -> RelationshipSchema | None:
    return _relationship_schemas.get(namespace)

def is_valid_subject(schema: RelationshipSchema, subject_model: type[models.Model]) -> bool:
    return subject_model in schema.valid_subjects
```

**Registration is DB-free.** `RelationshipSchema` stores model classes, not ContentType IDs. `register_relationship_schema` never touches the DB, so `CatalogConfig.ready()` is safe to call during `migrate` on a fresh DB (contenttypes table absent) or during test setup — matching the existing `register_relationship_targets` contract. The collision guard's `get_claim_fields(subject_model)` call is also DB-free — it iterates `model._meta.get_fields()` (app-registry introspection, verified at [core/models.py:317](../../../backend/apps/core/models.py#L317)) with no ORM calls. Subject validation operates on model classes throughout:

- `assert_claim` path already has `model_class = type(subject)` in hand — passes directly.
- Batch path reuses the existing `model_cache: dict[int, type[models.Model]]` keyed by `content_type_id` (populated via `ContentType.objects.get_for_id(ct_id).model_class()`). Do not use `claim.content_type.model_class()` — bulk-ingest builds unsaved `Claim` objects with only `content_type_id` set, and the FK descriptor would issue a query per claim.

No CT-ID caching on the schema; no lazy post-ready precomputation; no subtle ordering bug when schemas are registered before the `django_content_type` table exists.

**Idempotent registration** preserves the existing `register_relationship_targets` posture (dict-assignment idempotency) while still catching genuine drift (conflicting re-registration raises). Requires `RelationshipSchema` and `ValueKeySpec` equality to work, which `@dataclass(frozen=True, slots=True)` gives us automatically — `frozenset[type[Model]]` compares by membership, `tuple[ValueKeySpec, ...]` compares element-wise. Equality on `fk_target: tuple[type[Model], str]` is identity-on-the-class-object, which holds because Django's app registry guarantees model classes are singletons within a process — the same `Person` class object is handed back on every `apps.get_model("catalog", "Person")` call and every `from apps.catalog.models import Person`. For the `media_attachment` schema specifically, `apps.get_models()` returns models deterministically ordered by app loading order; if `ready()` fires twice in a test scenario, both walks produce the same frozenset membership, so re-registration equality holds.

**Edge case.** `override_settings(INSTALLED_APPS=...)` and similar app-registry reload patterns in tests can produce fresh model class objects that fail identity equality with the originally-registered ones, turning an idempotent re-registration into a spurious conflict. No current test does this, but if it ever bites, switch the equality basis from `type[Model]` identity to `(app_label, model_name)` labels (e.g. `frozenset(m._meta.label_lower for m in valid_subjects)`) rather than loosening the conflict guard.

**Registration-time collision guard.** `register_relationship_schema` additionally rejects any `namespace` that collides with any concrete field (as returned by `get_claim_fields()` — see [apps.core.models.get_claim_fields](../../../backend/apps/core/models.py)) on any class in `valid_subjects`. Implementation: for each `subject_model in valid_subjects`, check `namespace not in get_claim_fields(subject_model)`. Raises `ImproperlyConfigured` on collision. This matches the classifier's actual lookup — both consult the same field set (concrete fields, excluding reverse relations, primary keys, and infrastructure fields). Today no catalog namespace collides with any concrete field name, but nothing in the rest of this design prevents someone from adding one; without this guard, the classifier silently routes the collision to DIRECT (see "Classification change" below) and the relationship schema becomes dead code on that subject. Catching at `ready()` is free and makes the invariant a failure mode the reviewer can't miss.

`ValueKeySpec.identity` subsumes what `RefKey` and `LiteralKey` carry today. An FK reference like `{"person": int}` uses `identity="person"` (label equals name). An alias key like `alias_value: str` uses `identity="alias"` — matching the current `LiteralKey("alias_value", "alias")` shape. Non-identity optional keys (`count`, `category`, `is_primary`, `alias_display`) leave `identity=None`.

### Registry is keyed by namespace

One schema per namespace, not per `(namespace, subject)`. Shared-namespace cases (`abbreviation` on Title vs MachineModel, `credit` on MachineModel vs Series, `media_attachment` on N subjects) register once with multiple `valid_subjects`; this works because the value-key shapes are identical across those subjects today. **This is a structural assumption with no enforcement** — if a future requirement makes e.g. Title's `abbreviation` grow an optional field MachineModel's doesn't have, namespace-only keying breaks and the registry has to refactor to `(namespace, subject)` keying (the shape the deferred CatalogRelationshipSpec work lands on anyway). Accept this: today's shapes genuinely are identical across subjects, and the refactor when it happens is mechanical. The subject model class is resolved per claim (from `type(subject)` in `assert_claim`; from the existing `model_cache` in the batch path, populated via `ContentType.objects.get_for_id(ct_id).model_class()`) and passed to `is_valid_subject(schema, model_class)` — a check owned by the validator, not a registry-key discriminator. This keying is what a pre-launch hand-maintained registry needs; the `(namespace, subject_ct)` keying required for the UC cross-check belongs with the deferred spec work (see Non-goals).

### Catalog-side consolidation

[apps/catalog/claims.py](../../../backend/apps/catalog/claims.py) loses `_entity_ref_targets`, `_literal_schemas`, `RefKey`, `LiteralKey`, `_get_entity_ref_targets`, `_get_literal_schemas`, and `register_relationship_targets`. In their place:

- `register_catalog_relationship_schemas()` — one function called from `CatalogConfig.ready()`. Replaces `register_relationship_targets()`. Body is a series of `register_relationship_schema(namespace=..., value_keys=..., valid_subjects=...)` calls, one per namespace. The schemas are _the_ source: no intermediate dict.
- `build_relationship_claim(field_name, identity, exists)` — signature unchanged. Reworked internally to read from `get_relationship_schema(field_name)` and iterate `schema.value_keys` where `identity is not None`, using `spec.identity` as the claim_key label and `spec.name` as the value_dict key. Subject model is **not** threaded through this function — the wrong-subject rejection runs in the validator, which receives `subject_model` explicitly from its two call sites (`type(subject)` in `assert_claim`; cached `model_class` in the batch path). Keeping the signature stable avoids touching ~40 call sites across adapters, management commands, and tests in Commit A.
- `get_relationship_namespaces()` — returns `frozenset(_relationship_schemas)`.
- `get_all_namespace_keys()` — derived from the registry via a similar iteration. Used only in tests today; safe to rewrite.

Alias types added dynamically via `discover_alias_types()` must now call `register_relationship_schema` at discovery time instead of populating `_literal_schemas`. That hook lives in `register_catalog_relationship_schemas()` — same target registry, but the **timing shifts from lazy to eager**: today `_get_literal_schemas()` calls `discover_alias_types()` on first access (cached); under this plan it runs inside `ready()`. This is safe because every `AliasBase` subclass lives in `apps.catalog.models.*` and is imported by Django's model registry before `CatalogConfig.ready()` fires — verified today as 7 subclasses: `ThemeAlias`, `ManufacturerAlias`, `CorporateEntityAlias`, `PersonAlias`, `GameplayFeatureAlias`, `RewardTypeAlias`, `LocationAlias`. If a future contributor adds an `AliasBase` subclass outside the `apps.catalog.models` package (or defines one lazily post-`ready()`), the eager walk will miss it — the `alias_claim_field` validation in `AliasBase.__init_subclass__` already exists as the forcing function, but the eager-registration shift means missing aliases surface as "unknown namespace" rejections at write time rather than silent fallthrough. That's the intended posture.

No behavior change for any consumer of the public surface (`build_relationship_claim`, `get_relationship_namespaces`, `get_all_namespace_keys`). Existing call-site tests stay green.

Registered schemas (full coverage — must match the read-side TypedDicts in `catalog/resolve/_claim_values.py`):

- `"credit"` — `valid_subjects=(MachineModel, Series)`. Value keys: `{person: int (identity="person", fk=Person.pk), role: int (identity="role", fk=CreditRole.pk)}`.
- `"gameplay_feature"` — `valid_subjects=(MachineModel,)`. Value keys: `{gameplay_feature: int (identity="gameplay_feature", fk=GameplayFeature.pk), count: int | None (optional)}`.
- `"theme"` / `"tag"` / `"reward_type"` — `valid_subjects=(MachineModel,)`. Value keys: `{<namespace>: int (identity=<namespace>, fk=<target>.pk)}`.
- Alias namespaces (7) — one schema each. `valid_subjects=(<owner>,)`. Value keys: `{alias_value: str (identity="alias"), alias_display: str (optional)}`.
- `"abbreviation"` — `valid_subjects=(Title, MachineModel)`. Value keys: `{value: str (identity="value")}`.
- `"media_attachment"` — `valid_subjects` is derived at registration time by walking `django.apps.apps.get_models()` and filtering to concrete (`not m._meta.abstract`) subclasses of `MediaSupported`. Matches the repo pattern used at [apps.py:28](../../../backend/apps/catalog/apps.py#L28) and [signals.py:35](../../../backend/apps/catalog/signals.py#L35). `__subclasses__()` would miss transitive subclasses if an intermediate abstract base is ever introduced; `get_models()` handles that case. Today this produces four concrete models: `GameplayFeature`, `MachineModel`, `Manufacturer`, `Person` — **all currently in [apps.catalog.models](../../../backend/apps/catalog/models/)**. Value keys: `{media_asset: int (identity="media_asset", fk=MediaAsset.pk), category: str | None (optional), is_primary: bool (optional)}`. **App-load ordering:** `apps.get_models()` only returns models whose app has had `AppConfig` loaded; Django loads all `INSTALLED_APPS` before firing any `ready()`, so every `MediaSupported` subclass defined in an installed app is visible by the time `CatalogConfig.ready()` runs. Before this PR lands, verify the four concrete subclasses (GameplayFeature, MachineModel, Manufacturer, Person) are all in installed apps and live in `apps.catalog.models` or another app listed before catalog in `INSTALLED_APPS`. If a future contributor adds a `MediaSupported` subclass in an app that isn't in `INSTALLED_APPS` (or in a module Django never imports), the walk misses it — same failure mode as any `get_models()` consumer and surfaced by the same existing patterns at apps.py:28 / signals.py:35.
- `"location"` — `valid_subjects=(CorporateEntity,)`. Value keys: `{location: int (identity="location", fk=Location.pk)}`.
- `"theme_parent"` / `"gameplay_feature_parent"` — `valid_subjects=(Theme,)` / `(GameplayFeature,)`. Value keys: `{parent: int (identity="parent", fk=<self>.pk)}`.

### Classification change

**Full decision tree for `classify_claim(model_class, field_name, claim_key, value)`:**

1. If `field_name in get_claim_fields(model_class)` — i.e., a concrete DIRECT field (see [apps.core.models.get_claim_fields](../../../backend/apps/core/models.py)) which excludes reverse relations, primary keys, and infrastructure fields — return `DIRECT`. The registration-time collision guard (see "Registry API") guarantees no registered namespace shares a name with any DIRECT field on its `valid_subjects`, so step 1 and step 2 are structurally disjoint — this is routing, not precedence.
2. Else if `get_relationship_schema(field_name)` returns a schema, return `RELATIONSHIP`. **Regardless** of whether this subject is in the schema's `valid_subjects` (wrong-subject rejection happens in the validator, not here), **regardless** of whether `"exists"` is present in `value`. This replaces the old structural check (`claim_key != field_name and isinstance(value, dict) and "exists" in value`) for non-direct fields.
3. Else if the model has an `extra_data` field, return `EXTRA`.
4. Else return `UNRECOGNIZED` — unchanged from today. `assert_claim` raises `ValueError` on UNRECOGNIZED at [claim.py:122-125](../../../backend/apps/provenance/models/claim.py#L122); `validate_claims_batch` logs and rejects at [validation.py:255](../../../backend/apps/provenance/validation.py#L255).

The key changes: (a) registry lookup replaces the structural `claim_key != field_name and "exists" in value` heuristic; (b) wrong-subject case now routes to the validator instead of silent EXTRA fallthrough; (c) malformed relationship payloads on models with `extra_data` that used to collapse to EXTRA now route to RELATIONSHIP → validator → rejection; (d) the `UNRECOGNIZED` terminal state is preserved exactly as today — this plan does not change what happens when a field name is genuinely unknown.

**No separate DIRECT-precedence test.** The registration guard and the classifier consult the same field set (`get_claim_fields`), so the "what if both match?" case cannot occur under any non-monkey-patched state. Testing it would mean mutating `_relationship_schemas` directly to violate the guard's invariant, which is a test of the guard (that its invariant holds) rather than a test of the classifier. Guard coverage belongs with `register_relationship_schema` — see the TDD section.

### Single-claim validator

Factor a new `validate_single_relationship_claim` out of `validate_relationship_claims_batch`. Raises `ValidationError` on shape violation.

Signature accepts the pieces both paths actually have, not a `Claim` object — because `ClaimManager.assert_claim` validates _before_ the `Claim` row is built (see [claim.py:121](../../../backend/apps/provenance/models/claim.py#L121) where `classify_claim` is called with `(model_class, field_name, claim_key, value)`, and the `Claim` isn't created until line 140):

```python
def validate_single_relationship_claim(
    *,
    subject_model: type[models.Model],
    field_name: str,
    claim_key: str,
    value: Any,
) -> None:
    ...
```

Called from:

- `ClaimManager.assert_claim` at [claim.py:127](../../../backend/apps/provenance/models/claim.py#L127), in a new branch for `ct_result == RELATIONSHIP` that passes `subject_model=type(subject)` (already in scope as `model_class`) and propagates the `ValidationError`.
- `validate_claims_batch` at [validation.py:251](../../../backend/apps/provenance/validation.py#L251), replacing the accumulate-then-batch-validate path for shape. Reuse the existing `model_cache: dict[int, type[models.Model]]` at [validation.py:220](../../../backend/apps/provenance/validation.py#L220) (populated via `ContentType.objects.get_for_id(ct_id).model_class()`) and pass the cached `model_class` into the validator. Do **not** use `claim.content_type.model_class()` — bulk-ingest builds unsaved `Claim` objects with only `content_type_id` set, and the FK descriptor would issue a query per claim. Per-claim validation (O(N) registry dict lookups + O(N) `make_claim_key` calls) is negligible overhead — bulk ingest is I/O bound on the DB queries for FK-existence checks, which remain batched in `validate_relationship_claims_batch`. Existence checks remain batched in `validate_relationship_claims_batch`.

### Rejection conditions (shape)

Applied by `validate_single_relationship_claim` in both paths.

**Check order is load-bearing**, not cosmetic. Each rule below assumes its predecessors have passed — reordering trades a clean `ValidationError` for a `TypeError` / `KeyError` that masks the real problem. The validator must evaluate them top-to-bottom and return on the first failure:

1. **Wrong subject**: `subject_model not in schema.valid_subjects` (e.g. `field_name="credit"` on a `Title`). Closes the silent-EXTRA-fallthrough class for misrouted namespaces. First because continuing to shape-check a misrouted namespace produces a less informative error than naming the routing problem directly.
2. **Non-dict `value`**: `type(value) is not dict`. Must precede every subsequent rule — they all index into `value`.
3. **Missing/non-bool `"exists"`**: `"exists" not in value` or `type(value["exists"]) is not bool`. (Deliberately `type(...) is bool`, not `isinstance` — same reasoning as scalar_type below; the whole point of the strict rule is that `True`/`False` are `int` subclasses.)
4. **Missing required key**: any `ValueKeySpec` with `required=True` whose `name` is not in `value`. Must precede the canonical `claim_key` check, which composes identity parts via `value[spec.name]` and would `KeyError` on a missing required identity key.
5. **Wrong scalar type for any present registered key** (required or optional). `type(v) is spec.scalar_type`, or `v is None` when `spec.nullable=True`. Applies to identity keys (`person: int`, `alias_value: str`) and non-identity keys (`count: int | None`, `category: str | None`, `is_primary: bool`, `alias_display: str`).
6. **Unknown keys**: any key in `value` other than `"exists"` or a name in `schema.value_keys`. Prevents typos (`{person, role, rol}`) and stale fields from accumulating indefinitely in stored claim payloads. Same class of silent-drift as the silent-EXTRA-fallthrough — if extractors or adapters produce typos or leftover keys, nothing else rejects them today. **Applies uniformly to retractions (`exists=False`)** — a retraction carrying a stale extra key is rejected the same as a positive claim. The retraction carve-out below is scoped to FK-target _existence_, not shape. Safe because every retraction path in-repo constructs the value dict from canonical identity inputs (PK or alias value), never by echoing a prior claim's stored value — audited at [edit_claims.py:342,390,453,517,599,732](../../../backend/apps/catalog/api/edit_claims.py) and [media/api.py:330](../../../backend/apps/media/api.py#L330). If a future retraction path echoes stored values, it must reshape through the registry first.
7. **Non-canonical `claim_key`**: `claim_key != make_claim_key(field_name, **{spec.identity: value[spec.name] for spec in schema.value_keys if spec.identity is not None})`. Runs last because it depends on rules 2, 4, and 5 having passed (value is a dict, every identity `spec.name` is present, and the values are well-typed). `make_claim_key` internally sorts its kwargs (see [claim.py:61](../../../backend/apps/provenance/models/claim.py#L61) `for k in sorted(identity_parts)`), so the dict-comprehension order doesn't matter — the canonical form is pinned. Covers two failure modes that slip past value-shape rejections today: (a) caller passes no `claim_key` at all, so `assert_claim` defaults it to `field_name` ([claim.py:107-108](../../../backend/apps/provenance/models/claim.py#L107)) — a scalar key that collapses every `credit`/`theme`/`media_attachment` on the subject into a single identity for winner selection and supersession; (b) caller passes a `claim_key` whose identity parts drift from the value's identity fields (wrong PK, stale alias). The value is well-formed but lands under the wrong identity, so a later correct write doesn't supersede it.

**`None` handling.** A key is "present" iff its name appears in `value` — including when its value is `None`. For a spec with `nullable=True`, a present `None` is accepted (in addition to `type(v) is scalar_type`). For a spec with `nullable=False`, a present `None` is rejected. This applies uniformly to required and optional keys: `required=True, nullable=True` accepts `None`; `required=False, nullable=False` rejects `{key: None}` but accepts absence.

**Caller audit (completed 2026-04-24).** Every production `Claim.objects.assert_claim(...)` call for a relationship namespace passes `claim_key=` explicitly: three sites in [apps/media/api.py](../../../backend/apps/media/api.py) (`"media_attachment"`) and one in [apps/catalog/api/edit_claims.py:771](../../../backend/apps/catalog/api/edit_claims.py#L771) (forwards `spec.claim_key`). [scrape_images.py:215](../../../backend/apps/catalog/management/commands/scrape_images.py#L215) omits `claim_key=` but writes a DIRECT scalar (`image_urls`), which bypasses this check. So the non-canonical-claim_key rejection does **not** silently break any current caller. Any future caller that forgets `claim_key=` on a relationship namespace gets a clean `ValidationError` — that's the intended tightening, not a regression.

**`execute_claims` audit (complete before Commit B).** The direct-`assert_claim` audit above covers the two sites that call `assert_claim` directly, but the primary user-edit entry point is `execute_claims(entity, specs, user=..., action=...)`, which forwards `spec.claim_key` into `assert_claim` internally. Two follow-ups needed before Commit B lands:

1. **Spec producers must emit canonical `claim_key`s.** Grep every `ClaimSpec(...)` / spec-dict producer in [apps/catalog/api/edit_claims.py](../../../backend/apps/catalog/api/edit_claims.py) and any other caller of `execute_claims`, and confirm each relationship-namespace spec either (a) sets `claim_key` via `build_relationship_claim(...).claim_key`, or (b) sets it via an equivalent canonical composition. Any producer that hand-builds a relationship-namespace `claim_key` string starts raising `ValidationError` post-Commit B. Expected to be clean today (Commit A's claim_key equivalence test pins `build_relationship_claim` output to `make_claim_key`), but the producer side is a separate surface from the `assert_claim` caller side and needs its own walk.
2. **Partial-failure posture inside `execute_claims` must be explicit.** `execute_claims` writes many claims per user edit. If one spec fails shape validation mid-edit, the options are (a) abort the whole ChangeSet transactionally, (b) skip the bad spec and commit the rest. Today's code runs inside a `transaction.atomic()` block, so a raised `ValidationError` aborts the whole edit; that's the right posture (partial edits are worse than rejected edits — a user seeing "save failed" and retrying is cleaner than silently losing half a form submission). Confirm the atomic wrapper is still in place when Commit B wires the validator in, and add a regression test asserting that a multi-spec edit with one malformed relationship spec rolls back all the others. Document the posture in `execute_claims`'s docstring so a future refactor can't silently flip it.

**Why `type(value) is scalar_type`, not `isinstance(value, scalar_type)`.** `bool` is a subclass of `int` in Python, so `isinstance(True, int)` is `True`. A payload carrying `{"person": True}` or `{"count": False}` should be rejected, not silently accepted as PK `1` / count `0`. The primary threat is Python-side code (tests, ingest adapters) passing bools where ints belong; `json.loads` of `{"x": true}` also produces `bool`, so the rule catches wire payloads too. Future readers should not loosen this to `isinstance`. For `nullable=True` specs, accept `None` in addition to `type(v) is scalar_type`.

`IntEnum` / `StrEnum` / numpy scalar types (`numpy.int64`, etc.) pass `isinstance` but fail `type(v) is …`. **Grep performed 2026-04-24**: `grep -rn "import numpy\|import pandas\|from numpy\|from pandas\|IntEnum\|StrEnum" backend/apps/catalog/adapters/ backend/apps/catalog/management/commands/` returns zero matches. No unwrap work needed in Commit A. If a future adapter lands with enum/numpy values, the right fix is unwrapping at the adapter boundary (e.g. `int(numpy.int64(...))`), not loosening the check.

### Rejection conditions (existence — batch only)

Unchanged from today, including the explicit carve-out that **retractions (`exists=False`) are exempt from FK-target existence**. A retraction references a previous assertion, not a current row — the target may already have been deleted and the retraction must still succeed, otherwise claims about deleted entities could never be retracted. Identity keys remain required on retractions so batch resolve knows which row to remove; shape validation (above) applies uniformly to positive claims and retractions.

`validate_relationship_claims_batch` continues to do per-namespace group queries for FK `ValueKeySpec`s where `exists=True`; `exists=False` entries skip that check. `assert_claim` does not do existence checks regardless of `exists` — see Non-goals.

Test coverage for the retraction carve-out lives in [`test_validation.py`](../../../backend/apps/provenance/tests/test_validation.py) (explicit case for retractions against deleted targets). Do not remove or loosen without replacing.

## Commit sequence

### Before writing any code

Two gates that must pass before Commit A begins. Both are mechanical, both take under a minute:

1. **Confirm shared-env data posture.** Run `Claim.objects.filter(user__isnull=False).exists()` via `python manage.py shell` against the shared environment. `False` ⇒ proceed; the post-merge wipe is guaranteed clean. `True` ⇒ stop and revisit the "Data posture" section with the doc owner — user-edit claims exist that will be destroyed by the wipe, and the recovery path (re-ingest) won't reproduce them.
2. **Confirm no new adapter hazards.** Re-run the 2026-04-24 grep: `grep -rn "import numpy\|import pandas\|from numpy\|from pandas\|IntEnum\|StrEnum" backend/apps/catalog/adapters/ backend/apps/catalog/management/commands/`. Zero matches ⇒ proceed. Non-zero ⇒ the `type(v) is scalar_type` rule needs an unwrap-at-boundary fix in Commit A (see "Rejection conditions (shape)").

### The two commits

Two commits in one PR. Commit A is a mostly-mechanical registry rewrite, Commit B is the tightening proper. Keeping them separate matters even in one PR — reviewers can check A against today's behavior ("same inputs, same outputs") without tangling that against the shape-rejection rules B introduces.

**Commit A has two non-negotiable regression tests** (detailed in the TDD plan): the eager-alias-discovery test and the `media_attachment.valid_subjects` pin. These land in Commit A, not Commit B. They exist specifically because Commit A is not purely mechanical — two behavior changes ride in it (below) and these tests are what keep them honest. A Commit A that ships without both tests is incomplete; push back on any sequencing that defers them.

**Commit A is not purely mechanical** — two live behavior changes hide inside it. Call them out explicitly so reviewers know to look:

- **Alias discovery timing: lazy → eager.** Today `_get_literal_schemas()` walks `discover_alias_types()` on first access and caches. Under Commit A, the walk runs inside `CatalogConfig.ready()`. Safe because every `AliasBase` subclass lives in `apps.catalog.models.*` (7 subclasses, verified), and Django imports all model modules before any `ready()` fires. If a future contributor adds an `AliasBase` subclass outside `apps.catalog.models`, the eager walk misses it — same failure mode as today's lazy walk would have on that subclass, just surfaced at startup instead of first access.
- **`media_attachment.valid_subjects` frozen at `ready()` time.** Today each `MediaSupported` subject is implicit (resolved per-claim via ContentType). Under Commit A the set is snapshot once via `apps.get_models()`. If a subclass is added via plugin-style dynamic import after `ready()` completes, it won't be registered. Not a regression in practice (no such pattern exists in-repo), but add a `ready()`-time log line listing the discovered subjects so drift is greppable.

1. **Commit A — unified registry (behavior-preserving modulo the two items above).**
   - Add `ValueKeySpec` / `RelationshipSchema` (namespace + `value_keys` + `valid_subjects`) / `register_relationship_schema` / `get_relationship_schema` / `is_valid_subject` to [validation.py](../../../backend/apps/provenance/validation.py). Registry keyed by `namespace: str`.
   - Rewrite [catalog/claims.py](../../../backend/apps/catalog/claims.py): delete `_entity_ref_targets`, `_literal_schemas`, `RefKey`, `LiteralKey`, `_get_entity_ref_targets`, `_get_literal_schemas`, `register_relationship_targets`. Add `register_catalog_relationship_schemas()` with one `register_relationship_schema(...)` call per namespace (list below). Rework `build_relationship_claim`, `get_relationship_namespaces`, `get_all_namespace_keys` to read from the unified registry.
   - Rewrite `validate_relationship_claims_batch` internals to read `fk_target` tuples off `ValueKeySpec` entries (same existence-check semantics, new source).
   - Delete `_relationship_target_registry` and the old `register_relationship_targets` function in validation.py.
   - Rewrite [test_resolve_dispatch.py](../../../backend/apps/catalog/tests/test_resolve_dispatch.py) `TestLiteralSchemasAutoPopulated` (imports `_get_literal_schemas` which is deleted) — move assertions from `LiteralKey.value_key` / `.identity_key` shape to `ValueKeySpec` shape via `get_relationship_schema()`. Not a behavior change, just a form shift required to unblock the test-collection. Does not extend the regression gate — still only checking that alias discovery works.
   - `classify_claim` still uses the old structural check, no new rejections fire — claim-shape runtime behavior is identical. Mypy passes, full test suite passes, baseline unchanged.

2. **Commit B — classifier + validator + audit.**
   - Flip `classify_claim` to registry-driven classification (preserving DIRECT precedence, using `get_relationship_schema(field_name)` lookup).
   - Add `validate_single_relationship_claim` including the wrong-subject check.
   - **Pre-implementation audit (two parts):**
     - Direct `assert_claim` sites: grep all non-test `assert_claim(` calls in `apps/catalog`, `apps/media`, `apps/provenance` for calls that omit `claim_key=` when passing a relationship-namespace `field_name`. Current patterns use `build_relationship_claim` which returns a canonical key, so this is likely clean, but any bare `assert_claim(..., field_name="credit", ...)` will start raising `ValidationError` post-Commit B. Fix any such calls before proceeding (wrap them in `build_relationship_claim` or hand-craft the canonical key).
     - `execute_claims` spec producers: walk every `ClaimSpec(...)` producer in [apps/catalog/api/edit_claims.py](../../../backend/apps/catalog/api/edit_claims.py) and any other caller of `execute_claims`, and confirm each relationship-namespace spec sets `claim_key` via `build_relationship_claim(...).claim_key` or an equivalent canonical composition. Also confirm `execute_claims` still runs under `transaction.atomic()` so a mid-edit shape rejection rolls back the whole ChangeSet rather than committing a partial edit; add a regression test pinning that posture and a docstring note on `execute_claims`.
   - Wire the validator into `assert_claim` and `validate_claims_batch`.
   - No data-cleanup step bundled in — see "Data posture".

3. **Pre-merge dry-run (local).** With Commit B applied locally: `make reset-db` (or equivalent — wipe the localhost DB and reset migrations to 0001), then `make pull-ingest` + `make ingest`. Observe any validator rejections. Clean ⇒ merge. Dirty ⇒ rejections name the offending namespace + reason; fix at the extractor source, re-ingest, repeat until clean. This replaces the removed audit script as the "how bad is it" preview. **Scope caveat:** the dry-run is a smoke test over the canonical ingest inputs, not a completeness guarantee for shared-env state. It does not exercise user-edit paths (`execute_claims`), partial/hand-fixed ingests, or any divergence between localhost and shared env. **Before merge, confirm that no one has started using `execute_claims` in shared env.** Run against shared env (not localhost): `Claim.objects.filter(user__isnull=False).exists()` via `python manage.py shell` — `False` means no user-edit claims exist and the post-merge wipe is guaranteed clean. `True` means user-edit claims exist and they escape the pre-merge validator; same recovery (re-ingest) applies, just post-merge rather than pre-merge. This is a mechanical check; don't rely on asking around.

4. **Post-merge: wipe + re-ingest.** Same sequence against the shared environment so the DB is rebuilt fresh under the new validator. Behavior should match the pre-merge dry-run exactly.

Commit A is larger than a pure "scaffolding" commit would be, but the blast radius is bounded to `catalog/claims.py` and `provenance/validation.py` plus their tests. The size is bounded because every consumer of `build_relationship_claim` / `get_relationship_namespaces` sees unchanged behavior — those functions keep their signatures and semantics; only their implementation moves.

### Registered schemas

Every catalog relationship gets a `register_relationship_schema(...)` call in `register_catalog_relationship_schemas()`, once per namespace. Identity keys (`identity is not None`) drive `build_relationship_claim`'s claim_key composition; non-identity keys are shape-validated only. Missing any of these means resolver reads for that namespace stay unvalidated and [Step 5 of ResolveHardening.md](ResolveHardening.md) can't subscript those keys safely.

- **Alias (7 schemas, one per alias namespace):** `theme_alias` (valid_subjects=(Theme,)), `manufacturer_alias` ((Manufacturer,)), `person_alias` ((Person,)), `gameplay_feature_alias` ((GameplayFeature,)), `reward_type_alias` ((RewardType,)), `corporate_entity_alias` ((CorporateEntity,)), `location_alias` ((Location,)). Each → `alias_value: str (identity="alias")`, `alias_display: str (optional)`. Dynamic discovery via `discover_alias_types()` still happens — it just calls `register_relationship_schema` instead of populating `_literal_schemas`.
- **Abbreviation (1 schema):** `abbreviation`, `valid_subjects=(Title, MachineModel)`. → `value: str (identity="value")`.
- **Parent (2 schemas):** `theme_parent` ((Theme,)), `gameplay_feature_parent` ((GameplayFeature,)). Each → `parent: int (identity="parent", fk=<self>.pk)`.
- **Location (1 schema):** `location` ((CorporateEntity,)) → `location: int (identity="location", fk=Location.pk)`.
- **Credit (1 schema):** `credit`, `valid_subjects=(MachineModel, Series)`. → `person: int (identity="person", fk=Person.pk)`, `role: int (identity="role", fk=CreditRole.pk)`.
- **Gameplay feature (1 schema):** `gameplay_feature` ((MachineModel,)) → `gameplay_feature: int (identity="gameplay_feature", fk=GameplayFeature.pk)`, `count: int | None (optional)`.
- **Simple M2M (3 schemas):** `theme`, `tag`, `reward_type` each with `valid_subjects=(MachineModel,)`. → `<namespace>: int (identity=<namespace>, fk=<target>.pk)`.
- **Media attachment (1 schema):** `media_attachment`, `valid_subjects` derived at registration by walking `django.apps.apps.get_models()` and filtering to concrete subclasses of `MediaSupported` (today: `GameplayFeature`, `MachineModel`, `Manufacturer`, `Person`). → `media_asset: int (identity="media_asset", fk=MediaAsset.pk)`, `category: str | None (optional)`, `is_primary: bool (optional)`.

All registered fresh in the unified API — no migration shim needed because the old registries are deleted wholesale in the same commit.

## TDD plan

Assumes the "Commit sequence" above: Commit A (registry) → Commit B (classifier + validator) → pre-merge dry-run → post-merge wipe + re-ingest. Tests land with Commit B.

1. **Commit A is not TDD-gated for new behavior** (there isn't any), but **existing tests are the regression gate**. The full test suite must pass green, and the following modules specifically cover the rewritten surface and must stay green:
   - [apps/catalog/tests/test_claims.py](../../../backend/apps/catalog/tests/test_claims.py) — `build_relationship_claim` call-shape, `get_relationship_namespaces` / `get_all_namespace_keys` return sets, `register_relationship_targets` entry points.
   - [apps/catalog/tests/test_bulk_assert_claims.py](../../../backend/apps/catalog/tests/test_bulk_assert_claims.py) — bulk-path `build_relationship_claim` usage.
   - [apps/catalog/tests/test_api_claims_title.py](../../../backend/apps/catalog/tests/test_api_claims_title.py) — API-path namespace emission.
   - [apps/catalog/tests/test_resolve.py](../../../backend/apps/catalog/tests/test_resolve.py), [test_resolve_parents.py](../../../backend/apps/catalog/tests/test_resolve_parents.py), [test_resolve_aliases.py](../../../backend/apps/catalog/tests/test_resolve_aliases.py), [test_resolve_credits.py](../../../backend/apps/catalog/tests/test_resolve_credits.py), [test_resolve_dispatch.py](../../../backend/apps/catalog/tests/test_resolve_dispatch.py) — downstream consumers of namespace enumeration.
   - [apps/catalog/tests/test_validate_catalog.py](../../../backend/apps/catalog/tests/test_validate_catalog.py), [test_source_enabled.py](../../../backend/apps/catalog/tests/test_source_enabled.py) — cross-cutting validators that iterate namespaces.
   - [apps/provenance/tests/test_validation.py](../../../backend/apps/provenance/tests/test_validation.py) — `validate_relationship_claims_batch` existence-check semantics (new source, same behavior).

   If any test in these files fails, the rewrite has drifted from today's semantics — fix the rewrite, not the test.

   **Three required regression tests added in Commit A** (do not defer to Commit B):
   - _Eager alias discovery._ A test in `test_claims.py` that asserts `get_relationship_schema("theme_alias")` returns a non-`None` schema _immediately after Django startup_ without any prior resolver-path access — pinning the lazy→eager discovery timing shift. Today's test suite doesn't distinguish lazy from eager (the lazy cache populates on first access regardless), so without this test the behavior change rides in untested.
   - _`media_attachment.valid_subjects` pin._ A test that asserts `get_relationship_schema("media_attachment").valid_subjects == frozenset({GameplayFeature, MachineModel, Manufacturer, Person})`. Catches in CI the drift case where a new `MediaSupported` subclass lands without being picked up by the `apps.get_models()` walk (or the inverse: an existing subclass is removed). A log line at `ready()` time doesn't catch this — a test does. Update the test when the expected set genuinely changes; the edit is the forcing function.
   - _`build_relationship_claim` ↔ `make_claim_key` equivalence._ A parametrized test that, for every registered schema, builds a claim via `build_relationship_claim(namespace, **identity_kwargs, exists=True)` and asserts `claim.claim_key == make_claim_key(namespace, **identity_kwargs)`. Commit B's non-canonical-`claim_key` rejection (rule 7 above) assumes these two producers stay in lockstep — every production `ClaimSpec` ultimately sources its `claim_key` from one and every validator call composes via the other. Without this test, a refactor of `build_relationship_claim`'s internal composition (e.g. changing how identity labels are derived from `ValueKeySpec.identity`) could silently start failing the validator's canonical check on every production write, and the failure would first surface as "every edit rejects" in the pre-merge dry-run. The test is the cheap guard; land it in Commit A so Commit B can rely on it.

2. **Failing tests, one per rejection mode, per path:**
   - `assert_claim` path: assert `ValidationError` raised for each of — wrong subject (`field_name` registered but `subject.content_type not in schema.valid_subjects`), non-dict value, missing `exists`, non-bool `exists`, missing required key, wrong-scalar-type required key, wrong-scalar-type optional key, `bool` passed where `int` expected, unknown key, **non-canonical `claim_key` (omitted — defaults to `field_name`), non-canonical `claim_key` (hand-crafted with wrong PK or reordered identity parts)**.
   - Batch path: `validate_claims_batch(...)` returns `(valid, rejected_count)` — assert `rejected_count == 1` and the malformed claim is **not** in `valid`, for each of the same rejection modes as the `assert_claim` path (including both `claim_key` cases — omitted and mismatched). For shape rejection-reason assertions, call `validate_single_relationship_claim(...)` directly and assert on the `ValidationError` — shape validation now lives there, not in the batch function. For FK-existence rejection-reason assertions (batch-only concern), keep calling `validate_relationship_claims_batch(...)` directly (that function returns the rejected `list[Claim]`).
   - Classify-by-registry fix: a malformed relationship payload on a model with `extra_data` must reach the relationship validator (and be rejected), not land as `EXTRA`.
   - Registration collision guard: `register_relationship_schema(namespace="name", ...)` where `"name"` is a concrete field on any `valid_subjects` member raises `ImproperlyConfigured` at registration time. Covers the whole "DIRECT and RELATIONSHIP cannot both match" invariant at its actual enforcement point. No classifier-side precedence test — step 1 and step 2 of `classify_claim` are structurally disjoint under the guard.
3. Implement the tightenings. Tests go green.
4. **Pre-merge dry-run:** wipe localhost DB + reset migrations, `make pull-ingest`, `make ingest`. Any rejections name an extractor bug — fix at source, re-ingest, repeat until clean.
5. **Post-merge:** same wipe + re-ingest against the shared environment.

## Files touched

**Commit A — unified registry:**

- [apps/provenance/validation.py](../../../backend/apps/provenance/validation.py) — new `ValueKeySpec` / `RelationshipSchema` (namespace + `value_keys` + `valid_subjects`) / `register_relationship_schema` / `get_relationship_schema` / `is_valid_subject`, keyed by `namespace: str`. Delete `_relationship_target_registry` and the old `register_relationship_targets`. Rewrite `validate_relationship_claims_batch` internals to read `fk_target` tuples off `ValueKeySpec` entries.
- [apps/catalog/claims.py](../../../backend/apps/catalog/claims.py) — delete `RefKey`, `LiteralKey`, `_entity_ref_targets`, `_literal_schemas`, `_get_entity_ref_targets`, `_get_literal_schemas`, `register_relationship_targets`. Add `register_catalog_relationship_schemas()` with one `register_relationship_schema(...)` call per namespace. Rewrite `build_relationship_claim`, `get_relationship_namespaces`, `get_all_namespace_keys` to read from the unified registry. Alias-type dynamic discovery hooks into the new registration function.
- [apps/catalog/apps.py](../../../backend/apps/catalog/apps.py) — `CatalogConfig.ready()` calls `register_catalog_relationship_schemas()`.
- [apps/catalog/tests/test_claims.py](../../../backend/apps/catalog/tests/test_claims.py) (or wherever the existing claim-building tests live) — behavior-preserving; trivial touches if any.
- [apps/catalog/tests/test_resolve_dispatch.py](../../../backend/apps/catalog/tests/test_resolve_dispatch.py) — **not optional.** The top-level import `from apps.catalog.claims import _get_literal_schemas, build_relationship_claim` and the `TestLiteralSchemasAutoPopulated` class both reference symbols that Commit A deletes (`_get_literal_schemas`, `LiteralKey.value_key`, `LiteralKey.identity_key`). Rewrite the import to drop `_get_literal_schemas`, and rewrite the two test methods to assert via the new registry — e.g. `schema = get_relationship_schema("abbreviation")` + `assert schema is not None` for `test_contains_abbreviation`, and for `test_contains_all_alias_types`, walk `discover_alias_types()` and assert `get_relationship_schema(field_name)` returns a schema whose `value_keys` includes a `ValueKeySpec(name="alias_value", identity="alias", scalar_type=str, required=True)`. This rewrite is part of Commit A, not Commit B — without it the import fails at collection time and nothing else in the suite runs.

**Commit B — classifier + validator:**

- [apps/provenance/validation.py](../../../backend/apps/provenance/validation.py) — `classify_claim` registry-driven; new `validate_single_relationship_claim` (including wrong-subject check).
- [apps/provenance/models/claim.py](../../../backend/apps/provenance/models/claim.py) — `assert_claim` new `RELATIONSHIP` branch calling `validate_single_relationship_claim`.
- [apps/provenance/tests/test_validation.py](../../../backend/apps/provenance/tests/test_validation.py) — new rejection-mode tests (including wrong-subject and non-canonical `claim_key`).
- [apps/media/tests/test_media_claims.py](../../../backend/apps/media/tests/test_media_claims.py) — **`test_non_media_supported_entity_skipped` flips from "write succeeds, resolver skips" to "write raises `ValidationError`".** Today this test calls `Claim.objects.assert_claim(theme, "media_attachment", …)` and asserts the resolver produces no `EntityMedia`; under the plan the `assert_claim` call itself raises (Theme ∉ `media_attachment.valid_subjects`). Rewrite to `pytest.raises(ValidationError)` around the `assert_claim` call and drop the resolver assertion — the write-path rejection supersedes the "silently skipped" posture. Other tests in this module use `MachineModel` / `Manufacturer` / `Person` / `GameplayFeature` (all supported) and stay green.

## Verification

- `uv run --directory backend pytest apps/provenance/tests/test_validation.py apps/catalog/tests/test_claims.py apps/catalog/tests/test_bulk_assert_claims.py apps/catalog/tests/test_resolve_bulk.py apps/catalog/tests/test_resolve.py apps/catalog/tests/test_resolve_aliases.py apps/catalog/tests/test_resolve_credits.py apps/catalog/tests/test_resolve_parents.py apps/catalog/tests/test_resolve_dispatch.py apps/media/tests/test_media_claims.py` — all tests pass. (Broader `make test` also, but this is the focused set.)
- `./scripts/mypy` — baseline unchanged (this step has no mypy impact).
- **Pre-merge dry-run:** wipe localhost DB, reset migrations to 0001, `make pull-ingest`, `make ingest`. No rejections on clean data. If rejections appear, they're real malformed payloads upstream ingest is producing and must be fixed at the source before merging.
- **Post-merge:** same wipe + re-ingest against the shared environment.
- After landing (and after the post-merge wipe + re-ingest), [Step 5 of ResolveHardening.md](ResolveHardening.md) (resolver subscript flip) is unblocked.

## Relation to model-driven metadata

This registry is intentionally hand-maintained. The model-driven metadata umbrella ([ModelDrivenMetadata.md](../model_driven_metadata/ModelDrivenMetadata.md)) proposes moving these declarations onto the through-model classes as a typed `catalog_relationship_spec` ClassVar ([ModelDrivenCatalogRelationshipMetadata.md](../model_driven_metadata/ModelDrivenCatalogRelationshipMetadata.md)), derived at `ready()` and pushed into a registry that looks very much like this one. That move is deferred until a genuinely _independent_ consumer materializes — e.g. frontend edit metadata being actually built, not hypothetical.

Note the distinction: this PR's consumers (`classify_claim`, `validate_single_relationship_claim`, `validate_relationship_claims_batch`, `build_relationship_claim`, and — via Step 3's consistency test — the read-side TypedDicts) are what make the _unified registry_ pay off today. They don't meet the spec-move's ≥2-consumers bar because they're all facets of the same backend write/read path, tested against each other. The spec move is waiting for a second consumer that would motivate the richer `through_model` / `subject_fks` fields and `(namespace, subject_content_type)` keying, which this PR's consumers don't need.

The spec doc's identity-vs-UC cross-check (verifying `subject_fks ∪ identity_fields` matches one `UniqueConstraint` per through-model at `ready()`) is the piece worth lifting eventually, but it's deferred with the rest of the spec work — lifting it alone would require `through_model` and `subject_fks` on the schema and `(namespace, subject_content_type)` keying, which this PR otherwise doesn't need. When the second consumer arrives and the spec move lands, `register_catalog_relationship_schemas()` is replaced with a walk over a `ClaimThroughModel` marker base that emits the same `RelationshipSchema` objects plus the richer fields the cross-check needs. The registry interface (`get_relationship_schema`, `is_valid_subject`) stays the same; consumers don't change.
