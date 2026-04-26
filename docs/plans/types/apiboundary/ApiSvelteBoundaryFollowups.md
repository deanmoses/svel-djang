# API Boundary Followups

## Context

Items deferred until after the API boundary work in
[ApiSvelteBoundary.md](ApiSvelteBoundary.md) lands. They either
depend on the rename being settled, or are surfaced by doing the
boundary work and only become tractable once it's done.

This doc starts thin. Most items will be added as the boundary work
surfaces them — collision resolutions in the rename pass that reveal
real shape duplication, naming inconsistencies the rationalization
table couldn't fully resolve, page-vs-resource shape divergences the
rename couldn't predict, and so on.

## Consolidate `ManufacturerCorporateEntity` with `CorporateEntityListItem`

The rename pre-flight resolved both `…Schema`/`…ListSchema`
collision pairs by renaming the embedded shape under a
`Manufacturer*` name (parallel to `ManufacturerPerson`):

`CorporateEntitySchema` → `ManufacturerCorporateEntity`,
`CorporateEntityListSchema` → `CorporateEntityListItem`. These
have meaningfully different fields today:
`ManufacturerCorporateEntity` lacks `manufacturer` and
`model_count` because both are context-redundant when nested
under a manufacturer detail.

After the rename lands, revisit whether
`ManufacturerCorporateEntity` and `CorporateEntityListItem` should
consolidate. The question: is the field divergence
(`manufacturer` ref + `model_count` on the list shape) load-bearing,
or could a single schema cover both uses with optional/computed
fields? Deferred because consolidation is an API-shape decision that
benefits from seeing the renamed contract in place first.

## Sweep body-validation 422s onto every request-body endpoint

[ApiErrors.md](ApiErrors.md)'s §2 made a global behavioral change:
Ninja's malformed-body 422 now reshapes to `ValidationErrorSchema`.
That means _any_ endpoint that accepts a request body can produce
`ValidationErrorSchema` when Pydantic rejects the input —
independent of whether the view explicitly raises 422.

§3's sweep enumerated targets by what views _raise_
(`execute_claims`, `HttpError(422, …)`), not by whether they
accept a body. Roughly 15–20 endpoints declare a 422 shape that
doesn't include `ValidationErrorSchema`, or declare no 422 at
all:

- Catalog delete endpoints (generator + bespoke): currently
  `422: SoftDeleteBlockedSchema | AlreadyDeletedSchema`.
- Catalog restore endpoints (generator + bespoke): currently
  `422: ErrorDetailSchema`.
- Citation writes (5 endpoints in
  [citation/api.py](../../../../backend/apps/citation/api.py)):
  currently `422: ErrorDetailSchema`.
- Provenance `revert_claim`, `undo_changeset`,
  `create_citation_instance`: currently `422: ErrorDetailSchema`.
- Media `upload`, `detach`, `set_primary`: 0 / 0 / 0 declared.

The fix is mechanical: union `ValidationErrorSchema` into each
endpoint's 422 declaration (or add it where 422 is undeclared).

**Why deferred.** ApiErrors.md's §3 was a coherent sweep —
"declare what views explicitly raise." Body-validation 422s are
a categorically different sweep — "declare what Pydantic body
validation can raise on every body-accepting endpoint." Two PRs
with clear charters are easier to review than one mixed.

**No runtime breakage today.** The frontend parser dispatches by
body shape, not status code, and no frontend code imports error
schemas at type level. The miscoverage shows up as `/api/docs`
inaccuracy and as wrong types if a future consumer narrows on
the declared 422 shape. Worth fixing for contract honesty; not
urgent.

## Try `--immutable` for openapi-typescript

Marks every generated property and array `readonly`. Defensive
default for response types the frontend should never mutate; useful
for catching accidental mutation of API data.

**Empirical impact.** Tried alongside the other generator flags and
backed out: 341 svelte-check errors across 151 files. Almost all are
request-body construction sites that spread typed response objects
into mutable shapes, plus a handful of array-method calls on
`readonly` arrays. The friction is real and concentrated.

If revisited, ship as its own PR: the fix pattern is mostly mechanical
(add `readonly` to local types or copy arrays before mutation), but
the volume means a dedicated review pass. Skip entirely if the safety
benefit doesn't justify the churn.

## Split schema per-tag

If after the boundary work lands, `frontend/src/lib/api/schema.d.ts`
still feels unwieldy for AI/human reading, split it per Ninja tag so
working in catalog code only requires reading
`schema.catalog.d.ts` (~2–3k lines) instead of all 10k.

Requires build-tooling work: filter the OpenAPI doc per tag and run
`openapi-typescript` N times. The barrel from
[ApiSvelteBoundary.md](ApiSvelteBoundary.md) means consumers don't
change.

Skip this entirely if the file no longer feels like a problem after
the rename and barrel land.

## Page-model vs resource-canonical schema split

[docs/ApiDesign.md](../../../ApiDesign.md) draws a sharp distinction
between resource APIs (`/api/<entity>/...`) and page APIs
(`/api/pages/<entity>/...`), with page endpoints returning page
models. In practice, every `*Detail` schema today is shared between
the two — the page endpoint returns the same shape as the resource
detail endpoint. Splitting them is an architectural question, not a
naming one, and is explicitly out of scope for the rename.

After the boundary work lands and the names are settled, decide
whether to actually split them. The decision should be made per
page, not as a sweeping policy: most pages probably don't need a
distinct shape, and the conceptual cleanliness doesn't justify a
parallel schema family without concrete divergence. When divergence
shows up — a page wants a field the resource detail doesn't, or vice
versa — that's the point at which a `…Page` schema earns its name.
