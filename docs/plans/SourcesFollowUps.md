# Sources / Edit-History Follow-ups

Surfaced while landing the Sources + Edit-History consolidation (branch `refactor/consolidate-sources-edit-history`). Everything below is independent of that PR and can be picked up separately.

Ordered by rough ROI.

---

## Decide the soft-delete policy for per-entity provenance endpoints

**Problem.** `GET /api/pages/edit-history/{type}/{slug}/` has always returned 200 for soft-deleted entities (no `.active()` filter). `GET /api/pages/sources/{type}/{slug}/` was previously inconsistent — the old `/api/pages/evidence/` predecessor _did_ filter `.active()`. The consolidation refactor made both consistent by dropping `.active()` from sources, but this was a policy call made implicitly, not deliberately.

**Why it matters.** The two camps:

- **"Soft-delete is soft"** — deletion is reversible curation; audit/provenance surfaces should remain inspectable by any caller who knows the slug. The current (post-refactor) behavior.
- **"Deleted means hidden"** — once deleted, the API shouldn't leak field values via direct URL even to callers who know the slug. Under this policy, _both_ endpoints should filter `.active()`, and the current edit-history behavior is a latent bug.

Normal SvelteKit navigation already gates on the parent `[slug]/+layout.server.ts` (which does filter `.active()` via `/api/pages/{entity}/{slug}`), so human browsing is unaffected either way. The question is about the direct API surface — scrapers, admin tools, future API consumers.

**Shape.**

1. Make a deliberate product call.
2. Whichever direction, write a regression test for both endpoints asserting the chosen behavior for soft-deleted entities. There is currently no test for either side — the behavior is just whatever the code happens to do.
3. If "deleted means hidden" wins, add `.active()` back to [sources_page](../../backend/apps/provenance/page_endpoints.py) and add it for the first time to `edit_history_page`.

**Starting points:**

- [backend/apps/provenance/page_endpoints.py](../../backend/apps/provenance/page_endpoints.py) — both endpoints live here
- No existing test covers this edge case in [backend/apps/provenance/tests/](../../backend/apps/provenance/tests/).

**Risk.** Low. Whichever policy is chosen, the code change is one line per endpoint plus a test.

---

## Drop the prefetch fallback in `_serialize_model_detail`

