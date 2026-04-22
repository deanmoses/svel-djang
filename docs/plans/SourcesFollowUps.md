# Sources / Edit-History Follow-ups

Surfaced while landing the Sources + Edit-History consolidation (branch `refactor/consolidate-sources-edit-history`). Everything below is independent of that PR and can be picked up separately.

Ordered by rough ROI.

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
