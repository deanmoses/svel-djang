# Model-Driven Metadata Cleanup

Sibling doc to [ModelDrivenMetadata.md](ModelDrivenMetadata.md). The umbrella doc establishes the principle and the canonical Shape 1/2/3 templates. This doc covers the small-but-real gap between those templates and the existing codebase — typing inconsistencies, one fragile convention, and two hand-maintained lists that should be `_meta` walks.

## Scope

Bring existing model-driven metadata patterns to the canonical conventions in [ModelDrivenMetadata.md](ModelDrivenMetadata.md) before new spec work (`CatalogRelationshipSpec`, `CitationSourceSpec`) starts introducing more. Two motivations:

1. **Consistency as a copy-target.** Right now, a new contributor can copy `claim_fk_lookups` (untyped ad-hoc `getattr`) or `MEDIA_CATEGORIES` (`ClassVar`-typed, mixin-discovered) and propagate whichever inconsistency they happened to encounter. After this cleanup, any existing class attr is a valid template.
2. **Warm-up for the spec work.** The `AliasBase` upgrade and the Cluster 3 `_meta`-walk replacements exercise the same machinery (explicit identity attr, `ready()`-time discovery, parity tests) that `CatalogRelationshipSpec` needs — on a much smaller blast radius.

## Shape 2 typing sweep — _landed_

Existing Shape 2 class attrs that work correctly but lack `ClassVar[...]` typing. Each is a one-line edit.

| Attr                            | Pre-sweep                     | Final                      |
| ------------------------------- | ----------------------------- | -------------------------- |
| `claim_fk_lookups`              | untyped, bare `getattr`       | `ClassVar[dict[str, str]]` |
| `claims_exempt`                 | untyped                       | `ClassVar[frozenset[str]]` |
| `soft_delete_cascade_relations` | untyped → `tuple[str, ...]`   | `ClassVar[frozenset[str]]` |
| `soft_delete_usage_blockers`    | untyped → `tuple[str, ...]`   | `ClassVar[frozenset[str]]` |
| `MEDIA_CATEGORIES`              | already `ClassVar[list[str]]` | unchanged                  |

The `soft_delete_*` attrs went through two commits: a first pass that mirrored the tuple literal on the RHS (`ClassVar[tuple[str, ...]]`), then a second pass that corrected the semantics to `ClassVar[frozenset[str]]` with a `frozenset({...})` RHS. History is preserved in the arrow above as a worked example of the rule below.