**Problem.** [machine_models.py:346-361](../../backend/apps/catalog/api/machine_models.py#L346-L361) reads `active_claims` off the prefetched model, and if missing, reconstructs the prefetch queryset inline — with a `Case/When` priority annotation that duplicates the logic in [`claims_prefetch()`](../../backend/apps/provenance/helpers.py). If the priority tiebreak rule in `claims_prefetch()` ever changes, this fallback will silently diverge.

**Why it matters.** Silent divergence between two places computing "what does a winning claim look like" is exactly the bug that will show up in production months later as "sometimes the wrong source wins." The fallback is defensive coding against a contract violation — and the right response to a contract violation is a loud failure, not a silent patch.

**Shape.** Remove the fallback block. If `active_claims` isn't prefetched, the function should raise (or return, but fail loudly). The callers of `_serialize_model_detail` should always prefetch.

**Starting points:**

- [backend/apps/catalog/api/machine_models.py:346-361](../../backend/apps/catalog/api/machine_models.py#L346-L361) — the fallback to remove
- [backend/apps/provenance/helpers.py](../../backend/apps/provenance/helpers.py) — the canonical prefetch to rely on
- `grep -n "_serialize_model_detail" backend/apps/catalog/api/machine_models.py` — call sites to verify all prefetch claims before calling

**Risk.** Low. If tests pass, callers are doing the right thing. If they don't, we've found a real bug.

---

## Update `WebApiDesign.md` with the reads-vs-writes namespace split

**Problem.** [docs/WebApiDesign.md](../WebApiDesign.md) formalizes the reads-under-`/api/pages/` vs resources-under-`/api/` split, but says nothing about **where write endpoints for resource concepts belong**. This refactor established a convention — resource-style mutations live under a namespaced router like `/api/provenance/claims/{id}/revert/`, not under `/api/pages/`. That decision isn't written down anywhere, so the next person designing a write endpoint will re-derive it (or not).

**Why it matters.** The doc is the project's canonical API design guidance. Conventions implicit in code get lost.

**Shape.** Add a short section to `WebApiDesign.md`:

- `/api/pages/...` = reads only (page models)
- `/api/{resource}/...` = reads (listings, lookups) + writes for that resource
- For cross-cutting mutations (like revert, undo) that operate on a concept rather than a specific entity type, namespace under the concept: `/api/provenance/...`, `/api/media/...`.

**Starting points:**

- [docs/WebApiDesign.md](../WebApiDesign.md)
- This PR's moves as concrete examples: `POST /api/provenance/claims/{id}/revert/`, `POST /api/provenance/undo-changeset/`.

**Risk.** Zero. Doc-only.

---

## Shared resolver helper for per-entity generic endpoints

**Problem.** Both [`edit_history_page`](../../backend/apps/provenance/page_endpoints.py) and [`sources_page`](../../backend/apps/provenance/page_endpoints.py) start with the same 3-line dance: `get_linkable_model(entity_type)` wrapped in `try/except ValueError → 404`, then `get_object_or_404(model_class, slug=slug)`. Any future generic per-entity provenance endpoint (relationships, suggestions, moderation queue, etc.) will repeat it.

**Why it matters.** Not urgent at two call sites, but worth factoring at three. Also the right place to pin the 404 message wording so endpoints stay consistent.

**Shape.** A small helper (decorator or plain function) that takes `(entity_type, slug)` and returns the entity, or raises a Ninja `Status(404)`. Something like:

```python
def resolve_linkable_entity(entity_type: str, slug: str, *, queryset=None):
    try:
        model_class = get_linkable_model(entity_type)
    except ValueError:
        raise HttpError(404, f"Unknown entity type: {entity_type}")
    qs = queryset if queryset is not None else model_class.objects.all()
    return get_object_or_404(qs, slug=slug)
```

**Starting points:**

- [backend/apps/provenance/page_endpoints.py](../../backend/apps/provenance/page_endpoints.py) — both current call sites
- [backend/apps/core/entity_types.py](../../backend/apps/core/entity_types.py) — likely home for the helper

**Risk.** Low. Two call sites, good test coverage.

---

## Document the `entity_type` slug convention

**Problem.** The mapping between frontend route segments and backend `entity_type` strings is implicit (`/titles/` routes use `entity_type="title"`; `/corporate-entities/` uses `"corporate-entity"`; etc.). I had to grep existing loaders to derive it when generating the new sources routes. Anyone adding a new entity type will have to do the same.

**Why it matters.** This is a piece of "load-bearing knowledge" that exists only in examples. One place for the naming rule (hyphenated singular of the route segment) would prevent a class of "I named it plural and now nothing works" bugs.

**Shape.** A short section in [docs/DomainModel.md](../DomainModel.md) or a new `docs/EntityTypes.md`: the canonical list of entity types, the corresponding route segment, and the rule ("hyphenated singular; matches `CatalogModel.entity_type`").

Even better: derive the canonical list by inspection at doc-build time, so the list can't go stale. But a plain table is 80% of the value.

**Risk.** Zero. Doc-only.

---

## Audit other frontend components for dead URL-construction props

**Problem.** `EditHistory.svelte` accepted `entityType` and `entitySlug` props that existed _solely_ to construct the revert URL. When I moved revert to a claim-keyed URL, those props became dead weight — I dropped them and updated all 18 call sites. The same pattern may exist elsewhere: components taking props to build URLs that could be self-contained once the URL shape is designed right.

**Why it matters.** Dead props are a quiet form of coupling — every component that takes them forces callers to thread them through, often from a parent that also doesn't need them. The fix is usually free: move URL construction inside the component or redesign the endpoint to not need routing context.

**Shape.** Grep for components that accept `entityType` + `entitySlug` (or similar) and verify each prop is actually consumed for something other than URL construction.

**Starting points:**

- `grep -rn "entityType" frontend/src/lib/components/` — enumerate candidates
- [frontend/src/lib/components/EditHistory.svelte](../../frontend/src/lib/components/EditHistory.svelte) — the canonical example of what "good" looks like post-refactor
- [frontend/src/lib/components/EntitySources.svelte](../../frontend/src/lib/components/EntitySources.svelte) — another fully-decoupled example

**Risk.** Medium per component. Each candidate needs investigation; some props may turn out to be load-bearing.

---

## Rename `entity-provenance.ts` → `entity-sources.ts`

**Problem.** The component was renamed `EntityProvenance.svelte` → `EntitySources.svelte`, but its companion helper [`entity-provenance.ts`](../../frontend/src/lib/components/entity-provenance.ts) (containing `groupSourcesByField`) kept its old name.

**Why it matters.** Pure naming consistency. Low priority, but trivial to fix while the diff is fresh.

**Shape.** Rename the file; update the one import in [EntitySources.svelte](../../frontend/src/lib/components/EntitySources.svelte).

**Risk.** Zero.

---

## Parity test for edit-history soft-delete behavior

**Problem.** Whatever policy is chosen in the soft-delete follow-up above, there's currently **no test** covering "does GET edit-history for a soft-deleted entity return 200 or 404?" The behavior is whatever the code happens to do.

**Shape.** Covered by the soft-delete follow-up above. Called out separately because even if that product decision ratifies the status quo ("yes, soft-delete is soft, both endpoints return 200"), a regression test is still needed so nobody accidentally changes it later.

---

## Meta-observation: the plan-mode review cycle worked

Not a follow-up per se, but worth noting: this PR went through a plan-file review pass, then an AI code-review pass after the plan was drafted, and found two genuine bugs pre-commit (the revert blast-radius when moving to changeset-keyed URLs — reverted to claim-keyed after review; and using `ChangeSetSchema` vs `CitedChangeSetSchema` for evidence). Both would have shipped without the review pass. Worth keeping in the toolkit for other refactors this size.