Rule of thumb for these annotations: pick the collection type that matches the **semantics** of the attr, not just what the RHS literal happens to look like. Order and duplicates are meaningless for `soft_delete_*` (they're unordered sets of relation names — same shape as `claims_exempt`), so `frozenset[str]` is the right annotation even if the RHS was originally written as a tuple literal. Update the RHS to `frozenset({...})` at the same time, and update any consumer `getattr(..., default)` defaults to match the annotated type (`frozenset()` here, not `()`) — don't lie about the shape in the annotation or smuggle a mismatched default past the type checker.

Consumer-side: the bare `getattr(model, "attr", default)` reads stay — they're the canonical Shape 2 access pattern per the umbrella. Only the declarations get typed.

### Declaration inventory (verified)

Confirmed by grep across `backend/apps/` before the sweep landed:

- `claim_fk_lookups` — `catalog/models/location.py` (1 site; `Location` only).
- `claims_exempt` — `catalog/models/location.py` (1 site; `Location` only).
- `soft_delete_cascade_relations` — `catalog/models/title.py` (1 site; `Title` only).
- `soft_delete_usage_blockers` — 5 sites across `catalog/models/`: `theme.py` (`Theme`), `taxonomy.py` (`RewardType`, `Tag`, `CreditRole`), `gameplay_feature.py` (`GameplayFeature`).
- `MEDIA_CATEGORIES` — base annotation on `MediaSupported` in `core/models.py`; concrete subclasses (`person`, `manufacturer`, `machine_model`, `gameplay_feature`) just assign values without re-annotating. This is the canonical "base annotates, subclasses assign" pattern and is the template `entity_type` should follow.

Every consumer uses `getattr(model_class, "attr", default)` with a default matching the annotated type — no shadowing, no drift risk. No base class declares any of the four opt-in attrs, so subclass declarations are the only source of truth.

### `entity_type` typing — separate sub-item, _blocked on shape decision_

`entity_type` (LinkableModel's public identifier, listed in the umbrella as "already in the codebase") is also untyped today. It's Shape 2, same pattern, but has a bigger blast radius than the one-liners above: annotate the base on `LinkableModel` and touch every concrete subclass assignment.

**Open question before implementation:** what's the right annotation? The `frozenset[str]` follow-up on `soft_delete_*` established the rule of matching annotations to semantics, not RHS literal shape. `entity_type` values are a closed set (`"theme"`, `"tag"`, `"gameplay-feature"`, `"machine-model"`, …), not arbitrary strings. Three options:

- **`ClassVar[str]`** — matches the RHS literal; cheapest; undertypes, per the `soft_delete_*` lesson.
- **`ClassVar[Literal[...]]`** per subclass — strongest typing; lets callers refine on `entity_type`; but each subclass carries its own narrow `Literal` annotation, which is verbose.
- **`ClassVar[EntityType]`** where `EntityType = Literal[...]` or `Enum` at module level — declare the closed set once, reuse the alias everywhere.

Decide before starting. Implementing `ClassVar[str]` and redoing it would repeat the exact mistake the follow-up commit fixed. No consumer-side changes regardless of choice.

### Optional: `MEDIA_CATEGORIES` readiness validator

Not strictly required, but a `ready()`-time validator asserting every concrete `MediaSupported` subclass sets `MEDIA_CATEGORIES` to a non-empty list would catch "forgot to declare" errors at startup instead of first request. Defer if it adds friction; land if it's cheap.

## Shape 3 upgrades

### `AliasBase` — explicit identity attr — _landed_

Previously `_alias_registry.py` derived the claim namespace from `_meta.verbose_name` (`f"{verbose_name.replace(' ', '_')}_alias"`) — the "silver" fragility flagged in the Shape 3 ranking, since changing a model's `verbose_name` would silently shift the claim namespace. The upgrade:

1. `AliasBase` declares `alias_claim_field: ClassVar[str]` (base annotation, no default) and each of the seven concrete subclasses assigns the explicit value (`"theme_alias"`, `"person_alias"`, etc.). Same "base annotates, subclasses assign" pattern as `MEDIA_CATEGORIES`.
2. `AliasBase.__init_subclass__` enforces the declaration at class-creation time — a forgetful or empty-string subclass raises `TypeError` at import, before any discovery walk runs. `discover_alias_types()` can therefore do direct `cls.alias_claim_field` access and trust the annotation.
3. `apps.check_models_ready()` runs at the top of `discover_alias_types()` to guard the `lru_cache` against a too-early call (the function walks `__subclasses__()` and reads `_meta`).

Parity test in `test_resolve_dispatch.py` asserts the full `{(parent_model, claim_field)}` set of seven tuples — catches both typos in the claim_field string and right-value-wrong-class misdeclarations. New `AliasBase` subclasses fail the test and force intentional review.

**Grep-audit result (safe).** Beyond `_alias_registry.py`, the derived strings appear as literals in `resolve/_relationships.py` (per-parent `resolve_*_aliases` functions), `management/commands/ingest_pinbase.py`, `api/themes.py`, and tests. Every existing literal matches the derived value 1:1 — the upgrade only makes the derivation explicit; no string values change, and nothing reaches the frontend.

### `core/entity_types.py` — cosmetic alignment

Currently uses a module-level `_ENTITY_TYPE_MAP: dict | None = None` with a `global` statement in `get_linkable_model()`. Already functionally gold. Swap to `@functools.lru_cache(maxsize=1)` on a build function to match the canonical template and `_alias_registry.py`. Purely cosmetic; skip if it reads as churn.

## Cluster 3 — `_meta`-walk replacements

Two hand-maintained lists that are one `_meta` / app-registry walk away from being derived. Both are Shape 1 (no spec, no class attr).

### Cache-invalidation signal list — _landed_

Previously `catalog/signals.py` hand-listed eight models whose saves should bust the `/all/` cache. The upgrade replaced the list with an app-registry walk at `ready()` time: concrete `CatalogModel` subclasses plus three explicit extras (`Location`, `CorporateEntityLocation`, `Credit`). A parity test in `test_api_cache.py` pins the derived 22-model set so new `CatalogModel` additions fire the test and get reviewed intentionally.

Lessons worth retaining for future `_meta`-walk work:

- **Blanket inclusion beats opt-in markers** for correctness-critical paths. An alternative design — add `bust_all_cache_on_save: ClassVar[bool]` and let models opt in — would have recreated the exact drift surface the walk was eliminating. Fail-safe-by-construction is the right default: new entity → automatic freshness, at the cost of some over-invalidation on models that happen not to be embedded in `/all/` payloads (a cache-hit-rate cost, not a correctness cost).
- **Widening from 8 → 22 was a bug fix, not a behavior regression.** The old list was missing taxonomy models (`Theme`, `Tag`, `GameplayFeature`, `RewardType`, `Series`, `Franchise`, etc.) that _are_ embedded in `/all/` payloads; edits to them via admin or outside the claims pipeline produced stale responses. That's exactly the drift the walk was designed to catch.
- **The parity test's hardcoded expected set is the point.** It pins the derived output so new models fire the test and force intentional review. Don't collapse the expected set into the same walk as production — that would make the test assert `x == x`.
- **Document the coverage gaps in code, not just PR discussion.** `MachineModel*` through-rows and `AliasBase` subclasses aren't covered by this signal path because they're populated by the claims resolver (which calls `invalidate_all()` directly via `transaction.on_commit`). A comment in `signals.py` explains this so future maintainers can find the answer to "why isn't `MachineModelTheme` in here?" without having to git-blame.

### `_SOURCE_FIELDS` in `citation/seeding.py`

Currently a hand-sync'd frozenset of scalar column names on `CitationSource`. Upgrade: derive from `CitationSource._meta.get_fields()` minus relations at seed time. Parity test catches drift if a scalar is added to the model but forgotten in seed YAML.

**Defer to `CitationSourceSpec` work.** This cleanup target overlaps the upcoming [ModelDrivenCitationSourceMetadata.md](ModelDrivenCitationSourceMetadata.md) axis, which will very likely subsume or reshape what `_SOURCE_FIELDS` describes. Landing it as a standalone `_meta`-walk now and then revisiting it under `CitationSourceSpec` means touching citation seeding twice. Skip until the citation spec work starts, then fold into that effort.

## Resolver signature standardization

Mechanical prep work for `CatalogRelationshipSpec` that has no dependency on the spec itself and reads cleanly as cleanup. See the "Resolver strategy" section of [ModelDrivenCatalogRelationshipMetadata.md](ModelDrivenCatalogRelationshipMetadata.md) for the full audit; the cleanup items are:

1. Rename `entity_ids` → `subject_ids` on all bespoke resolvers (affects `resolve_all_corporate_entity_locations`, `resolve_media_attachments`, and any others surfaced by the audit). Keep the existing `model_ids` callers working by renaming them too.
2. Drop the unused `dict[str, int]` stats return from `resolve_all_corporate_entity_locations` (no consumer reads it).
3. Confirm every bespoke resolver conforms to `(subject_ids: set[int] | None = None) -> None` after the above.

This is not _required_ before `CatalogRelationshipSpec` lands — the spec PR could do it — but separating it keeps the spec PR narrowly focused on introducing the spec + generic resolver, and lets the rename land sooner as an independent refactor.

## Sequencing

### Landed

1. Shape 2 typing sweep (table) — including the `frozenset[str]` follow-up for `soft_delete_*`.
2. Cache-invalidation signal list `_meta` walk — including parity test and coverage-gap comment.
3. `AliasBase` explicit-identity-attr upgrade.

### Next

1. **`entity_type` typing** — blocked on shape decision (see "Open question" in that section).

### Remaining

1. Resolver signature standardization — independent cleanup; can land any time before `CatalogRelationshipSpec` implementation.
2. `entity_types.py` cosmetic — optional.

None of these have hard dependencies on the new spec work. They can land before or alongside it; the value is that new-spec contributors have a clean, consistent landscape to copy from.
